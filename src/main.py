import asyncio
import sys
import time

import onnxruntime as ort

from gui.hub import Hub
from gui.login import login
from gui.main import App
from gui.select_brawler import SelectBrawler
from lobby_automation import LobbyAutomation
from play import Play
from stage_manager import StageManager
from state_finder.main import get_state
from time_management import TimeManagement
from utils import (
    api_base_url,
    async_notify_user,
    check_version,
    cprint,
    current_wall_model_is_latest,
    get_brawler_list,
    get_latest_version,
    get_latest_wall_model_file,
    load_toml_as_dict,
    update_icons,
    update_missing_brawlers_info,
    update_wall_model_classes,
)
from window_controller import WindowController

pyla_version = load_toml_as_dict("./cfg/general_config.toml")["pyla_version"]


def _log_gpu_provider():
    providers = ort.get_available_providers()
    if "DmlExecutionProvider" in providers:
        print("DirectML GPU active")
    elif "CUDAExecutionProvider" in providers:
        print("CUDA GPU active")
    else:
        print("Running on CPU")


class _BotSession:

    MODEL_DIR = "./models/"
    MODELS = ["mainInGameModel.onnx", "tileDetector.onnx"]

    def __init__(self, data):
        self.data = data
        self.window_controller = WindowController()
        model_paths = [self.MODEL_DIR + m for m in self.MODELS]
        self.Play = Play(*model_paths, self.window_controller)
        self.Time_management = TimeManagement()
        self.lobby_automator = LobbyAutomation(self.window_controller)
        self.Stage_manager = StageManager(data, self.lobby_automator, self.window_controller)
        self.states_requiring_data = ["play_store", "lobby"]

        if data[0]["automatically_pick"]:
            print("Picking brawler automatically")
            self.lobby_automator.select_brawler(data[0]["brawler"])
        self.Play.current_brawler = data[0]["brawler"]
        self.no_detections_action_threshold = 60 * 8
        self._init_trophy_state()

        self.state = None
        cfg = load_toml_as_dict("cfg/general_config.toml")
        try:
            self.max_ips = int(cfg["max_ips"])
        except (ValueError, TypeError):
            self.max_ips = None
        self.run_for_minutes = int(cfg["run_for_minutes"])
        self.start_time = time.time()
        self.in_cooldown = False
        self.cooldown_start_time = 0
        self.cooldown_duration = 3 * 60

    def _init_trophy_state(self):
        obs = self.Stage_manager.Trophy_observer
        obs.win_streak = self.data[0]["win_streak"] or 0
        obs.current_trophies = self.data[0]["trophies"] or 0
        obs.current_wins = self.data[0]["wins"] if self.data[0]["wins"] != "" else 0

    def _notify_and_exit(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            screenshot = self.window_controller.screenshot_numpy()[0]
            loop.run_until_complete(async_notify_user("bot_is_stuck", screenshot))
        finally:
            loop.close()
        print("Bot stuck — user notified. Shutting down.")
        self.window_controller.keys_up(list("wasd"))
        self.window_controller.close()
        sys.exit(1)

    def _tick_state(self, frame):
        if self.Time_management.state_check():
            state = get_state(frame)
            self.state = state
            if state != "match":
                self.Play.time_since_last_proceeding = time.time()
            frame_data = frame if state in self.states_requiring_data else None
            self.Stage_manager.do_state(state, frame_data)

        if self.Time_management.no_detections_check():
            for key, last_seen in self.Play.time_since_detections.items():
                if time.time() - last_seen > self.no_detections_action_threshold:
                    self._notify_and_exit()

        if self.Time_management.idle_check():
            self.lobby_automator.check_for_idle(frame)

    def main(self):
        _log_gpu_provider()
        s_time = time.time()
        c = 0
        while True:
            if self.max_ips:
                frame_start = time.perf_counter()

            if self.run_for_minutes > 0 and not self.in_cooldown:
                if (time.time() - self.start_time) / 60 >= self.run_for_minutes:
                    cprint(f"Session time ({self.run_for_minutes}m) done, finishing current game...", "#e8a838")
                    self.in_cooldown = True
                    self.cooldown_start_time = time.time()
                    self.Stage_manager.states["lobby"] = lambda _: 0

            if self.in_cooldown and time.time() - self.cooldown_start_time >= self.cooldown_duration:
                cprint("Stopping.", "#e8a838")
                break

            if time.time() - s_time >= 1:
                elapsed = time.time() - s_time
                print(f"{c / elapsed:.2f} IPS")
                s_time = time.time()
                c = 0

            frame_np, last_ft = self.window_controller.screenshot_numpy()

            if last_ft > 0 and (time.time() - last_ft) > self.window_controller.FRAME_STALE_TIMEOUT:
                self.Play.window_controller.keys_up(list("wasd"))
                print("Stale frame — pausing until feed resumes")
                time.sleep(1)
                continue

            self._tick_state(frame_np)

            brawler = self.Stage_manager.brawlers_pick_data[0]["brawler"]
            if self.state == "match":
                self.Play.main(frame_np, brawler)
            c += 1

            if self.max_ips:
                target_period = 1 / self.max_ips
                work_time = time.perf_counter() - frame_start
                if work_time < target_period:
                    time.sleep(target_period - work_time)


def pyla_main(data):
    _BotSession(data).main()


all_brawlers = get_brawler_list()
update_icons()

if api_base_url != "localhost":
    update_missing_brawlers_info(all_brawlers)
    check_version()
    update_wall_model_classes()
    if not current_wall_model_is_latest():
        print("Downloading new wall detection model...")
        get_latest_wall_model_file()

App(login, SelectBrawler, pyla_main, all_brawlers, Hub).start(pyla_version, get_latest_version)

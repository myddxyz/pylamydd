import atexit
import ctypes
import math
import threading
import time
import cv2
import numpy as np
import win32gui
import win32con
import win32ui
import pyautogui
from typing import List

# New libraries
import scrcpy
from adbutils import adb

from utils import load_toml_as_dict

# --- Configuration ---
brawl_stars_width, brawl_stars_height = 1920, 1080

key_coords_dict = {
    "H": (1400, 990),
    "G": (1640, 990),
    "M": (1725, 800),
    "Q": (1740, 1000),
    "E": (1510, 880)
}

directions_xy_deltas_dict = {
    "w": (0, -150),
    "a": (-150, 0),
    "s": (0, 150),
    "d": (150, 0),
}

BRAWL_STARS_PACKAGE = "com.supercell.brawlstars"


class WindowController:
    def __init__(self):
        self.scale_factor = None
        self.width = None
        self.height = None
        self.width_ratio = None
        self.height_ratio = None
        self.joystick_x, self.joystick_y = None, None
        # --- 2. ADB & Scrcpy Connection ---
        print("Connecting to ADB...")
        try:
            # Connect to device (adbutils automatically handles port detection mostly)
            # but adbutils is usually smarter at finding the open device.
            device_list = adb.device_list()
            if not device_list:
                # Try connecting to common ports if empty
                for port in [5555, load_toml_as_dict("cfg/general_config.toml")["emulator_port"], 16384, 5635] + list(range(5565, 5756, 10)):
                    try:
                         adb.connect(f"127.0.0.1:{port}")
                    except Exception:
                         pass
                device_list = adb.device_list()

            if not device_list:
                 raise ConnectionError("No ADB devices found.")

            self.device = device_list[0]
            print(f"Connected to device: {self.device.serial}")

            self.frame_lock = threading.Lock()
            self.scrcpy_client = scrcpy.Client(device=self.device, max_width=0)
            self.last_frame = None
            self.last_frame_time = 0.0
            self.last_joystick_pos = (None, None)
            self.FRAME_STALE_TIMEOUT = 5.0

            def on_frame(frame):
                if frame is not None:
                    with self.frame_lock:
                        self.last_frame = frame
                        self.last_frame_time = time.time()

            self.scrcpy_client.add_listener(scrcpy.EVENT_FRAME, on_frame)
            self.scrcpy_client.start(threaded=True)
            atexit.register(self.close)
            print("Scrcpy client started successfully.")

        except Exception as e:
            raise ConnectionError(f"Failed to initialize Scrcpy: {e}")
        self.are_we_moving = False
        self.PID_JOYSTICK = 1  # ID for WASD movement
        self.PID_ATTACK = 2  # ID for clicks/attacks
        self.check_if_brawl_stars_crashed_timer = load_toml_as_dict("cfg/time_tresholds.toml")["check_if_brawl_stars_crashed"]
        self.time_since_checked_if_brawl_stars_crashed = time.time()

    def get_latest_frame(self):
        with self.frame_lock:
            if self.last_frame is None:
                return None, 0.0
            return self.last_frame.copy(), self.last_frame_time

    def _get_raw_frame(self):
        """Shared logic: check for crash, wait for first frame, init ratios."""
        c_time = time.time()
        if c_time - self.time_since_checked_if_brawl_stars_crashed > self.check_if_brawl_stars_crashed_timer:
            if self.device.app_current().package != BRAWL_STARS_PACKAGE:
                print("Brawl stars has crashed ! Restarting...")
                self.device.app_start(BRAWL_STARS_PACKAGE)
                time.sleep(3)
                self.time_since_checked_if_brawl_stars_crashed = time.time()
            else:
                self.time_since_checked_if_brawl_stars_crashed = c_time
        frame, frame_time = self.get_latest_frame()

        deadline = time.time() + 15
        while frame is None:
            if time.time() > deadline:
                raise ConnectionError(
                    "No frame received from scrcpy within 15s. "
                    "Check USB/emulator connection."
                )
            print("Waiting for first frame...")
            time.sleep(0.1)
            frame, frame_time = self.get_latest_frame()

        age = time.time() - frame_time
        if frame_time > 0 and age > self.FRAME_STALE_TIMEOUT:
            print(f"WARNING: scrcpy frame is {age:.1f}s stale -- feed may be frozen")

        if not self.width or not self.height:
            self.width = frame.shape[1]
            self.height = frame.shape[0]
            self.width_ratio = self.width / brawl_stars_width
            self.height_ratio = self.height / brawl_stars_height
            self.joystick_x, self.joystick_y = 220 * self.width_ratio, 870 * self.height_ratio
            self.scale_factor = min(self.width_ratio, self.height_ratio)

        return frame, frame_time

    def screenshot(self, array=False):
        """Return an RGB numpy array (legacy method, use screenshot_numpy() for performance)."""
        frame, _ = self._get_raw_frame()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame_rgb

    def screenshot_numpy(self):
        """Return (BGR numpy frame, frame_time) — zero conversion overhead.
        Use this in the hot game loop instead of screenshot() for max performance."""
        frame, frame_time = self._get_raw_frame()
        return frame, frame_time

    def touch_down(self, x, y, pointer_id=0):
        # We explicitly pass the pointer_id
        self.scrcpy_client.control.touch(int(x), int(y), scrcpy.ACTION_DOWN, pointer_id)

    def touch_move(self, x, y, pointer_id=0):
        self.scrcpy_client.control.touch(int(x), int(y), scrcpy.ACTION_MOVE, pointer_id)

    def touch_up(self, x, y, pointer_id=0):
        self.scrcpy_client.control.touch(int(x), int(y), scrcpy.ACTION_UP, pointer_id)

    def keys_up(self, keys: List[str]):
        if "".join(keys).lower() == "wasd":
            if self.are_we_moving:
                # Use PID_JOYSTICK so we don't lift the attack finger
                self.touch_up(self.joystick_x, self.joystick_y, pointer_id=self.PID_JOYSTICK)
                self.are_we_moving = False
                self.last_joystick_pos = (None, None)

    def keys_down(self, keys: List[str]):

        delta_x, delta_y = 0, 0
        for key in keys:
            if key in directions_xy_deltas_dict:
                dx, dy = directions_xy_deltas_dict[key]
                delta_x += dx
                delta_y += dy

        if not self.are_we_moving:
            self.touch_down(self.joystick_x, self.joystick_y, pointer_id=self.PID_JOYSTICK)
            self.are_we_moving = True
            # Immediately move joystick to target direction
            target_x = self.joystick_x + delta_x
            target_y = self.joystick_y + delta_y
            self.touch_move(target_x, target_y, pointer_id=self.PID_JOYSTICK)
            self.last_joystick_pos = (target_x, target_y)

        elif self.last_joystick_pos != (self.joystick_x + delta_x, self.joystick_y + delta_y):
            self.touch_move(self.joystick_x + delta_x, self.joystick_y + delta_y, pointer_id=self.PID_JOYSTICK)
            self.last_joystick_pos = (self.joystick_x + delta_x, self.joystick_y + delta_y)

    def click(self, x: int, y: int, delay=0.05, already_include_ratio=True, touch_up=True, touch_down=True):
        if not already_include_ratio:
            x = x * self.width_ratio
            y = y * self.height_ratio
        # Use PID_ATTACK for clicks so we don't interrupt movement
        if touch_down: self.touch_down(x, y, pointer_id=self.PID_ATTACK)
        time.sleep(delay)
        if touch_up: self.touch_up(x, y, pointer_id=self.PID_ATTACK)

    def press_key(self, key, delay=0.05, touch_up=True, touch_down=True):
        if key not in key_coords_dict:
            return
        x, y = key_coords_dict[key]
        target_x = x * self.width_ratio
        target_y = y * self.height_ratio
        self.click(target_x, target_y, delay, touch_up=touch_up, touch_down=touch_down)

    def swipe(self, start_x, start_y, end_x, end_y, duration=0.2):
        dist_x = end_x - start_x
        dist_y = end_y - start_y
        distance = math.sqrt(dist_x ** 2 + dist_y ** 2)

        if distance == 0:
            return

        step_len = 25
        steps = max(int(distance / step_len), 1)
        step_delay = duration / steps

        self.touch_down(int(start_x), int(start_y), pointer_id=self.PID_ATTACK)
        for i in range(1, steps + 1):
            t = i / steps
            cx = start_x + dist_x * t
            cy = start_y + dist_y * t
            time.sleep(step_delay)
            self.touch_move(int(cx), int(cy), pointer_id=self.PID_ATTACK)
        self.touch_up(int(end_x), int(end_y), pointer_id=self.PID_ATTACK)

    def close(self):
        if hasattr(self, 'scrcpy_client'):
            self.scrcpy_client.stop()

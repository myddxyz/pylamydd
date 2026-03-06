import json
import re
import threading
import tkinter as tk
import urllib.parse
import urllib.request
from math import ceil

import customtkinter as ctk
import pyautogui
from PIL import Image
from customtkinter import CTkImage
from utils import load_toml_as_dict, update_toml_file, save_brawler_icon, get_dpi_scale
from tkinter import filedialog

debug = load_toml_as_dict("cfg/general_config.toml")['super_debug'] == "yes"
orig_screen_width, orig_screen_height = 1920, 1080
width, height = pyautogui.size()
width_ratio = width / orig_screen_width
height_ratio = height / orig_screen_height
scale_factor = min(width_ratio, height_ratio)
scale_factor *= 96/get_dpi_scale()
pyla_version = load_toml_as_dict("./cfg/general_config.toml")['pyla_version']


def _normalize_brawler_name(raw: str) -> str:
    return re.sub(r'[^a-z0-9]', '', raw.lower())


class SelectBrawler:

    def __init__(self, data_setter, brawlers):
        self.app = ctk.CTk()

        square_size = int(75 * scale_factor)
        amount_of_rows = ceil(len(brawlers) / 8) + 1
        calculated_height = (int(145 * scale_factor) + amount_of_rows * square_size + (amount_of_rows - 1) * int(3 * scale_factor))
        necessary_height = min(calculated_height, int(750 * scale_factor))
        
        self.app.title("PYLAMYDD — Select Brawler")
        self.brawlers = brawlers

        self.app.geometry(f"{str(int(710 * scale_factor))}x{necessary_height}+{str(int(600 * scale_factor))}")
        self.data_setter = data_setter
        self.colors = {
            'gray': "#71717A",
            'red': "#E62937",
            'darker_white': '#E4E4E7',
            'dark gray': '#16161A',
            'cherry red': '#E62937',
            'ui box gray': '#09090B',
            'chess white': '#F8F9FA',
            'chess brown': '#b58863',
            'indian red': "#FF3A4A"
        }

        self.app.configure(fg_color=self.colors['ui box gray'])

        self.player_tag = load_toml_as_dict("cfg/general_config.toml").get('player_tag', "")
        self.trophies_dict = {}
        self._fetch_player_data_async()

        self.images = []
        self.brawlers_data = []
        self.farm_type = ""

        for brawler in self.brawlers:
            img_path = f"./api/assets/brawler_icons/{brawler}.png"
            try:
                img = Image.open(img_path)
            except FileNotFoundError:
                save_brawler_icon(brawler)
                img = Image.open(img_path)

            img_tk = CTkImage(img, size=(square_size, square_size))
            self.images.append((brawler, img_tk))

        self.filter_var = tk.StringVar()
        self.filter_entry = ctk.CTkEntry(
            self.app, textvariable=self.filter_var,
            placeholder_text="Type brawler name...", font=("", int(20 * scale_factor)), width=int(200 * scale_factor),
            fg_color=self.colors['ui box gray'], border_color=self.colors['cherry red'], text_color="white"
        )
        ctk.CTkLabel(self.app, text="Write brawler", font=("Inter", int(20 * scale_factor)),
                     text_color=self.colors['cherry red']).place(x=int(scale_factor * 298), y=int(scale_factor * 20))
        self.filter_entry.place(x=int(265 * scale_factor), y=int(scale_factor * 52))
        self.filter_var.trace_add("write", lambda *args: self.update_images(self.filter_var.get()))

        scroll_height = necessary_height - int(190 * scale_factor)
        self.image_frame = ctk.CTkScrollableFrame(self.app, fg_color=self.colors['ui box gray'], width=int(690 * scale_factor), height=scroll_height)
        self.image_frame.place(x=int(10 * scale_factor), y=int(100 * scale_factor))

        self.update_images("")

        ctk.CTkButton(self.app, text="Start", command=self.start_bot, fg_color=self.colors['ui box gray'],
                      text_color="white",
                      font=("Inter", int(25 * scale_factor)), border_color=self.colors['cherry red'],
                      border_width=int(2 * scale_factor)).place(x=int(315 * scale_factor), y=int((necessary_height - 60 * scale_factor)))

        ctk.CTkButton(self.app, text="Load Brawler Config", command=self.load_brawler_config,
                      fg_color=self.colors['ui box gray'],
                      text_color="white",
                      font=("Inter", int(25 * scale_factor)), border_color=self.colors['cherry red'],
                      border_width=int(2 * scale_factor)).place(x=int(10 * scale_factor),
                                                                y=int((necessary_height - 60 * scale_factor)))

        self.timer_var = tk.StringVar()
        self.timer_entry = ctk.CTkEntry(
            self.app, textvariable=self.timer_var,
            placeholder_text="Enter an amount of minutes", font=("", int(20 * scale_factor)), width=int(80 * scale_factor),
            fg_color=self.colors['ui box gray'], border_color=self.colors['cherry red'], text_color="white"
        )
        ctk.CTkLabel(self.app, text="Run for :", font=("Inter", int(22 * scale_factor)),
                     text_color="white").place(x=int(scale_factor * 430), y=int((necessary_height - 55 * scale_factor)))
        self.timer_entry.place(x=int(scale_factor * 525), y=int((necessary_height - 55 * scale_factor)))
        self.timer_var.set(load_toml_as_dict("cfg/general_config.toml")["run_for_minutes"])
        self.timer_var.trace_add("write", lambda *args: self.update_timer(self.timer_var.get()))
        ctk.CTkLabel(self.app, text="minutes", font=("Inter", int(22 * scale_factor)),
                     text_color="white").place(x=int(scale_factor * 610), y=int((necessary_height - 55 * scale_factor)))

        self.app.mainloop()

    def set_farm_type(self, value):
        self.farm_type = value

    def _fetch_player_data_async(self):
        if not self.player_tag:
            return
        thread = threading.Thread(target=self._fetch_player_data_worker, daemon=True)
        thread.start()

    def _fetch_player_data_worker(self):
        try:
            tag = self.player_tag.strip().upper()
            if not tag.startswith('#'):
                tag = '#' + tag
            tag_encoded = urllib.parse.quote(tag)
            
            # Official API URL
            url = f"https://api.brawlstars.com/v1/players/{tag_encoded}"
            
            # Load token from config
            config = load_toml_as_dict("cfg/general_config.toml")
            api_token = config.get("brawl_stars_api_token", "").strip()
            
            if not api_token:
                if debug:
                    print("Brawl Stars API Token missing from general_config.toml. Cannot fetch player trophies.")
                return

            req = urllib.request.Request(
                url, 
                headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Authorization': f'Bearer {api_token}',
                    'Accept': 'application/json'
                }
            )
            response = urllib.request.urlopen(req, timeout=8)
            data = json.loads(response.read().decode('utf-8'))
            result = {}
            if 'brawlers' in data:
                for b in data['brawlers']:
                    key = _normalize_brawler_name(b['name'])
                    result[key] = b['trophies']
            self.app.after(0, self._on_player_data_ready, result)
        except Exception as e:
            if debug:
                print(f"Brawl Stars API fetch failed: {e}")

    def _on_player_data_ready(self, result: dict):
        self.trophies_dict = result
        self.update_images(self.filter_var.get())

    def start_bot(self):
        self.data_setter(self.brawlers_data)
        self.app.destroy()

    def load_brawler_config(self):
        file_path = filedialog.askopenfilename(
            title="Select Brawler Config File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r') as file:
                    brawlers_data = json.load(file)
                    try:
                        brawlers_data = [
                            bd for bd in brawlers_data
                            if not (bd["push_until"] <= bd[bd["type"]])
                        ]
                        self.brawlers_data = brawlers_data
                        print("Brawler data loaded successfully :", brawlers_data)
                    except Exception as e:
                        print("Invalid data format. Expected a list of brawler data.", e)
            except Exception as e:
                print(f"Error loading brawler data: {e}")

    def on_image_click(self, brawler):
        self.open_brawler_entry(brawler)

    def open_brawler_entry(self, brawler):
        top = ctk.CTkToplevel(self.app)
        top.configure(fg_color=self.colors['ui box gray'])
        top.geometry(
            f"{str(int(300 * scale_factor))}x{str(int(450 * scale_factor))}+{str(int(1100 * scale_factor))}+{str(int(200 * scale_factor))}")
        top.title("Enter Brawler Data")
        top.attributes("-topmost", True)

        push_until_var = tk.StringVar()
        push_until_entry = ctk.CTkEntry(
            top, textvariable=push_until_var, fg_color=self.colors['ui box gray'], text_color="white",
            border_color=self.colors['cherry red'], border_width=int(2 * scale_factor), height=int(28 * scale_factor)
        )

        normalized = _normalize_brawler_name(brawler)
        default_trophies = self.trophies_dict.get(normalized, "")
        trophies_var = tk.StringVar(value=str(default_trophies) if default_trophies != "" else "")
        trophies_entry = ctk.CTkEntry(
            top, textvariable=trophies_var, fg_color=self.colors['ui box gray'], text_color="white",
            border_color=self.colors['cherry red'], border_width=int(2 * scale_factor), height=int(28 * scale_factor)
        )

        wins_var = tk.StringVar()
        wins_entry = ctk.CTkEntry(
            top, textvariable=wins_var, fg_color=self.colors['ui box gray'], text_color="white",
            border_color=self.colors['cherry red'], border_width=int(2 * scale_factor), height=int(28 * scale_factor)
        )

        current_win_streak_var = tk.StringVar(value="0")
        current_win_streak_entry = ctk.CTkEntry(
            top, textvariable=current_win_streak_var, fg_color=self.colors['ui box gray'], text_color="white",
            border_color=self.colors['cherry red'], border_width=int(2 * scale_factor), height=int(28 * scale_factor)
        )

        auto_pick_var = tk.BooleanVar(value=True)
        auto_pick_checkbox = ctk.CTkCheckBox(
            top, text="Bot auto-selects brawler", variable=auto_pick_var,
            fg_color=self.colors['cherry red'], text_color="white", checkbox_height=int(24 * scale_factor)
        )

        def submit_data():
            push_until_value = push_until_var.get()
            push_until_value = int(push_until_value) if push_until_value.isdigit() else ""
            trophies_raw = trophies_var.get()
            trophies_value = int(trophies_raw) if trophies_raw.isdigit() else 0
            wins_value = wins_var.get()
            wins_value = int(wins_value) if wins_value.isdigit() else ""
            current_win_streak_value = current_win_streak_var.get()
            if self.farm_type == "trophies" and wins_value == "":
                wins_value = 0
            data = {
                "brawler": brawler,
                "push_until": push_until_value,
                "trophies": trophies_value,
                "wins": wins_value,
                "type": self.farm_type,
                "automatically_pick": auto_pick_var.get(),
                "win_streak": int(current_win_streak_value) if str(current_win_streak_value).isdigit() else 0
            }

            if data["type"] == "":
                if data["trophies"] <= data["wins"]:
                    data["type"] = "trophies"
                else:
                    data["type"] = "wins"

            self.brawlers_data = [item for item in self.brawlers_data if item["brawler"] != data["brawler"]]
            self.brawlers_data.append(data)

            if debug:
                print("Selected Brawler Data :", self.brawlers_data)
            top.destroy()

        submit_button = ctk.CTkButton(
            top, text="Submit", command=submit_data, fg_color=self.colors['ui box gray'],
            border_color=self.colors['cherry red'],
            text_color="white", border_width=int(2 * scale_factor), width=int(80 * scale_factor)
        )

        farm_type_button_frame = ctk.CTkFrame(top, width=int(210 * scale_factor), height=int(50 * scale_factor),
                                              fg_color=self.colors['ui box gray'])

        self.wins_button = ctk.CTkButton(farm_type_button_frame, text="Win Amount", width=int(90 * scale_factor),
                                         command=lambda: self.set_farm_type_color("wins"),
                                         hover_color=self.colors['cherry red'],
                                         font=("", int(15 * scale_factor)),
                                         fg_color=self.colors["ui box gray"],
                                         border_color=self.colors['cherry red'],
                                         border_width=int(2 * scale_factor))
        self.trophies_button = ctk.CTkButton(farm_type_button_frame, text="Trophies", width=int(85 * scale_factor),
                                             command=lambda: self.set_farm_type_color("trophies"),
                                             hover_color=self.colors['cherry red'],
                                             font=("", int(15 * scale_factor)),
                                             fg_color=self.colors["ui box gray"],
                                             border_color=self.colors['cherry red'],
                                             border_width=int(2 * scale_factor))

        self.trophies_button.place(x=int(10 * scale_factor))
        self.wins_button.place(x=int(110 * scale_factor))

        ctk.CTkLabel(top, text=f"Brawler: {brawler}", font=("Inter", int(20 * scale_factor)),
                     text_color=self.colors['red']).pack(pady=int(7 * scale_factor))
        farm_type_button_frame.pack()
        ctk.CTkLabel(top, text="Target Amount", font=("Inter", int(15 * scale_factor)),
                     text_color=self.colors['chess white']).pack()
        push_until_entry.pack(pady=int(4 * scale_factor))
        ctk.CTkLabel(top, text="Current Trophies", font=("Inter", int(15 * scale_factor)),
                     text_color=self.colors['chess white']).pack()
        trophies_entry.pack(pady=int(4 * scale_factor))
        ctk.CTkLabel(top, text="Current Wins", font=("Inter", int(15 * scale_factor)),
                     text_color=self.colors['chess white']).pack()
        wins_entry.pack(pady=int(4 * scale_factor))
        ctk.CTkLabel(top, text="Current Brawler's Win Streak", font=("Inter", int(15 * scale_factor)),
                     text_color=self.colors['chess white']).pack()
        current_win_streak_entry.pack(pady=int(4 * scale_factor))
        auto_pick_checkbox.pack(pady=int(4 * scale_factor))
        submit_button.pack(pady=int(7 * scale_factor))

    def set_farm_type_color(self, value):
        self.farm_type = value
        if value == "wins":
            self.wins_button.configure(fg_color=self.colors['cherry red'])
            self.trophies_button.configure(fg_color=self.colors['ui box gray'])
        else:
            self.wins_button.configure(fg_color=self.colors['ui box gray'])
            self.trophies_button.configure(fg_color=self.colors['cherry red'])

    def update_images(self, filter_text):
        if hasattr(self, 'current_brawler_widgets'):
            for widget in self.current_brawler_widgets:
                widget.destroy()
        self.current_brawler_widgets = []

        row_num = 0
        col_num = 0

        for brawler, img_tk in self.images:
            if brawler.startswith(filter_text.lower()):
                normalized = _normalize_brawler_name(brawler)
                trophy_count = self.trophies_dict.get(normalized)
                text = f"🏆 {trophy_count}" if trophy_count is not None else ""

                label = ctk.CTkLabel(
                    self.image_frame, image=img_tk, text=text,
                    font=("Inter", int(12 * scale_factor), "bold"),
                    text_color="#FFD700", compound="top"
                )
                label.bind("<Button-1>", lambda e, b=brawler: self.on_image_click(b))
                label.grid(row=row_num, column=col_num, padx=int(5 * scale_factor), pady=int(3 * scale_factor))
                self.current_brawler_widgets.append(label)

                col_num += 1
                if col_num == 8:
                    col_num = 0
                    row_num += 1

    def update_timer(self, value):
        try:
            minutes = int(value)
            config = load_toml_as_dict("cfg/general_config.toml")
            config['run_for_minutes'] = minutes
            update_toml_file("cfg/general_config.toml", config)
        except ValueError:
            pass


def dummy_data_setter(data):
    print("Data set:", data)

import sys
import customtkinter as ctk
import webbrowser
import os
import pyautogui
from PIL import Image
import tkinter as tk
import bettercam
from utils import load_toml_as_dict, save_dict_as_toml, get_discord_link, get_dpi_scale
from packaging import version

orig_screen_width, orig_screen_height = 1920, 1080
width, height = pyautogui.size()
width_ratio = width / orig_screen_width
height_ratio = height / orig_screen_height
scale_factor = min(width_ratio, height_ratio)
scale_factor *= 96/get_dpi_scale()

def S(value):
    return int(value * scale_factor)

BG          = "#0D0D0D"
SIDEBAR_BG  = "#111111"
PANEL_BG    = "#161616"
CARD_BG     = "#1E1E1E"
HEADER_BG   = "#131313"
FOOTER_BG   = "#131313"
ACCENT      = "#C80000"
ACCENT_HVR  = "#E61A1A"
BTN_OFF     = "#2A2A2A"
BTN_HVR     = "#3A3A3A"
TEXT_PRI    = "#FFFFFF"
TEXT_SEC    = "#888888"
TEXT_DIM    = "#555555"
DIVIDER     = "#2A2A2A"
SECTION_HDR = "#C80000"
GREEN       = "#2ecc71"
GOLD        = "#FFD700"


class Hub:

    def __init__(self, version_str, latest_version_str,
                 correct_zoom=True, on_close_callback=None):

        self.version_str = version_str
        self.latest_version_str = latest_version_str
        self.correct_zoom = correct_zoom
        self.on_close_callback = on_close_callback

        self.bot_config_path = "cfg/bot_config.toml"
        self.time_tresholds_path = "cfg/time_tresholds.toml"
        self.match_history_path = "cfg/match_history.toml"
        self.general_config_path = "cfg/general_config.toml"

        self.bot_config = load_toml_as_dict(self.bot_config_path)
        self.time_tresholds = load_toml_as_dict(self.time_tresholds_path)
        self.match_history = load_toml_as_dict(self.match_history_path)
        self.general_config = load_toml_as_dict(self.general_config_path)

        self.bot_config.setdefault("gamemode_type", 3)
        self.bot_config.setdefault("gamemode", "brawlball")
        self.bot_config.setdefault("bot_uses_gadgets", "yes")
        self.bot_config.setdefault("minimum_movement_delay", 0.4)
        self.bot_config.setdefault("wall_detection_confidence", 0.9)
        self.bot_config.setdefault("entity_detection_confidence", 0.6)
        self.bot_config.setdefault("unstuck_movement_delay", 3.0)
        self.bot_config.setdefault("unstuck_movement_hold_time", 1.5)

        self.time_tresholds.setdefault("state_check", 3)
        self.time_tresholds.setdefault("no_detections", 10)
        self.time_tresholds.setdefault("idle", 10)
        self.time_tresholds.setdefault("super", 0.1)
        self.time_tresholds.setdefault("gadget", 0.5)
        self.time_tresholds.setdefault("hypercharge", 2)

        self.general_config.setdefault("max_ips", "auto")
        self.general_config.setdefault("super_debug", "yes")
        self.general_config.setdefault("cpu_or_gpu", "auto")
        self.general_config.setdefault("long_press_star_drop", "no")
        self.general_config.setdefault("trophies_multiplier", 1.0)
        self.general_config.setdefault("current_emulator", "LDPlayer")
        self.general_config.setdefault("player_tag", "")

        ctk.set_appearance_mode("dark")

        self.tooltip_window = None
        self._tooltip_after_id = None
        self._tooltip_owner = None
        self._tooltip_text = ""
        self._player_tag_after_id = None

        self.app = ctk.CTk()
        self.app.title("PYLAMYDD CONTROL CENTER")
        self.app.geometry(f"{S(1020)}x{S(700)}")
        self.app.resizable(False, False)
        self.app.configure(fg_color=BG)

        for seq in ("<ButtonPress>", "<MouseWheel>", "<KeyPress>", "<FocusOut>"):
            self.app.bind_all(seq, self._hide_tooltip, add="+")
        self.app.bind("<Configure>", self._hide_tooltip, add="+")

        self._build_header()
        self._build_footer()
        self._build_sidebar()
        self._build_content_area()

        self.panels = {}
        self._build_dashboard_panel()
        self._build_settings_panel()

        self._show_panel("dashboard")
        self._set_active_sidebar(0)

        self.app.mainloop()

    def _build_header(self):
        header = ctk.CTkFrame(self.app, fg_color=HEADER_BG, height=S(40), corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        logo_frame = ctk.CTkFrame(header, fg_color="transparent")
        logo_frame.pack(side="left", padx=S(12))
        ctk.CTkLabel(logo_frame, text="PYLAMYDD", font=("Arial", S(16), "bold"),
                     text_color=TEXT_PRI).pack(side="top")
        ctk.CTkFrame(logo_frame, fg_color=ACCENT, height=S(3),
                     width=S(60), corner_radius=0).pack(side="top")

        ctk.CTkLabel(header, text="CONTROL CENTER",
                     font=("Arial", S(12)), text_color=TEXT_SEC
                     ).pack(side="left", padx=S(10))

        badge = ctk.CTkFrame(header, fg_color="#1E1E1E", corner_radius=S(12),
                             border_width=1, border_color="#333333")
        badge.pack(side="right", padx=S(15))
        ctk.CTkLabel(badge, text="  ● IDLE  ", font=("Arial", S(10)),
                     text_color=TEXT_SEC).pack(padx=S(4), pady=S(2))

    def _build_footer(self):
        footer = ctk.CTkFrame(self.app, fg_color=FOOTER_BG, height=S(28), corner_radius=0)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        ctk.CTkLabel(footer, text="●  DISCONNECTED", font=("Arial", S(9)),
                     text_color=GOLD).pack(side="left", padx=S(12))
        ctk.CTkLabel(footer, text=f"STABLE {self.version_str}",
                     font=("Arial", S(9)), text_color=TEXT_DIM
                     ).pack(side="right", padx=S(12))

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self.app, fg_color=SIDEBAR_BG, width=S(58),
                                    corner_radius=0)
        self.sidebar.pack(fill="y", side="left")
        self.sidebar.pack_propagate(False)

        icons = [
            ("🏠", "dashboard"),
            ("⚙", "settings"),
        ]

        self.sidebar_btns = []
        self.sidebar_indicators = []

        for i, (icon, panel_key) in enumerate(icons):
            frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            frame.pack(pady=(S(10) if i == 0 else S(3)))

            indicator = ctk.CTkFrame(frame, fg_color="transparent",
                                     width=S(3), height=S(36), corner_radius=0)
            indicator.pack(side="left")

            btn = ctk.CTkButton(
                frame, text=icon, width=S(42), height=S(42),
                fg_color="transparent", hover_color=BTN_HVR,
                font=("Arial", S(18)),
                command=lambda pk=panel_key, idx=i: self._on_sidebar_click(pk, idx),
                corner_radius=S(6)
            )
            btn.pack(side="left", padx=S(2))

            self.sidebar_btns.append(btn)
            self.sidebar_indicators.append(indicator)

        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="y", expand=True)

        discord_link = get_discord_link()
        discord_btn = ctk.CTkButton(
            self.sidebar, text="💬", width=S(42), height=S(42),
            fg_color="transparent", hover_color=BTN_HVR,
            font=("Arial", S(18)),
            command=lambda: webbrowser.open(discord_link),
            corner_radius=S(6)
        )
        discord_btn.pack(side="bottom", pady=S(10))

        ctk.CTkLabel(self.sidebar, text=f"v{self.version_str}",
                     font=("Arial", S(8)), text_color=TEXT_DIM
                     ).pack(side="bottom", pady=S(2))

    def _on_sidebar_click(self, panel_key, idx):
        self._show_panel(panel_key)
        self._set_active_sidebar(idx)

    def _set_active_sidebar(self, active_idx):
        for i, (btn, indicator) in enumerate(zip(self.sidebar_btns, self.sidebar_indicators)):
            if i == active_idx:
                btn.configure(fg_color=CARD_BG)
                indicator.configure(fg_color=ACCENT)
            else:
                btn.configure(fg_color="transparent")
                indicator.configure(fg_color="transparent")

    def _build_content_area(self):
        self.content = ctk.CTkFrame(self.app, fg_color=PANEL_BG, corner_radius=S(10))
        self.content.pack(fill="both", expand=True, padx=S(6), pady=S(6))

    def _show_panel(self, panel_key):
        for key, frame in self.panels.items():
            frame.pack_forget()
        if panel_key in self.panels:
            self.panels[panel_key].pack(fill="both", expand=True)

    def _section_header(self, parent, text):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=S(25), pady=(S(18), S(6)))
        ctk.CTkLabel(frame, text=text.upper(), font=("Arial", S(11), "bold"),
                     text_color=SECTION_HDR).pack(side="left")
        ctk.CTkFrame(frame, fg_color=DIVIDER, height=1).pack(
            side="left", fill="x", expand=True, padx=S(10))
        return frame

    def _toggle_btn(self, parent, values, current, callback):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        btns = []
        for val, label, disabled in values:
            btn = ctk.CTkButton(
                frame, text=label, width=S(140), height=S(38),
                font=("Arial", S(13), "bold"), corner_radius=S(6),
                fg_color=ACCENT if val == current else BTN_OFF,
                hover_color=ACCENT_HVR if val == current else BTN_HVR,
                text_color=TEXT_PRI if not disabled else TEXT_DIM,
                state="disabled" if disabled else "normal",
                command=lambda v=val: callback(v)
            )
            btn.pack(side="left", padx=S(5))
            btns.append((val, btn))

        def refresh(selected):
            for v, b in btns:
                if v == selected:
                    b.configure(fg_color=ACCENT, hover_color=ACCENT_HVR)
                else:
                    b.configure(fg_color=BTN_OFF, hover_color=BTN_HVR)

        return frame, refresh

    def _build_dashboard_panel(self):
        panel = ctk.CTkScrollableFrame(self.content, fg_color="transparent",
                                       corner_radius=0)
        self.panels["dashboard"] = panel

        w_list = []
        if not self.correct_zoom:
            w_list.append("⚠  Windows zoom isn't 100% (DPI ≠ 96)")
        if self.latest_version_str and version.parse(self.version_str) < version.parse(self.latest_version_str):
            w_list.append(f"⚠  Update available: {self.latest_version_str}")

        if w_list:
            for w in w_list:
                ctk.CTkLabel(panel, text=w, text_color="#e74c3c",
                             font=("Arial", S(13), "bold")).pack(pady=S(3))

        self._section_header(panel, "MAP ORIENTATION")

        self.gamemode_type_var = tk.IntVar(value=self.bot_config["gamemode_type"])

        def on_orient(val):
            self.gamemode_type_var.set(val)
            self.orient_refresh(val)
            self._refresh_gm_frames()

        orient_frame, self.orient_refresh = self._toggle_btn(
            panel,
            [(3, "Vertical", False), (5, "Horizontal", False)],
            self.bot_config["gamemode_type"],
            on_orient
        )
        orient_frame.pack(pady=S(6))

        self._section_header(panel, "GAMEMODE SELECTION")

        self.gamemode_var = tk.StringVar(value=self.bot_config["gamemode"])

        self.gm3_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.gm5_frame = ctk.CTkFrame(panel, fg_color="transparent")

        def on_gm(val, orient):
            self.bot_config["gamemode_type"] = orient
            self.bot_config["gamemode"] = val
            save_dict_as_toml(self.bot_config, self.bot_config_path)
            self.gamemode_type_var.set(orient)
            self.gamemode_var.set(val)
            self.orient_refresh(orient)
            self.gm3_refresh(val)
            self.gm5_refresh(val)
            self._refresh_gm_frames()

        gm3_inner, self.gm3_refresh = self._toggle_btn(
            self.gm3_frame,
            [("brawlball", "Brawlball", False),
             ("showdown", "Showdown", True),
             ("other", "Other", False)],
            self.bot_config["gamemode"],
            lambda v: on_gm(v, 3)
        )
        gm3_inner.pack()

        gm5_inner, self.gm5_refresh = self._toggle_btn(
            self.gm5_frame,
            [("basketbrawl", "Basket Brawl", False),
             ("brawlball_5v5", "Brawlball 5v5", False)],
            self.bot_config["gamemode"],
            lambda v: on_gm(v, 5)
        )
        gm5_inner.pack()

        self._refresh_gm_frames()

        self._section_header(panel, "EMULATOR TARGET")

        self.emu_var = tk.StringVar(value=self.general_config["current_emulator"])

        def on_emu(val):
            self.emu_var.set(val)
            self.general_config["current_emulator"] = val
            save_dict_as_toml(self.general_config, self.general_config_path)
            self.emu_refresh(val)

        emu_frame, self.emu_refresh = self._toggle_btn(
            panel,
            [("LDPlayer", "LDPlayer", False),
             ("BlueStacks", "BlueStacks", False),
             ("MEmu", "MEmu", False),
             ("Others", "Others", False)],
            self.general_config["current_emulator"],
            on_emu
        )
        emu_frame.pack(pady=S(6))

        start_btn = ctk.CTkButton(
            panel, text="▶  START", width=S(260), height=S(52),
            fg_color=ACCENT, hover_color=ACCENT_HVR,
            font=("Arial", S(18), "bold"), corner_radius=S(8),
            command=self._on_start
        )
        start_btn.pack(pady=S(25))

        foot = ctk.CTkFrame(panel, fg_color="transparent")
        foot.pack(pady=S(5))
        ctk.CTkLabel(foot, text="Pyla is free and public.  ›  ",
                     font=("Arial", S(11)), text_color=TEXT_DIM).pack(side="left")
        discord_link = get_discord_link()
        link = ctk.CTkLabel(foot, text="Join Community", font=("Arial", S(11)),
                            text_color="#5865F2", cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open(discord_link))

    def _refresh_gm_frames(self):
        self.gm3_frame.pack_forget()
        self.gm5_frame.pack_forget()
        if self.gamemode_type_var.get() == 3:
            self.gm3_frame.pack(pady=S(6))
        else:
            self.gm5_frame.pack(pady=S(6))

    def _build_settings_panel(self):
        panel = ctk.CTkFrame(self.content, fg_color="transparent", corner_radius=0)
        self.panels["settings"] = panel

        settings_sidebar = ctk.CTkFrame(panel, fg_color=CARD_BG, width=S(160),
                                        corner_radius=0)
        settings_sidebar.pack(fill="y", side="left", padx=0)
        settings_sidebar.pack_propagate(False)

        ctk.CTkLabel(settings_sidebar, text="SETTINGS",
                     font=("Arial", S(11), "bold"), text_color=SECTION_HDR
                     ).pack(anchor="w", padx=S(15), pady=(S(15), S(8)))

        sub_pages = {}
        sub_btns = []

        def show_sub(key, idx):
            for k, f in sub_pages.items():
                f.pack_forget()
            if key in sub_pages:
                sub_pages[key].pack(fill="both", expand=True)
            for j, b in enumerate(sub_btns):
                if j == idx:
                    b.configure(fg_color=BTN_OFF)
                else:
                    b.configure(fg_color="transparent")

        items = [("General", "general"), ("Timers", "timers"), ("Match History", "history")]
        for i, (label, key) in enumerate(items):
            btn = ctk.CTkButton(
                settings_sidebar, text=f"  {label}", anchor="w",
                fg_color="transparent", hover_color=BTN_HVR,
                text_color=TEXT_PRI, font=("Arial", S(12)),
                width=S(140), height=S(32), corner_radius=S(4),
                command=lambda k=key, idx=i: show_sub(k, idx)
            )
            btn.pack(padx=S(8), pady=S(2))
            sub_btns.append(btn)

        settings_content = ctk.CTkFrame(panel, fg_color="transparent")
        settings_content.pack(fill="both", expand=True)

        general = ctk.CTkScrollableFrame(settings_content, fg_color="transparent")
        sub_pages["general"] = general

        self._section_header(general, "ACCOUNT")
        self._setting_row_player_tag(general)
        self._setting_row(general, "Official API Token", "brawl_stars_api_token",
                         str, "Your API token from developer.brawlstars.com for auto-fetching trophies.", True)

        self._section_header(general, "DETECTION")
        self._setting_row(general, "Minimum Movement Delay", "minimum_movement_delay",
                         float, "How long the bot maintains a movement before changing it.", False)
        self._setting_row(general, "Wall Detection Confidence", "wall_detection_confidence",
                         float, "0-1 scale: how sure must the bot be to detect a wall.", False)
        self._setting_row(general, "Entity Detection Confidence", "entity_detection_confidence",
                         float, "0-1 scale: how sure to detect player/enemies/allies.", False)

        self._section_header(general, "UNSTUCK")
        self._setting_row(general, "Unstuck Movement Delay", "unstuck_movement_delay",
                         float, "How long before trying to unstick.", False)
        self._setting_row(general, "Unstuck Duration", "unstuck_movement_hold_time",
                         float, "How long the bot tries a different direction.", False)

        self._section_header(general, "PERFORMANCE")

        perf_frame = ctk.CTkFrame(general, fg_color="transparent")
        perf_frame.pack(fill="x", padx=S(25), pady=S(6))
        ctk.CTkLabel(perf_frame, text="Hardware Acceleration",
                     font=("Arial", S(13), "bold"), text_color=TEXT_PRI).pack(side="left")
        ctk.CTkLabel(perf_frame, text="Use GPU for smoother processing.",
                     font=("Arial", S(10)), text_color=TEXT_SEC).pack(side="left", padx=S(10))

        gpu_var = tk.StringVar(value=self.general_config["cpu_or_gpu"])
        gpu_switch = ctk.CTkSwitch(
            perf_frame, text="", variable=gpu_var,
            onvalue="auto", offvalue="cpu",
            progress_color=ACCENT, button_color=TEXT_PRI,
            command=lambda: self._save_general("cpu_or_gpu", gpu_var.get())
        )
        gpu_switch.pack(side="right")
        if gpu_var.get() == "auto":
            gpu_switch.select()

        self._section_header(general, "THRESHOLDS")
        self._setting_row(general, "Super Detection Pixels", "super_pixels_minimum",
                         float, "Yellow pixels needed to detect super ready.", False)
        self._setting_row(general, "Gadget Detection Pixels", "gadget_pixels_minimum",
                         float, "Green pixels needed to detect gadget ready.", False)
        self._setting_row(general, "Hypercharge Detection Pixels", "hypercharge_pixels_minimum",
                         float, "Purple pixels needed to detect hypercharge ready.", False)
        self._setting_row(general, "Max IPS", "max_ips",
                         lambda s: s if s.lower() == "auto" else int(s),
                         "'auto' or integer. Max images per second.", True)
        self._setting_row(general, "Trophies Multiplier", "trophies_multiplier",
                         int, "Set to 2 for Brawl Arena etc.", True)

        timers = ctk.CTkScrollableFrame(settings_content, fg_color="transparent")
        sub_pages["timers"] = timers

        self._section_header(timers, "TIMER SETTINGS")

        timer_configs = [
            ("super", "Super Check Delay", "How often the bot checks if super is ready."),
            ("hypercharge", "Hypercharge Check Delay", "How often the bot checks hypercharge."),
            ("gadget", "Gadget Check Delay", "How often the bot checks gadget."),
            ("wall_detection", "Wall Detection Delay", "How often the bot detects walls."),
            ("no_detection_proceed", "No Detection Proceed", "How often to press Q when player not found."),
        ]
        for param, label, tip in timer_configs:
            self._timer_row(timers, param, label, tip)

        history = ctk.CTkScrollableFrame(settings_content, fg_color="transparent")
        sub_pages["history"] = history
        self._section_header(history, "MATCH HISTORY")
        self._build_history_content(history)

        show_sub("general", 0)

    def _save_general(self, key, value):
        self.general_config[key] = value
        save_dict_as_toml(self.general_config, self.general_config_path)

    def _setting_row_player_tag(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=S(25), pady=S(4))

        ctk.CTkLabel(row, text="Player Tag (#...)", font=("Arial", S(12)),
                     text_color=TEXT_PRI).pack(side="left")

        raw = self.general_config.get("player_tag", "")
        var = tk.StringVar(value=str(raw) if raw is not None else "")

        def _schedule_save(*_):
            if self._player_tag_after_id is not None:
                try:
                    self.app.after_cancel(self._player_tag_after_id)
                except Exception:
                    pass
            self._player_tag_after_id = self.app.after(600, _do_save)

        def _do_save():
            self._player_tag_after_id = None
            v = var.get().strip()
            self.general_config["player_tag"] = v
            save_dict_as_toml(self.general_config, self.general_config_path)

        var.trace_add("write", _schedule_save)

        entry = ctk.CTkEntry(row, textvariable=var, width=S(140),
                             font=("Arial", S(12)), fg_color=CARD_BG,
                             border_color=DIVIDER)
        entry.pack(side="right", padx=S(5))
        entry.bind("<FocusOut>", lambda _: _do_save())
        entry.bind("<Return>", lambda _: _do_save())

        self.attach_tooltip(
            entry,
            "Your Brawl Stars player tag. Used to automatically fetch current brawler trophies."
        )

    def _setting_row(self, parent, label, config_key, convert_func, tooltip,
                     use_general=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=S(25), pady=S(4))

        cfg = self.general_config if use_general else self.bot_config
        path = self.general_config_path if use_general else self.bot_config_path

        ctk.CTkLabel(row, text=label, font=("Arial", S(12)),
                     text_color=TEXT_PRI).pack(side="left")

        raw = cfg.get(config_key, "")
        var = tk.StringVar(value=str(raw) if raw is not None else "")

        def save(*_):
            v = var.get().strip()
            try:
                cfg[config_key] = convert_func(v)
                save_dict_as_toml(cfg, path)
            except (ValueError, TypeError):
                pass

        var.trace_add("write", save)

        entry = ctk.CTkEntry(row, textvariable=var, width=S(90),
                             font=("Arial", S(12)), fg_color=CARD_BG,
                             border_color=DIVIDER)
        entry.pack(side="right", padx=S(5))
        entry.bind("<FocusOut>", save)
        entry.bind("<Return>", save)

        if tooltip:
            self.attach_tooltip(entry, tooltip)

    def _timer_row(self, parent, param, label, tooltip):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=S(25), pady=S(6))

        ctk.CTkLabel(row, text=label, font=("Arial", S(12)),
                     text_color=TEXT_PRI).pack(side="left")

        val_var = tk.StringVar(value=str(self.time_tresholds.get(param, 1.0)))

        entry = ctk.CTkEntry(row, textvariable=val_var, width=S(60),
                             font=("Arial", S(11)), fg_color=CARD_BG,
                             border_color=DIVIDER)
        entry.pack(side="right", padx=S(5))

        sld = ctk.CTkSlider(
            row, from_=0.1, to=10, number_of_steps=99, width=S(180),
            progress_color=ACCENT, button_color=TEXT_PRI,
            command=lambda v: self._on_timer_slide(v, val_var, param)
        )
        sld.pack(side="right", padx=S(5))

        try:
            init = float(self.time_tresholds.get(param, 1.0))
            sld.set(max(0.1, min(10, init)))
        except Exception:
            sld.set(1.0)

        def on_entry_save(_=None):
            try:
                val = float(val_var.get().strip())
                self.time_tresholds[param] = val
                save_dict_as_toml(self.time_tresholds, self.time_tresholds_path)
                sld.set(max(0.1, min(10, val)))
            except ValueError:
                val_var.set(str(self.time_tresholds.get(param, 1.0)))

        entry.bind("<FocusOut>", on_entry_save)
        entry.bind("<Return>", on_entry_save)

        if tooltip:
            self.attach_tooltip(sld, tooltip)
            self.attach_tooltip(entry, tooltip)

    def _on_timer_slide(self, value, var, param):
        v = float(value)
        var.set(f"{v:.2f}")
        self.time_tresholds[param] = v
        save_dict_as_toml(self.time_tresholds, self.time_tresholds_path)

    def _build_history_content(self, parent):
        max_cols = 4
        row_idx = 0
        col_idx = 0
        icon_size = S(80)

        grid_frame = ctk.CTkFrame(parent, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=S(10), pady=S(5))

        for brawler, stats in self.match_history.items():
            if brawler == "total":
                continue
            icon_path = f"./api/assets/brawler_icons/{brawler}.png"
            icon_img = None
            if os.path.exists(icon_path):
                pil_img = Image.open(icon_path).resize((icon_size, icon_size))
                icon_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img,
                                        size=(icon_size, icon_size))

            total = stats["victory"] + stats["defeat"]
            wr = round(100 * stats["victory"] / total, 1) if total else 0
            lr = round(100 * stats["defeat"] / total, 1) if total else 0

            cell = ctk.CTkFrame(grid_frame, fg_color=CARD_BG, corner_radius=S(8),
                                width=S(160), height=S(180))
            cell.grid(row=row_idx, column=col_idx, padx=S(8), pady=S(8))

            if icon_img:
                ctk.CTkLabel(cell, image=icon_img, text="").pack(pady=S(4))

            ctk.CTkLabel(cell, text=f"{brawler}\n{total} games",
                         font=("Arial", S(12), "bold"),
                         text_color=TEXT_PRI).pack()

            stats_f = ctk.CTkFrame(cell, fg_color="transparent")
            stats_f.pack(pady=S(3))
            ctk.CTkLabel(stats_f, text=f"{wr}%", font=("Arial", S(11), "bold"),
                         text_color=GREEN).pack(side="left", padx=S(3))
            ctk.CTkLabel(stats_f, text=f"{lr}%", font=("Arial", S(11), "bold"),
                         text_color="#e74c3c").pack(side="left", padx=S(3))

            col_idx += 1
            if col_idx >= max_cols:
                col_idx = 0
                row_idx += 1

    def _pointer_over_widget(self, widget) -> bool:
        if widget is None or not widget.winfo_exists():
            return False
        try:
            px, py = widget.winfo_pointerx(), widget.winfo_rooty()
            x, y = widget.winfo_rootx(), widget.winfo_rooty()
            w, h = widget.winfo_width(), widget.winfo_height()
            return x <= px <= x + w and y <= py <= y + h
        except tk.TclError:
            return False

    def _hide_tooltip(self, _event=None):
        if self._tooltip_after_id is not None:
            try:
                self.app.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = None
        if self.tooltip_window is not None:
            try:
                self.tooltip_window.destroy()
            except Exception:
                pass
            self.tooltip_window = None
        self._tooltip_owner = None
        self._tooltip_text = ""

    def attach_tooltip(self, widget, text, delay_ms: int = 250):
        def schedule_show(event=None):
            self._hide_tooltip()
            self._tooltip_owner = widget
            self._tooltip_text = text

            def do_show():
                if (self._tooltip_owner is None
                        or not self._tooltip_owner.winfo_exists()
                        or not self._tooltip_owner.winfo_viewable()
                        or not self._pointer_over_widget(self._tooltip_owner)):
                    self._hide_tooltip()
                    return
                self.tooltip_window = ctk.CTkToplevel(self.app)
                self.tooltip_window.overrideredirect(True)
                self.tooltip_window.attributes("-topmost", True)
                px = self.app.winfo_pointerx()
                py = self.app.winfo_pointery()
                self.tooltip_window.geometry(f"+{px + 12}+{py + 12}")
                label = ctk.CTkLabel(
                    self.tooltip_window, text=self._tooltip_text,
                    fg_color=CARD_BG, text_color=TEXT_PRI,
                    corner_radius=S(6), font=("Arial", S(11))
                )
                label.pack(padx=S(6), pady=S(4))
                self.tooltip_window.bind("<Enter>", self._hide_tooltip)
                self.tooltip_window.bind("<Leave>", self._hide_tooltip)

            self._tooltip_after_id = self.app.after(delay_ms, do_show)

        def on_leave(_=None):
            self._hide_tooltip()

        widget.bind("<Enter>", schedule_show, add="+")
        widget.bind("<Leave>", on_leave, add="+")
        widget.bind("<Unmap>", on_leave, add="+")
        widget.bind("<Destroy>", on_leave, add="+")
        widget.bind("<ButtonPress>", on_leave, add="+")

    def _on_start(self):
        sys.stdout.flush()
        o_out, o_err = sys.stdout, sys.stderr
        fd_out, fd_err = o_out.fileno(), o_err.fileno()
        saved_out, saved_err = os.dup(fd_out), os.dup(fd_err)
        dn = os.open(os.devnull, os.O_RDWR)
        os.dup2(dn, fd_out); os.dup2(dn, fd_err); os.close(dn)

        tkint = getattr(getattr(self, 'app', None), 'tk', None)
        renamed = False
        if tkint:
            try:
                if tkint.eval('info procs ::bgerror'):
                    tkint.eval('rename ::bgerror ::_old_bgerr'); renamed = True
                tkint.eval('proc ::bgerror args {}')
            except tk.TclError:
                pass

        try: self.app.destroy()
        except Exception: pass
        os.dup2(saved_out, fd_out); os.dup2(saved_err, fd_err)
        os.close(saved_out); os.close(saved_err)
        sys.stdout, sys.stderr = o_out, o_err

        if tkint:
            try:
                tkint.eval('rename ::bgerror {}')
                if renamed: tkint.eval('rename ::_old_bgerr ::bgerror')
            except tk.TclError: pass

        if callable(self.on_close_callback):
            self.on_close_callback()

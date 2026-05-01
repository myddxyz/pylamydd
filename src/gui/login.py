import os
import sys

import customtkinter as ctk  
from gui.api import check_if_exists
from utils import api_base_url
sys.path.append(os.path.abspath('../'))
from utils import save_dict_as_toml, load_toml_as_dict

def login(logged_in_setter):

    if api_base_url == "localhost":
        logged_in_setter(True)
        return

    def validate_api_key(api_key):
        return check_if_exists(api_key)

    def on_login_button_click():
        api_key = api_key_entry.get()
        if validate_api_key(api_key):
            result_label.configure(text="Login Successful!", text_color="green")
            logged_in_setter(True)
            app.destroy()
            save_dict_as_toml({"key": api_key}, "./cfg/login.toml")
            return
        else:
            result_label.configure(text="Invalid API Key", text_color="red")

    login_data = load_toml_as_dict('./cfg/login.toml')
    auth_key = login_data['key']
    if auth_key:
        if validate_api_key(auth_key):
            logged_in_setter(True)
            return

    app = ctk.CTk()
    app.title('PYLAMYDD — Authentication')
    app.geometry('500x230')
    ctk.set_appearance_mode("dark")
    app.configure(fg_color="#111318")

    header = ctk.CTkFrame(app, fg_color="#0d0f14", height=36)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(header, text="AUTHENTICATION", font=("Inter", 14, "bold"), text_color="#9aa0ad").pack(padx=12, pady=8)

    label = ctk.CTkLabel(app, text="Enter API Key:", font=("Inter", 18, "bold"), text_color="#f0f0f0")
    label.pack(pady=(20, 5))

    api_key_entry = ctk.CTkEntry(
        app, placeholder_text="API Key", font=("Inter", 15), width=400, height=40,
        fg_color="#1e2128", border_color="#2a2f3a", text_color="#f0f0f0"
    )
    api_key_entry.pack(pady=(10, 15))

    login_button = ctk.CTkButton(
        app, text="LOGIN", command=on_login_button_click,
        font=("Inter", 16, "bold"), fg_color="#e8343a", hover_color="#c42a30",
        corner_radius=8, height=45, width=400
    )
    login_button.pack()

    result_label = ctk.CTkLabel(app, text="", font=("Inter", 13))
    result_label.pack(pady=(8, 0))

    app.mainloop()

import os
import sys

import customtkinter as ctk  
from gui.api import check_if_exists
from utils import api_base_url
sys.path.append(os.path.abspath('../'))
from utils import update_toml_file, load_toml_as_dict

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
            update_toml_file("./cfg/login.toml", {"key": api_key})
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
    app.geometry('500x220')
    ctk.set_appearance_mode("dark")
    app.configure(fg_color="#0B0B0B")

    header = ctk.CTkFrame(app, fg_color="#1A1A1A", height=40, corner_radius=0)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(header, text="AUTHENTICATION", font=("Arial", 13, "bold"), text_color="#C80000").pack(side="left", padx=15)

    label = ctk.CTkLabel(app, text="Enter API Key:", font=("Arial", 18, "bold"), text_color="#FFFFFF")
    label.pack(pady=(15, 5))

    api_key_entry = ctk.CTkEntry(
        app, placeholder_text="API Key", font=("Arial", 16), width=400,
        fg_color="#1A1A1A", border_color="#C80000", text_color="#FFFFFF"
    )
    api_key_entry.pack(pady=(10, 10))

    login_button = ctk.CTkButton(
        app, text="LOGIN", command=on_login_button_click,
        font=("Arial", 18, "bold"), fg_color="#C80000", hover_color="#FF1A1A",
        corner_radius=6, height=40
    )
    login_button.pack()

    result_label = ctk.CTkLabel(app, text="", font=("Arial", 13))
    result_label.pack(pady=(8, 0))

    app.mainloop()

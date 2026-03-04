import hashlib
import io
import os
from io import BytesIO
import ctypes
import json
import aiohttp
import google_play_scraper
import requests
import toml
from PIL import Image
from discord import Webhook
import discord
import cv2
import numpy as np
from packaging import version

import time
import easyocr

def extract_text_and_positions(image_path):
    results = reader.readtext(image_path)
    text_details = {}
    for (bbox, text, prob) in results:
        top_left, top_right, bottom_right, bottom_left = bbox
        cx = (top_left[0] + top_right[0] + bottom_right[0] + bottom_left[0]) / 4
        cy = (top_left[1] + top_right[1] + bottom_right[1] + bottom_left[1]) / 4
        center = (cx, cy)
        formatted_bbox = {
            'top_left': top_left,
            'top_right': top_right,
            'bottom_right': bottom_right,
            'bottom_left': bottom_left,
            'center': center
        }

        text_details[text.lower()] = formatted_bbox

    return text_details

class DefaultEasyOCR:
    def __init__(self):
        self._reader = None

    def _ensure_loaded(self):
        if self._reader is None:
            self._reader = easyocr.Reader(['en'], gpu=False)

    def readtext(self, image_input):
        self._ensure_loaded()
        return self._reader.readtext(image_input)

def load_toml_as_dict(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return toml.load(f)
    else:
        return {}


reader = DefaultEasyOCR()
api_base_url = "localhost"
brawlers_info_file_path = "cfg/brawlers_info.json"

def count_hsv_pixels(image_input, low_hsv, high_hsv):
    """Count pixels in HSV range.
    If image_input is a numpy array, it MUST be BGR (from screenshot_numpy).
    If image_input is a PIL Image, it is assumed to be RGB and converted to BGR first."""
    if isinstance(image_input, np.ndarray):
        bgr_image = image_input  # Already BGR numpy
    else:
        bgr_image = cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
    hsv_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv_image, np.array(low_hsv), np.array(high_hsv))
    pixel_count = np.count_nonzero(mask)
    return pixel_count

def save_brawler_data(data):
    """
    Save the given data to a json file. As a list of dictionaries.
    """
    with open("latest_brawler_data.json", 'w') as f:
        json.dump(data, f, indent=4)



def find_template_center(main_img, template, threshold=0.8):
    if isinstance(main_img, np.ndarray):
        # Numpy arrays from screenshot_numpy() are BGR
        if len(main_img.shape) == 3:
            main_image_cv = cv2.cvtColor(main_img, cv2.COLOR_BGR2GRAY)
        else:
            main_image_cv = main_img
    else:
        # PIL images are RGB
        main_image_cv = cv2.cvtColor(np.array(main_img), cv2.COLOR_RGB2GRAY)
    template_arr = np.array(template)
    if len(template_arr.shape) == 3 and template_arr.shape[2] == 3:
        template_cv = cv2.cvtColor(template_arr, cv2.COLOR_BGR2GRAY)
    else:
        template_cv = template_arr
    w, h = template_cv.shape[::-1]

    # Perform template matching
    result = cv2.matchTemplate(main_image_cv, template_cv, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    # Check if the match is found based on a threshold value
    if max_val >= threshold:
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2

        return center_x, center_y
    else:
        return False





def save_dict_as_toml(data, file_path):
    with open(file_path, 'w') as f:
        toml.dump(data, f)


def update_toml_file(path, new_data):
    with open(path, 'w') as file:
        toml.dump(new_data, file)

def load_brawlers_info():
    if os.path.exists(brawlers_info_file_path):
        with open(brawlers_info_file_path, 'r') as f:
            return json.load(f)
    else:
        return {}

def update_brawlers_info(brawlers_info):
    with open(brawlers_info_file_path, 'w') as f:
        json.dump(brawlers_info, f, indent=4)


def get_brawler_list():
    if api_base_url == "localhost":
        brawler_list = list(load_brawlers_info().keys())
        return brawler_list
    url = f'https://{api_base_url}/get_brawler_list'
    response = requests.post(url)
    if response.status_code == 201:
        data = response.json()
        return data.get('brawlers', [])
    else:
        return []


def update_missing_brawlers_info(brawlers):
    brawlers_info = load_brawlers_info()
    for brawler in brawlers:
        if brawler not in brawlers_info:
            brawler_info = get_brawler_info(brawler)
            if brawler_info:
                brawlers_info[brawler] = brawler_info
                update_brawlers_info(brawlers_info)
                print(f"Added info for brawler '{brawler}': {brawler_info}")
                # Download the brawler icon
                save_brawler_icon(brawler)
            else:
                print(f"Could not find info for brawler '{brawler}'")
        if not os.path.exists(f"./api/assets/brawler_icons/{brawler}.png"):
            save_brawler_icon(brawler)


def get_brawler_info(brawler_name):
    url = f'https://{api_base_url}/get_brawler_info'  # Adjust the URL if necessary
    response = requests.post(url, json={'brawler_name': brawler_name})
    if response.status_code == 200:
        data = response.json()
        return data.get('info', [])
    else:
        print(f"Error fetching range for '{brawler_name}': {response.status_code} - {response.text}")
        return None


def save_brawler_icon(brawler_name):
    # Clean the brawler name for filename
    brawler_name_clean = brawler_name.lower().replace(' ', '').replace('-', '').replace('.', '').replace('&',
                                                                                                         '')
    brawlers_url = "https://api.brawlapi.com/v1/brawlers"
    response = requests.get(brawlers_url)
    if response.status_code != 200:
        print(f"Failed to fetch brawlers from API: {response.status_code}")
        return
    brawlers_data = response.json()['list']

    # Find the brawler in the API data
    for brawler_obj in brawlers_data:
        api_brawler_name = brawler_obj['name'].lower().replace(' ', '').replace('-', '').replace('.',
                                                                                                 '').replace(
            '&', '')
        if api_brawler_name == brawler_name_clean:
            icon_url = brawler_obj['imageUrl2']
            img_response = requests.get(icon_url)
            if img_response.status_code == 200:
                image = Image.open(BytesIO(img_response.content))
                image.save(f"api/assets/brawler_icons/{brawler_name_clean}.png")
                print(f"Saved icon for brawler '{brawler_name}'")
            else:
                print(f"Failed to download icon for '{brawler_name}'")
            return
    print(f"Icon not found for brawler '{brawler_name}'")


def update_icons():
    try:
        icon_link = google_play_scraper.app("com.supercell.brawlstars")["icon"]
    except:
        time.sleep(1)
        try:
            icon_link = google_play_scraper.app("com.supercell.brawlstars")["icon"]
        except Exception as e:
            print(f"Failed to get latest icon link from Google Play Store: {e}")
            return

    response = requests.get(icon_link)
    big_icon = 'brawl_stars_icon_big.png'
    small_icon = 'brawl_stars_icon.png'
    if response.status_code == 200:
        icon_image = Image.open(BytesIO(response.content))

        # big icon
        big_icon_image = icon_image.resize((69, 69))
        width, height = big_icon_image.size
        left = (width - 50) / 2
        top = (height - 50) / 2
        right = (width + 50) / 2
        bottom = (height + 50) / 2
        big_icon_image = big_icon_image.crop((left, top, right, bottom))
        big_icon_image.save(f'./state_finder/images_to_detect/{big_icon}')

        # small icon resize to 16x16
        small_icon_image = icon_image.resize((16, 16))
        width, height = small_icon_image.size
        left = (width - 12) / 2
        top = (height - 12) / 2
        right = (width + 12) / 2
        bottom = (height + 12) / 2
        small_icon_image = small_icon_image.crop((left, top, right, bottom))
        small_icon_image.save(f'./state_finder/images_to_detect/{small_icon}')
        print(f"Updated to the latest icon !")
    else:
        print(f"Failed to download latest icon. Status code: {response.status_code}")


def get_latest_version():
    url = f'https://{api_base_url}/check_version'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('version', '')
    else:
        return None

def check_version():
    if api_base_url != "localhost":
        latest_version = get_latest_version()
        if latest_version:
            current_version = load_toml_as_dict("cfg/general_config.toml").get('pyla_version', '')
            if version.parse(current_version) < version.parse(latest_version):
                print(f"Warning: (ignore if you're using early access) You are not using the latest public version of Pyla. \nCheck the discord for the latest download link.")
        else:
            print("Error, couldn't get the version, please check your internet connection or go ask for help in the discord.")


async def async_notify_user(message_type: str | None = None, screenshot: Image = None) -> None:
    user_id = load_toml_as_dict("cfg/general_config.toml")["discord_id"]
    webhook_url = load_toml_as_dict("cfg/general_config.toml")["personal_webhook"]
    if not webhook_url:
        print("Couldn't notify: no webhook configured.")
        return

    if message_type == "completed":
        status_line = f"Pyla has completed all its targets!"
        ping = f"<@{user_id}>"
    elif message_type == "bot_is_stuck":
        status_line = f"Your bot is currently stuck!"
        ping = f"<@{user_id}>"
    else:
        status_line = f"Pyla completed brawler goal for {message_type}!"
        ping = f"<@{user_id}>"

    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    buffer.seek(0)
    file = discord.File(buffer, filename="screenshot.png")

    # Build the embed that holds both the text and the screenshot
    embed = discord.Embed(description=status_line)
    embed.set_image(url="attachment://screenshot.png")   # show the attached screenshot

    # Send the embed
    async with aiohttp.ClientSession() as session:
        webhook = Webhook.from_url(webhook_url, session=session)
        print("sending webhook")
        await webhook.send(embed=embed, file=file, username="Pyla notifier", content=ping)
        
def get_discord_link():
    if api_base_url == "localhost":
        return "https://discord.gg/xUusk3fw4A"
    url = f'https://{api_base_url}/get_discord_link'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('link', '')
    else:
        return None

def get_online_wall_model_hash():
    url = f'https://{api_base_url}/get_wall_model_hash'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('hash', '')
    else:
        return None

def calculate_sha256(file_path):
    """
    Calculate the SHA-256 hash of a file.
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as file:
        # Read the file in chunks to handle large files
        for chunk in iter(lambda: file.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def current_wall_model_is_latest() -> bool:
    """
    Check if the current wall model is the latest version.
    """
    local_hash = calculate_sha256("models/tileDetector.onnx")
    online_hash = get_online_wall_model_hash()
    return local_hash == online_hash

def get_latest_wall_model_file():
    #download the new model to replace the current file and also updates the tile list
    url = f'https://{api_base_url}/get_wall_model_file'
    response = requests.get(url)
    if response.status_code == 200:
        with open("./models/tileDetector.onnx", "wb") as file:
            file.write(response.content)
        print("Downloaded the latest wall model.")
    else:
        print(f"Failed to download the latest wall model. Status code: {response.status_code}")

def get_latest_wall_model_classes():
    url = f'https://{api_base_url}/get_wall_model_classes'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('classes', [])
    else:
        return None

def update_wall_model_classes():
    classes = get_latest_wall_model_classes()
    current_classes = load_toml_as_dict("cfg/bot_config.toml")["wall_model_classes"]
    if classes:
        if classes != current_classes:
            print("New wall model classes found. Updating...")
            full_config = load_toml_as_dict("cfg/bot_config.toml")
            full_config["wall_model_classes"] = classes
            update_toml_file("cfg/bot_config.toml", full_config)
            print("Updated the wall model classes.")
    else:
        print("Failed to update the wall model classes, please report this error.")


def cprint(text: str, hex_color: str): #omg color!!!
    try:
        hex_color = hex_color.lstrip("#")
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        print(f"\033[38;2;{r};{g};{b}m{text}\033[0m")
    except Exception:
        print(text)

def get_dpi_scale():
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    return int(user32.GetDpiForSystem())
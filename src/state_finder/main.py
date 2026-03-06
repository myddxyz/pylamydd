import os
import sys
from utils import reader, extract_text_and_positions
import cv2
import numpy as np
sys.path.append(os.path.abspath('../'))
from utils import count_hsv_pixels, load_toml_as_dict
from trophy_observer import TrophyObserver

orig_screen_width, orig_screen_height = 1920, 1080

path = r"./state_finder/images_to_detect/"
images_with_star_drop = []

for file in os.listdir("./state_finder/images_to_detect"):
    if "star_drop" in file:
        images_with_star_drop.append(file)
# path = r"./images_to_detect/"
region_data = load_toml_as_dict("./cfg/lobby_config.toml")['template_matching']
super_debug = load_toml_as_dict("./cfg/general_config.toml")['super_debug'] == "yes"
if super_debug:
    debug_folder = "./debug_frames/"
    if not os.path.exists(debug_folder):
        os.makedirs(debug_folder)
def is_template_in_region(image, template_path, region):
    current_height, current_width = image.shape[:2]
    orig_x, orig_y, orig_width, orig_height = region
    width_ratio, height_ratio = current_width / orig_screen_width, current_height / orig_screen_height


    new_x, new_y = int(orig_x * width_ratio), int(orig_y * height_ratio)
    new_width, new_height = int(orig_width * width_ratio), int(orig_height * height_ratio)
    cropped_image = image[new_y:new_y + new_height, new_x:new_x + new_width]
    current_height, current_width = image.shape[:2]
    loaded_template = load_template(template_path, current_width, current_height)
    # save to debug frames both template and image
    result = cv2.matchTemplate(cropped_image, loaded_template,
                               cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    return max_val > 0.7


_template_cache = {}

def load_template(image_path, width, height):
    """Load and resize template — cached after first load per resolution."""
    cache_key = (image_path, width, height)
    if cache_key in _template_cache:
        return _template_cache[cache_key]
    current_width_ratio, current_height_ratio = width / orig_screen_width, height / orig_screen_height
    image = cv2.imread(image_path)
    orig_height, orig_width = image.shape[:2]
    resized_image = cv2.resize(image, (int(orig_width * current_width_ratio), int(orig_height * current_height_ratio)))
    _template_cache[cache_key] = resized_image
    return resized_image

crop_region = load_toml_as_dict("./cfg/lobby_config.toml")['lobby']['trophy_observer']


def rework_game_result(res_string):
    return TrophyObserver.rework_game_result(res_string)



def find_game_result(screenshot):
    # Vérifiez que screenshot est bien un numpy.ndarray
    if not isinstance(screenshot, np.ndarray):
        raise TypeError("Expected a numpy.ndarray, but got {}".format(type(screenshot)))

    # Effectuez le recadrage directement sur l'array numpy
    x1, y1, x2, y2 = crop_region
    screenshot = screenshot[y1:y2, x1:x2]

    # Appliquez l'OCR
    result = reader.readtext(screenshot)
    if len(result) == 0:
        return False

    _, text, conf = result[0]
    game_result, ratio = rework_game_result(text)
    if ratio < 0.55:
        if ratio > 0:
            print("Couldn't find game result", game_result, ratio)
        return False
    return True


def get_in_game_state(image):
    if is_in_end_of_a_match(image): return "end"
    if is_in_shop(image): return "shop"
    if is_in_offer_popup(image): return "popup"
    if is_in_lobby(image): return "lobby"
    if is_in_brawler_selection(image):
        return "brawler_selection"

    if count_hsv_pixels(image, (0, 0, 240), (180, 20, 255)) > 300000:
        return "play_store"

    if is_in_brawl_pass(image) or is_in_star_road(image):
        return "shop"

    if is_in_star_drop(image):
        return "star_drop"

    if is_in_trophy_reward(image):
        return "trophy_reward"

    return "match"


def is_in_shop(image) -> bool:
    return is_template_in_region(image, path + 'powerpoint.png', region_data["powerpoint"])


def is_in_brawler_selection(image) -> bool:
    return is_template_in_region(image, path + 'brawler_menu_task.png', region_data["brawler_menu_task"])


def is_in_offer_popup(image) -> bool:
    return is_template_in_region(image, path + 'close_popup.png', region_data["close_popup"])


def is_in_lobby(image) -> bool:
    return is_template_in_region(image, path + 'lobby_menu.png', region_data["lobby_menu"])


def is_in_end_of_a_match(image):
    return find_game_result(image)



def is_in_trophy_reward(image):
    starting_x = int(image.shape[1] * 0.75)
    starting_y = int(image.shape[0] * 0.75)
    image = image[starting_y:, starting_x:]
    all_text = (" ".join(extract_text_and_positions(image).keys())).lower().replace("'", "")
    return "go" in all_text


def is_in_brawl_pass(image):
    return is_template_in_region(image, path + 'brawl_pass_house.PNG',
                                 region_data['brawl_pass_house'])


def is_in_star_road(image):
    return is_template_in_region(image, path + "go_back_arrow.png", region_data['go_back_arrow'])


def is_in_star_drop(image):
    for image_filename in images_with_star_drop: #kept getting errors so tried changing from image to image_filename
        if is_template_in_region(image, path + image_filename, region_data['star_drop']):
            return True
    return False

def get_state(screenshot):
    """Accepts BGR numpy array."""
    if super_debug:
        cv2.imwrite(f"./debug_frames/state_screenshot_{len(os.listdir('./debug_frames'))}.png", screenshot)
    state = get_in_game_state(screenshot)
    print(f"State: {state}")
    return state



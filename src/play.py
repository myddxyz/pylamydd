import math
import random
import time

import cv2
from shapely import LineString
from shapely.geometry import Polygon
from state_finder.main import get_state
from detect import Detect
from utils import load_toml_as_dict, count_hsv_pixels, load_brawlers_info

brawl_stars_width, brawl_stars_height = 1920, 1080
debug = load_toml_as_dict("cfg/general_config.toml")['super_debug'] == "yes"
super_crop_area = load_toml_as_dict("./cfg/lobby_config.toml")['pixel_counter_crop_area']['super']
gadget_crop_area = load_toml_as_dict("./cfg/lobby_config.toml")['pixel_counter_crop_area']['gadget']
hypercharge_crop_area = load_toml_as_dict("./cfg/lobby_config.toml")['pixel_counter_crop_area']['hypercharge']

class Movement:

    def __init__(self, window_controller):
        bot_config = load_toml_as_dict("cfg/bot_config.toml")
        time_config = load_toml_as_dict("cfg/time_tresholds.toml")
        self.fix_movement_keys = {
            "delay_to_trigger": bot_config["unstuck_movement_delay"],
            "duration": bot_config["unstuck_movement_hold_time"],
            "toggled": False,
            "started_at": time.time(),
            "fixed": ""
        }
        self.game_mode = bot_config["gamemode_type"]
        gadget_value = bot_config["bot_uses_gadgets"]
        self.should_use_gadget = str(gadget_value).lower() in ("yes", "true", "1")
        self.super_treshold = time_config["super"]
        self.gadget_treshold = time_config["gadget"]
        self.hypercharge_treshold = time_config["hypercharge"]
        self.walls_treshold = time_config["wall_detection"]
        self.keep_walls_in_memory = self.walls_treshold <= 1
        self.last_walls_data = []
        self.keys_hold = []
        self.time_since_different_movement = time.time()
        self.time_since_gadget_checked = time.time()
        self.is_gadget_ready = False
        self.time_since_hypercharge_checked = time.time()
        self.is_hypercharge_ready = False
        self.window_controller = window_controller
        self.TILE_SIZE = 60
        
    @staticmethod
    def get_enemy_pos(enemy):
        return (enemy[0] + enemy[2]) / 2, (enemy[1] + enemy[3]) / 2

    @staticmethod
    def get_player_pos(player_data):
        return (player_data[0] + player_data[2]) / 2, (player_data[1] + player_data[3]) / 2

    @staticmethod
    def get_distance(enemy_coords, player_coords):
        return math.hypot(enemy_coords[0] - player_coords[0], enemy_coords[1] - player_coords[1])

    @staticmethod
    def is_there_enemy(enemy_data):
        if not enemy_data:
            return False
        return True

    @staticmethod
    def get_horizontal_move_key(direction_x, opposite=False):
        if opposite:
            return "A" if direction_x > 0 else "D"
        return "D" if direction_x > 0 else "A"

    @staticmethod
    def get_vertical_move_key(direction_y, opposite=False):
        if opposite:
            return "W" if direction_y > 0 else "S"
        return "S" if direction_y > 0 else "W"

    def attack(self):
        """Auto-aim attack."""
        self.window_controller.press_key("M")

    def use_hypercharge(self):
        print("Using hypercharge")
        self.window_controller.press_key("H")

    def use_gadget(self):
        print("Using gadget")
        self.window_controller.press_key("G")

    def use_super(self):
        print("Using super")
        self.window_controller.press_key("E")

    @staticmethod
    def get_random_attack_key():
        random_movement = random.choice(["A", "W", "S", "D"])
        random_movement += random.choice(["A", "W", "S", "D"])
        return random_movement

    @staticmethod
    def reverse_movement(movement):
        # Create a translation table
        movement = movement.lower()
        translation_table = str.maketrans("wasd", "sdwa")
        return movement.translate(translation_table)

    def unstuck_movement_if_needed(self, movement, current_time=None):
        if current_time is None:
            current_time = time.time()
        movement = movement.lower()
        if self.fix_movement_keys['toggled']:
            if current_time - self.fix_movement_keys['started_at'] > self.fix_movement_keys['duration']:
                self.fix_movement_keys['toggled'] = False

            return self.fix_movement_keys['fixed']

        if "".join(self.keys_hold) != movement and movement[::-1] != "".join(self.keys_hold):
            self.time_since_different_movement = current_time

        # print(f"Last change: {self.time_since_different_movement}", f" self.hold: {self.keys_hold}",f" c movement: {movement}")
        if current_time - self.time_since_different_movement > self.fix_movement_keys["delay_to_trigger"]:
            reversed_movement = self.reverse_movement(movement)

            if reversed_movement == "s":
                reversed_movement = random.choice(['aw', 'dw'])
            elif reversed_movement == "w":
                reversed_movement = random.choice(['as', 'ds'])

            """
            If reverse movement is either "w" or "s" it means the bot is stuck
            going forward or backward. This happens when it doesn't detect a wall in front
            so to go around it it could either go to the left diagonal or right
            """

            self.fix_movement_keys['fixed'] = reversed_movement
            self.fix_movement_keys['toggled'] = True
            self.fix_movement_keys['started_at'] = current_time
            #print(f"REVERSED! from {movement} to {reversed_movement}!")
            return reversed_movement

        return movement


class Play(Movement):

    def __init__(self, main_info_model, tile_detector_model, window_controller):
        super().__init__(window_controller)

        bot_config = load_toml_as_dict("cfg/bot_config.toml")
        time_config = load_toml_as_dict("cfg/time_tresholds.toml")

        self.Detect_main_info = Detect(main_info_model, classes=['enemy', 'teammate', 'player'])
        self.tile_detector_model_classes = bot_config["wall_model_classes"]
        self.Detect_tile_detector = Detect(
            tile_detector_model,
            classes=self.tile_detector_model_classes
        )

        self.time_since_movement = time.time()
        self.time_since_gadget_checked = time.time()
        self.time_since_hypercharge_checked = time.time()
        self.time_since_super_checked = time.time()
        self.time_since_walls_checked = 0
        self.time_since_movement_change = time.time()
        self.time_since_player_last_found = time.time()
        self.current_brawler = None
        self.is_hypercharge_ready = False
        self.is_gadget_ready = False
        self.is_super_ready = False
        self.brawlers_info = load_brawlers_info()
        self.brawler_ranges = None
        self.time_since_detections = {
            "player": time.time(),
            "enemy": time.time(),
        }
        self.time_since_last_proceeding = time.time()

        self.last_movement = ''
        self.last_movement_time = time.time()
        self.time_since_last_attack = 0
        self.attack_cooldown = bot_config.get("attack_cooldown", 0.35)

        # --- Ammo tracking (per-brawler reload from brawlers_info.json) ---
        self.max_ammo = 3
        self.current_ammo = self.max_ammo
        self.shot_timestamps = []  # timestamps of recent shots for reload calc

        # --- Micro-strafing ---
        self.strafe_direction = 1  # 1 or -1 (left/right)
        self.strafe_switch_time = time.time()
        self.strafe_interval = bot_config.get("strafe_interval", 0.3)  # quick micro-dodges

        self.wall_history = []
        self.wall_history_length = 3  # Number of frames to keep walls
        self.scene_data = []
        self.should_detect_walls = bot_config["gamemode"] in ["brawlball", "brawl_ball", "brawll ball"]
        self.minimum_movement_delay = bot_config["minimum_movement_delay"]
        self.no_detection_proceed_delay = time_config["no_detection_proceed"]
        self.gadget_pixels_minimum = bot_config["gadget_pixels_minimum"]
        self.hypercharge_pixels_minimum = bot_config["hypercharge_pixels_minimum"]
        self.super_pixels_minimum = bot_config["super_pixels_minimum"]
        self.wall_detection_confidence = bot_config["wall_detection_confidence"]
        self.entity_detection_confidence = bot_config["entity_detection_confidence"]

    def load_brawler_ranges(self, brawlers_info=None):
        if not brawlers_info:
            brawlers_info = load_brawlers_info()
        screen_size_ratio = self.window_controller.scale_factor
        ranges = {}
        for brawler, info in brawlers_info.items():
            attack_range = info['attack_range']
            safe_range = info['safe_range']
            super_range = info['super_range']
            v = [safe_range, attack_range, super_range]
            ranges[brawler] = [int(v[0] * screen_size_ratio), int(v[1] * screen_size_ratio), int(v[2] * screen_size_ratio)]
        return ranges

    @staticmethod
    def can_attack_through_walls(brawler, skill_type, brawlers_info=None):
        if not brawlers_info: brawlers_info = load_brawlers_info()
        if skill_type == "attack":
            return brawlers_info[brawler]['ignore_walls_for_attacks']
        elif skill_type == "super":
            return brawlers_info[brawler]['ignore_walls_for_supers']
        raise ValueError("skill_type must be either 'attack' or 'super'")


    @staticmethod
    def walls_are_in_line_of_sight(line_of_sight, walls):
        for wall in walls:
            x1, y1, x2, y2 = wall
            wall_polygon = Polygon([
                (x1, y1), (x2, y1),
                (x2, y2), (x1, y2)
            ])
            if line_of_sight.intersects(wall_polygon):
                return True
        return False

    def no_enemy_movement(self, player_data, walls):
        player_position = self.get_player_pos(player_data)
        preferred_movement = 'W' if self.game_mode == 3 else 'D'  # Adjust based on game mode

        if not self.is_path_blocked(player_position, preferred_movement, walls):
            return preferred_movement
        else:
            # Try alternative movements
            alternative_moves = ['W', 'A', 'S', 'D']
            alternative_moves.remove(preferred_movement)
            random.shuffle(alternative_moves)
            for move in alternative_moves:
                if not self.is_path_blocked(player_position, move, walls):
                    return move
            print("no movement possible ?")
            # If no movement is possible, return empty string
            return preferred_movement

    def is_enemy_hittable(self, player_pos, enemy_pos, walls, skill_type):
        if self.can_attack_through_walls(self.current_brawler, skill_type, self.brawlers_info):
            return True
        if self.walls_are_in_line_of_sight(LineString([player_pos, enemy_pos]), walls):
            return False
        return True

    def find_closest_enemy(self, enemy_data, player_coords, walls, skill_type):
        player_pos_x, player_pos_y = player_coords
        closest_hittable_distance = float('inf')
        closest_unhittable_distance = float('inf')
        closest_hittable = None
        closest_unhittable = None
        for enemy in enemy_data:
            enemy_pos = self.get_enemy_pos(enemy)
            distance = self.get_distance(enemy_pos, player_coords)
            if self.is_enemy_hittable((player_pos_x, player_pos_y), enemy_pos, walls, skill_type):
                if distance < closest_hittable_distance:
                    closest_hittable_distance = distance
                    closest_hittable = [enemy_pos, distance]
            else:
                if distance < closest_unhittable_distance:
                    closest_unhittable_distance = distance
                    closest_unhittable = [enemy_pos, distance]
        if closest_hittable:
            return closest_hittable
        elif closest_unhittable:
            return closest_unhittable

        return None, None

    def get_main_data(self, frame):
        data = self.Detect_main_info.detect_objects(frame, conf_tresh=self.entity_detection_confidence)
        return data

    def is_path_blocked(self, player_pos, move_direction, walls, distance=None):  # Increased distance
        if distance is None:
            distance = self.TILE_SIZE*self.window_controller.scale_factor
        dx, dy = 0, 0
        if 'w' in move_direction.lower():
            dy -= distance
        if 's' in move_direction.lower():
            dy += distance
        if 'a' in move_direction.lower():
            dx -= distance
        if 'd' in move_direction.lower():
            dx += distance
        new_pos = (player_pos[0] + dx, player_pos[1] + dy)
        path_line = LineString([player_pos, new_pos])
        return self.walls_are_in_line_of_sight(path_line, walls)

    @staticmethod
    def validate_game_data(data):
        incomplete = False
        if "player" not in data.keys():
            incomplete = True  # This is required so track_no_detections can also keep track if enemy is missing

        if "enemy" not in data.keys():
            data['enemy'] = None

        if 'wall' not in data.keys() or not data['wall']:
            data['wall'] = []

        return False if incomplete else data

    def track_no_detections(self, data):
        if not data:
            data = {
                "enemy": None,
                "player": None
            }
        for key in self.time_since_detections:
            if key in data and data[key]:
                self.time_since_detections[key] = time.time()

    def do_movement(self, movement):
        movement = movement.lower()
        keys_to_keyDown = []
        for key in ['w', 'a', 's', 'd']:
            if key in movement:
                keys_to_keyDown.append(key)

        if keys_to_keyDown:
            self.window_controller.keys_down(keys_to_keyDown)

        self.keys_hold = keys_to_keyDown

    def get_brawler_range(self, brawler):
        if self.brawler_ranges is None:
            self.brawler_ranges = self.load_brawler_ranges(self.brawlers_info)
        return self.brawler_ranges[brawler]

    def loop(self, brawler, data, current_time):
        movement = self.get_movement(player_data=data['player'][0], enemy_data=data['enemy'], walls=data['wall'], brawler=brawler)
        current_time = time.time()
        if current_time - self.time_since_movement > self.minimum_movement_delay:
            movement = self.unstuck_movement_if_needed(movement, current_time)
            self.do_movement(movement)
            self.time_since_movement = time.time()
        return movement

    def check_if_hypercharge_ready(self, frame):
        """Check hypercharge status via HSV pixel count. Expects BGR numpy frame."""
        x1 = int(hypercharge_crop_area[0] * self.window_controller.width_ratio)
        y1 = int(hypercharge_crop_area[1] * self.window_controller.height_ratio)
        x2 = int(hypercharge_crop_area[2] * self.window_controller.width_ratio)
        y2 = int(hypercharge_crop_area[3] * self.window_controller.height_ratio)
        crop = frame[y1:y2, x1:x2]
        purple_pixels = count_hsv_pixels(crop, (137, 158, 159), (179, 255, 255))
        if debug:
            print("hypercharge purple pixels:", purple_pixels, "(if > ", self.hypercharge_pixels_minimum, " then hypercharge is ready)")
            cv2.imwrite(f"debug_frames/hypercharge_debug_{int(time.time())}.png", crop)
        if purple_pixels > self.hypercharge_pixels_minimum:
            return True
        return False

    def check_if_gadget_ready(self, frame):
        """Check gadget status via HSV pixel count. Expects BGR numpy frame."""
        x1 = int(gadget_crop_area[0] * self.window_controller.width_ratio)
        y1 = int(gadget_crop_area[1] * self.window_controller.height_ratio)
        x2 = int(gadget_crop_area[2] * self.window_controller.width_ratio)
        y2 = int(gadget_crop_area[3] * self.window_controller.height_ratio)
        crop = frame[y1:y2, x1:x2]
        green_pixels = count_hsv_pixels(crop, (57, 219, 165), (62, 255, 255))
        if debug:
            print("gadget green pixels:", green_pixels, "(if > ", self.gadget_pixels_minimum, " then gadget is ready)")
            cv2.imwrite(f"debug_frames/gadget_debug_{int(time.time())}.png", crop)
        if green_pixels > self.gadget_pixels_minimum:
            return True
        return False

    def check_if_super_ready(self, frame):
        """Check super status via HSV pixel count. Expects BGR numpy frame."""
        x1 = int(super_crop_area[0] * self.window_controller.width_ratio)
        y1 = int(super_crop_area[1] * self.window_controller.height_ratio)
        x2 = int(super_crop_area[2] * self.window_controller.width_ratio)
        y2 = int(super_crop_area[3] * self.window_controller.height_ratio)
        crop = frame[y1:y2, x1:x2]
        yellow_pixels = count_hsv_pixels(crop, (19, 190, 232), (24, 240, 255))
        if debug:
            print("super yellow pixels:", yellow_pixels, "(if > ", self.super_pixels_minimum, " then super is ready)")
            cv2.imwrite(f"debug_frames/super_debug_{int(time.time())}.png", crop)
        if yellow_pixels > self.super_pixels_minimum:
            return True
        return False

    def get_tile_data(self, frame):
        tile_data = self.Detect_tile_detector.detect_objects(frame, conf_tresh=self.wall_detection_confidence)
        return tile_data

    def process_tile_data(self, tile_data):
        walls = []
        for class_name, boxes in tile_data.items():
            if class_name != 'bush':
                walls.extend(boxes)

        self.wall_history.append(walls)
        if len(self.wall_history) > self.wall_history_length:
            self.wall_history.pop(0)
        combined_walls = self.combine_walls_from_history()

        return combined_walls

    def combine_walls_from_history(self):
        wall_counts = {}
        for walls in self.wall_history:
            for wall in walls:
                wall_key = tuple(wall)
                wall_counts[wall_key] = wall_counts.get(wall_key, 0) + 1

        threshold = 1

        combined_walls = [list(wall) for wall, count in wall_counts.items() if count >= threshold]

        return combined_walls

    def _update_ammo(self, current_time, brawler):
        """Refill ammo based on per-brawler reload time."""
        reload = self.brawlers_info.get(brawler, {}).get("reload_time", 1.5)
        self.shot_timestamps = [t for t in self.shot_timestamps
                                if current_time - t < reload]
        self.current_ammo = self.max_ammo - len(self.shot_timestamps)

    def _consume_ammo(self, current_time):
        """Record a shot and decrement ammo."""
        self.shot_timestamps.append(current_time)
        self.current_ammo = self.max_ammo - len(self.shot_timestamps)

    def _add_strafe(self, movement, direction_x, direction_y, current_time):
        """Add lateral strafing to dodge enemy shots while in combat."""
        # Switch strafe direction periodically
        if current_time - self.strafe_switch_time >= self.strafe_interval:
            self.strafe_direction *= -1
            self.strafe_switch_time = current_time

        # Determine lateral direction (perpendicular to enemy direction)
        if abs(direction_x) > abs(direction_y):
            # Enemy is mostly horizontal → strafe vertically
            strafe_key = "W" if self.strafe_direction > 0 else "S"
        else:
            # Enemy is mostly vertical → strafe horizontally
            strafe_key = "A" if self.strafe_direction > 0 else "D"

        # Add strafe key to movement if not already there and doesn't cancel
        opposite = {'W': 'S', 'S': 'W', 'A': 'D', 'D': 'A'}
        if strafe_key not in movement.upper() and opposite[strafe_key] not in movement.upper():
            movement = movement + strafe_key
        return movement

    def _get_category_behavior(self, brawler, enemy_distance, safe_range, attack_range):
        """Return playstyle adjustments based on brawler category.
        Returns (range_multiplier, aggression, should_strafe)
        - range_multiplier: how far within attack_range to start shooting (0.0-1.0)
        - aggression: safe_range override factor (lower = more aggressive)
        - should_strafe: whether to strafe during combat
        """
        category = self.brawlers_info.get(brawler, {}).get("category", "fighter")

        if category == "tank":
            # Tanks: rush in, get close, be aggressive, light strafe
            return 1.0, 0.3, True
        elif category == "assassin":
            # Assassins: rush in fast, attack at full range, strafe a lot
            return 0.9, 0.2, True
        elif category == "sharpshooter":
            # Sharpshooters: keep max distance, only shoot at 70% range, strafe
            return 0.7, 1.5, True
        elif category == "thrower":
            # Throwers: stay far, shoot at 80% range, light strafe
            return 0.8, 1.3, True
        elif category == "support":
            # Support: stay back, shoot conservatively at 75% range, strafe
            return 0.75, 1.2, True
        elif category == "controller":
            # Controllers: medium distance, zone enemies, strafe
            return 0.8, 1.1, True
        else:  # fighter (default)
            # Fighters: balanced, shoot at 80% range, strafe
            return 0.8, 1.0, True

    def get_movement(self, player_data, enemy_data, walls, brawler):
        brawler_info = self.brawlers_info.get(brawler)
        if not brawler_info:
            raise ValueError(f"Brawler '{brawler}' not found in brawlers info.")
        safe_range, attack_range, super_range = self.get_brawler_range(brawler)

        # Get category-based behavior
        range_mult, aggression, should_strafe = self._get_category_behavior(
            brawler, 0, safe_range, attack_range
        )
        effective_safe_range = int(safe_range * aggression)

        player_pos = self.get_player_pos(player_data)
        current_time = time.time()
        self._update_ammo(current_time, brawler)

        if debug: print(f"[{brawler}] pos:{player_pos} ammo:{self.current_ammo} cat:{brawler_info.get('category','?')}")
        if not self.is_there_enemy(enemy_data):
            return self.no_enemy_movement(player_data, walls)
        enemy_coords, enemy_distance = self.find_closest_enemy(enemy_data, player_pos, walls, "attack")
        if enemy_coords is None:
            return self.no_enemy_movement(player_data, walls)
        if debug: print(f"  enemy:{enemy_coords} dist:{enemy_distance:.0f} range:{attack_range}")
        direction_x = enemy_coords[0] - player_pos[0]
        direction_y = enemy_coords[1] - player_pos[1]

        # --- Retreat if out of ammo ---
        out_of_ammo = self.current_ammo <= 0

        # Determine initial movement direction based on category behavior
        if out_of_ammo:
            # No ammo: always retreat
            move_horizontal = self.get_horizontal_move_key(direction_x, opposite=True)
            move_vertical = self.get_vertical_move_key(direction_y, opposite=True)
        elif enemy_distance > effective_safe_range:  # Move towards enemy
            move_horizontal = self.get_horizontal_move_key(direction_x)
            move_vertical = self.get_vertical_move_key(direction_y)
        else:  # Too close, move away
            move_horizontal = self.get_horizontal_move_key(direction_x, opposite=True)
            move_vertical = self.get_vertical_move_key(direction_y, opposite=True)

        movement_options = [move_horizontal + move_vertical]
        if self.game_mode == 3:
            movement_options += [move_vertical, move_horizontal]
        elif self.game_mode == 5:
            movement_options += [move_horizontal, move_vertical]
        else:
            raise ValueError("Gamemode type is invalid")

        # Check for walls and adjust movement
        for move in movement_options:
            if not self.is_path_blocked(player_pos, move, walls):
                movement = move
                break
        else:
            print("default paths are blocked")
            alternative_moves = ['W', 'A', 'S', 'D']
            random.shuffle(alternative_moves)
            for move in alternative_moves:
                if not self.is_path_blocked(player_pos, move, walls):
                    movement = move
                    break
            else:
                movement = move_horizontal + move_vertical

        # --- Micro-strafing (only for categories that benefit from it) ---
        if should_strafe and enemy_distance <= attack_range * 1.2 and not out_of_ammo:
            movement = self._add_strafe(movement, direction_x, direction_y, current_time)

        if movement != self.last_movement:
            if current_time - self.last_movement_time >= self.minimum_movement_delay:
                self.last_movement = movement
                self.last_movement_time = current_time
            else:
                movement = self.last_movement
        else:
            self.last_movement_time = current_time

        # --- Attack logic with category-based range ---
        effective_attack_range = attack_range * range_mult
        can_attack_now = (
            enemy_distance <= effective_attack_range
            and self.current_ammo > 0
            and (current_time - self.time_since_last_attack >= self.attack_cooldown)
        )

        if enemy_distance <= attack_range:
            if self.should_use_gadget and self.is_gadget_ready:
                self.use_gadget()
                self.time_since_gadget_checked = time.time()
                self.is_gadget_ready = False
            if self.is_hypercharge_ready:
                self.use_hypercharge()
                self.time_since_hypercharge_checked = time.time()
                self.is_hypercharge_ready = False

        if can_attack_now:
            enemy_hittable = self.is_enemy_hittable(player_pos, enemy_coords, walls, "attack")
            if enemy_hittable:
                self.attack()
                self._consume_ammo(current_time)
                self.time_since_last_attack = current_time

        if self.is_super_ready:
            super_type = brawler_info['super_type']
            enemy_hittable = self.is_enemy_hittable(player_pos, enemy_coords, walls, "super")

            if (enemy_hittable and
                    (enemy_distance <= super_range
                     or super_type in ["spawnable", "other"]
                     or (brawler in ["stu", "surge"] and super_type == "charge" and enemy_distance <= super_range + attack_range)
                    )):
                self.use_super()
                self.time_since_super_checked = time.time()
                self.is_super_ready = False
        return movement

    def main(self, frame, brawler):
        # Reset ammo state when switching brawlers
        if brawler != self.current_brawler:
            self.current_brawler = brawler
            self.shot_timestamps = []
            self.current_ammo = self.max_ammo
        current_time = time.time()
        data = self.get_main_data(frame)
        if self.should_detect_walls and current_time - self.time_since_walls_checked > self.walls_treshold:

            tile_data = self.get_tile_data(frame)

            walls = self.process_tile_data(tile_data)

            self.time_since_walls_checked = current_time
            self.last_walls_data = walls
            data['wall'] = walls
        elif self.keep_walls_in_memory:
            data['wall'] = self.last_walls_data


        data = self.validate_game_data(data)
        self.track_no_detections(data)
        if data:
            self.time_since_player_last_found = time.time()
        if not data:
            if current_time - self.time_since_player_last_found > 1.0:
                self.window_controller.keys_up(list("wasd"))
            self.time_since_different_movement = time.time()
            if current_time - self.time_since_last_proceeding > self.no_detection_proceed_delay:
                current_state = get_state(frame)
                if current_state != "match":
                    self.time_since_last_proceeding = current_time
                else:
                    print("haven't detected the player in a while proceeding")
                    self.window_controller.press_key("Q")
                    self.time_since_last_proceeding = time.time()
            return
        self.time_since_last_proceeding = time.time()
        self.is_hypercharge_ready = False
        if current_time - self.time_since_hypercharge_checked > self.hypercharge_treshold:
            self.is_hypercharge_ready = self.check_if_hypercharge_ready(frame)
            self.time_since_hypercharge_checked = current_time
        self.is_gadget_ready = False
        if current_time - self.time_since_gadget_checked > self.gadget_treshold:
            self.is_gadget_ready = self.check_if_gadget_ready(frame)
            self.time_since_gadget_checked = current_time
        self.is_super_ready = False
        if current_time - self.time_since_super_checked > self.super_treshold:
            self.is_super_ready = self.check_if_super_ready(frame)
            self.time_since_super_checked = current_time

        movement = self.loop(brawler, data, current_time)

        # if data:
        #     # Record scene data
        #     self.scene_data.append({
        #         'frame_number': len(self.scene_data),
        #         'player': data.get('player', []),
        #         'enemy': data.get('enemy', []),
        #         'wall': data.get('wall', []),
        #         'movement': movement,
        #     })

    def generate_visualization(self, output_filename='visualization.mp4'):
        import cv2
        import numpy as np

        frame_size = (1920, 1080)  # Adjust as needed
        fps = 10

        # Initialize VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_filename, fourcc, fps, frame_size)

        for frame_data in self.scene_data:
            # Create a blank image
            img = np.zeros((frame_size[1], frame_size[0], 3), np.uint8)

            # Scale factors if needed
            scale_x = frame_size[0] / 1920
            scale_y = frame_size[1] / 1080

            if frame_data['wall']:
                # Draw walls
                for wall in frame_data['wall']:
                    x1, y1, x2, y2 = map(int, wall)
                    x1 = int(x1 * scale_x)
                    y1 = int(y1 * scale_y)
                    x2 = int(x2 * scale_x)
                    y2 = int(y2 * scale_y)
                    cv2.rectangle(img, (x1, y1), (x2, y2), (128, 128, 128), -1)  # Gray walls

            if frame_data['enemy']:
                # Draw enemies
                for enemy in frame_data['enemy']:
                    x1, y1, x2, y2 = map(int, enemy)
                    x1 = int(x1 * scale_x)
                    y1 = int(y1 * scale_y)
                    x2 = int(x2 * scale_x)
                    y2 = int(y2 * scale_y)
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), -1)  # Red enemies

            if frame_data['player']:
                # Draw player
                for player in frame_data['player']:
                    x1, y1, x2, y2 = map(int, player)
                    x1 = int(x1 * scale_x)
                    y1 = int(y1 * scale_y)
                    x2 = int(x2 * scale_x)
                    y2 = int(y2 * scale_y)
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), -1)  # Green player

            # Draw movement decision
            movement = frame_data['movement']
            direction = self.movement_to_direction(movement)
            cv2.putText(img, f'Movement: {direction}', (10, frame_size[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1)

            # Write frame to video
            out.write(img)

        out.release()

    @staticmethod
    def movement_to_direction(movement):
        mapping = {
            'w': 'up',
            'a': 'left',
            's': 'down',
            'd': 'right',
            'wa': 'up-left',
            'aw': 'up-left',
            'wd': 'up-right',
            'dw': 'up-right',
            'sa': 'down-left',
            'as': 'down-left',
            'sd': 'down-right',
            'ds': 'down-right',
        }
        movement = movement.lower()
        movement = ''.join(sorted(movement))
        return mapping.get(movement, 'idle' if movement == '' else movement)

import json
import os

CHAR_PATH = "saves/characters/"


def ensure_folder():
    os.makedirs(CHAR_PATH, exist_ok=True)


def get_character_path(name: str):
    return f"{CHAR_PATH}{name.lower()}.json"


def save_character(data: dict):
    ensure_folder()

    path = get_character_path(data["name"])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def load_character(name: str):
    path = get_character_path(name)

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def character_exists(name: str):
    return os.path.exists(get_character_path(name))
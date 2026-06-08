import json
import os

BASE_PATH = "saves/guilds"


def normalize_name(name: str) -> str:
    return " ".join(w.capitalize() for w in name.strip().split())


def get_character_folder(guild_id: int | str):
    return os.path.join(BASE_PATH, str(guild_id), "characters")


def ensure_folder(guild_id: int | str):
    os.makedirs(get_character_folder(guild_id), exist_ok=True)


def safe_file_name(name: str) -> str:
    return name.lower().replace(" ", "_")


def get_character_path(name: str, guild_id: int | str):
    name = normalize_name(name)
    return os.path.join(get_character_folder(guild_id), f"{safe_file_name(name)}.json")


def save_character(data: dict, guild_id: int | str):
    ensure_folder(guild_id)

    path = get_character_path(data["name"], guild_id)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_character(name: str, guild_id: int | str):
    path = get_character_path(name, guild_id)

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def character_exists(name: str, guild_id: int | str):
    return os.path.exists(get_character_path(name, guild_id))


def list_characters(guild_id: int | str):
    folder = get_character_folder(guild_id)

    if not os.path.exists(folder):
        return []

    result = []
    for file in os.listdir(folder):
        if file.endswith(".json"):
            result.append(file[:-5].replace("_", " ").title())

    return sorted(result)
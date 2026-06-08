import json
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def normalize_id(value: str) -> str:
    return value.strip().lower()


def load_item(item_id: str):
    return load_json("data/items.json").get(normalize_id(item_id))


def load_ability(ability_id: str):
    return load_json("data/abilities.json").get(normalize_id(ability_id))


def load_weapon(weapon_id: str):
    return load_json("data/weapons.json").get(normalize_id(weapon_id))


def load_skill_map():
    return load_json("data/skills.json")
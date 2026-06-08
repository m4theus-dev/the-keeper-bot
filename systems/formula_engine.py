import random
import re

from systems.database_loader import load_json, load_skill_map


DEFAULT_SKILL_MAP = {
    "ATHLETICS": "STR",
    "ACROBATICS": "DEX",
    "SLEIGHT_OF_HAND": "DEX",
    "STEALTH": "DEX",
    "ARCANA": "INT",
    "HISTORY": "INT",
    "INVESTIGATION": "INT",
    "NATURE": "INT",
    "RELIGION": "INT",
    "ANIMAL_HANDLING": "WIS",
    "INSIGHT": "WIS",
    "MEDICINE": "WIS",
    "PERCEPTION": "WIS",
    "SURVIVAL": "WIS",
    "DECEPTION": "CHA",
    "INTIMIDATION": "CHA",
    "PERFORMANCE": "CHA",
    "PERSUASION": "CHA",
}

DICE_PATTERN = re.compile(r"(\d+)d(\d+)")
VAR_PATTERN = re.compile(r"\b(STR|DEX|CON|INT|WIS|CHA|LEVEL|PROF)\b", re.IGNORECASE)
SKILL_PATTERN = re.compile(r"SKILL:([A-Z_ ]+)", re.IGNORECASE)


def normalize_skill_key(skill: str) -> str:
    return skill.strip().upper().replace(" ", "_")


def roll_dice(n: int, sides: int):
    return [random.randint(1, sides) for _ in range(n)]


def get_mod(value: int) -> int:
    return (int(value) - 10) // 2


def get_skill_map() -> dict:
    loaded = load_skill_map()
    if not loaded:
        return DEFAULT_SKILL_MAP

    normalized = {}
    for key, attr in loaded.items():
        normalized[normalize_skill_key(str(key))] = str(attr).upper().strip()
    return normalized


def get_skill_bonus(character: dict, skill_name: str):
    skill_key = normalize_skill_key(skill_name)
    skill_map = get_skill_map()

    if skill_key not in skill_map:
        raise KeyError(f"Unknown skill: {skill_name}")

    attr_key = skill_map[skill_key]
    attrs = character.get("attributes", {})
    skills = character.get("skills", {})

    raw_attr = int(attrs.get(attr_key, 10))
    attr_mod = get_mod(raw_attr)
    skill_level = int(skills.get(skill_key, 0))
    prof_bonus = int(character.get("prof_bonus", 2))
    total_bonus = attr_mod + (skill_level * prof_bonus)

    detail = {
        "skill": skill_key,
        "attribute": attr_key,
        "raw": raw_attr,
        "mod": attr_mod,
        "skill_level": skill_level,
        "prof_bonus": prof_bonus,
        "bonus": total_bonus,
    }

    return total_bonus, detail


def _resolve_weapon_placeholder(formula: str, context: dict | None):
    if not context:
        return formula

    weapon_formula = context.get("weapon_formula")
    if not weapon_formula:
        return formula

    formula = re.sub(r"\bweapon_damage\b", f"({weapon_formula})", formula, flags=re.IGNORECASE)
    formula = re.sub(r"\bweapon\b", f"({weapon_formula})", formula, flags=re.IGNORECASE)
    return formula


def evaluate_formula(formula: str, character: dict, context: dict | None = None):
    original = formula.strip()
    context = context or {}

    formula = _resolve_weapon_placeholder(original, context)

    variables = {}
    skills = {}

    def replace_skill(match):
        skill_key = normalize_skill_key(match.group(1))
        bonus, detail = get_skill_bonus(character, skill_key)
        skills[skill_key] = detail
        return str(bonus)

    formula = SKILL_PATTERN.sub(replace_skill, formula)

    attrs = character.get("attributes", {})

    def get_attr(name: str):
        try:
            return int(attrs.get(name, 10))
        except (TypeError, ValueError):
            return 10

    var_map = {
        "STR": get_mod(get_attr("STR")),
        "DEX": get_mod(get_attr("DEX")),
        "CON": get_mod(get_attr("CON")),
        "INT": get_mod(get_attr("INT")),
        "WIS": get_mod(get_attr("WIS")),
        "CHA": get_mod(get_attr("CHA")),
        "LEVEL": int(character.get("level", 1)),
        "PROF": int(character.get("prof_bonus", 2)),
    }

    def replace_var(match):
        key = match.group(1).upper()
        value = var_map.get(key, 0)
        if key in {"LEVEL", "PROF"}:
            variables[key] = {"raw": None, "mod": value}
        else:
            raw = get_attr(key)
            variables[key] = {"raw": raw, "mod": value}
        return str(value)

    formula = VAR_PATTERN.sub(replace_var, formula)

    dice_log = []

    def replace_dice(match):
        n = int(match.group(1))
        sides = int(match.group(2))

        rolls = roll_dice(n, sides)
        total = sum(rolls)

        dice_log.append({
            "expr": f"{n}d{sides}",
            "rolls": rolls,
            "total": total,
        })

        return str(total)

    formula = DICE_PATTERN.sub(replace_dice, formula)

    allowed = "0123456789+-*/(). "
    if any(c not in allowed for c in formula):
        raise ValueError("Invalid formula")

    total = eval(formula, {"__builtins__": {}}, {})

    return {
        "formula": original,
        "final_expression": formula,
        "final": formula,
        "variables": variables,
        "skills": skills,
        "dice": dice_log,
        "total": total,
    }
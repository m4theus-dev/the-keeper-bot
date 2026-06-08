import re

from systems.formula_engine import evaluate_formula


def normalize_id(value: str) -> str:
    return value.strip().lower()


def weapon_matches_requirement(weapon_data: dict, ability_data: dict) -> bool:
    required_tags = [str(tag).lower() for tag in ability_data.get("weapon_tags", []) if tag]
    if not required_tags:
        return True

    weapon_tags = [str(tag).lower() for tag in weapon_data.get("tags", [])]
    weapon_type = str(weapon_data.get("type", "")).lower()

    return any(tag in weapon_tags or tag == weapon_type for tag in required_tags)


def select_weapon(character: dict, weapons_db: dict, ability_data: dict | None = None, preferred_weapon: str | None = None):
    owned = []
    for key in character.get("weapons", []):
        owned.append(normalize_id(key))
    for key in character.get("items", []):
        owned.append(normalize_id(key))

    owned = list(dict.fromkeys(owned))

    if preferred_weapon:
        preferred = normalize_id(preferred_weapon)
        if preferred in owned and preferred in weapons_db:
            weapon_data = weapons_db[preferred]
            if not ability_data or weapon_matches_requirement(weapon_data, ability_data):
                return preferred, weapon_data
        return None, None

    for weapon_id in owned:
        if weapon_id not in weapons_db:
            continue

        weapon_data = weapons_db[weapon_id]
        if ability_data and not weapon_matches_requirement(weapon_data, ability_data):
            continue

        return weapon_id, weapon_data

    return None, None


def _resolve_formula(formula: str, character: dict, weapon_data: dict | None = None):
    context = {}
    if weapon_data:
        weapon_formula = weapon_data.get("damage") or weapon_data.get("value")
        if weapon_formula:
            context["weapon_formula"] = weapon_formula

    return evaluate_formula(formula, character, context=context)


def execute_action(character: dict, data: dict, weapon_data: dict | None = None):
    if not isinstance(data, dict):
        return {"error": "Invalid data block."}

    if data.get("requires_weapon") and weapon_data is None:
        return {"error": "This action requires a weapon."}

    steps = data.get("steps")
    if isinstance(steps, list) and steps:
        step_results = []
        total = 0

        for index, step in enumerate(steps, start=1):
            repeat = int(step.get("repeat", 1) or 1)

            for rep in range(repeat):
                step_result = execute_action(character, step, weapon_data=weapon_data)
                if step_result.get("error"):
                    return step_result

                step_result["step"] = index
                step_result["repeat"] = rep + 1
                step_results.append(step_result)

                if step_result.get("final") is not None:
                    total += int(step_result["final"])

        return {
            "attempt": None,
            "value": None,
            "final": total,
            "steps": step_results,
        }

    attempt_formula = data.get("attempt")
    value_formula = data.get("value") or data.get("damage")

    if not attempt_formula and not value_formula:
        return {"error": "Action has no attempt or value defined."}

    result = {
        "attempt": None,
        "value": None,
        "final": None,
    }

    if attempt_formula:
        result["attempt"] = _resolve_formula(attempt_formula, character, weapon_data)

    if value_formula:
        result["value"] = _resolve_formula(value_formula, character, weapon_data)

    if result["value"] is not None:
        result["final"] = result["value"]["total"]
    elif result["attempt"] is not None:
        result["final"] = result["attempt"]["total"]

    return result
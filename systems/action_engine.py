import re
from systems.formula_engine import evaluate_formula


def normalize_id(value: str) -> str:
    return value.strip().lower()


def weapon_matches_requirement(weapon_data: dict, ability_data: dict) -> bool:
    required_tags = [
        str(tag).lower()
        for tag in ability_data.get("weapon_tags", [])
        if tag
    ]

    if not required_tags:
        return True

    weapon_tags = [
        str(tag).lower()
        for tag in weapon_data.get("weapon_tags", [])
    ]

    weapon_type = str(weapon_data.get("type", "")).lower()

    # OR logic: ANY match is valid
    return any(
        tag in weapon_tags or tag == weapon_type
        for tag in required_tags
    )


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
        context["weapon_damage"] = weapon_data.get("damage")
        context["weapon_attempt"] = weapon_data.get("attempt")

    return evaluate_formula(formula, character, context=context)


def _resolve_value(value: str, character: dict, weapon_data: dict | None = None):
    """
    Handles special keyword: 'weapon'
    """
    if value == "weapon":
        if not weapon_data:
            return None

        return {
            "total": None,
            "weapon_damage": weapon_data.get("damage"),
            "weapon_attempt": weapon_data.get("attempt"),
            "weapon": weapon_data
        }

    return _resolve_formula(value, character, weapon_data)


def execute_action(character: dict, data: dict, weapon_data: dict | None = None):
    if not isinstance(data, dict):
        return {"error": "Invalid data block."}

    if data.get("requires_weapon") and weapon_data is None:
        return {"error": "This action requires a weapon."}

    steps = data.get("steps")

    # =========================
    # MULTI STEP SYSTEM
    # =========================
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

    # =========================
    # SINGLE ACTION
    # =========================
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
        result["value"] = _resolve_value(value_formula, character, weapon_data)

        # If weapon is used, override with weapon damage
        if value_formula == "weapon" and weapon_data:
            result["value"] = {
                "total": None,
                "weapon_damage": weapon_data.get("damage"),
                "weapon_attempt": weapon_data.get("attempt"),
                "weapon": weapon_data
            }

    if result["value"] is not None and isinstance(result["value"], dict) and "total" in result["value"] and result["value"]["total"] is not None:
        result["final"] = result["value"]["total"]

    elif result["attempt"] is not None:
        result["final"] = result["attempt"]["total"]

    return result
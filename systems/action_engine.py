import re
from systems.formula_engine import evaluate_formula


# =========================
# NORMALIZE
# =========================

def normalize_id(value: str) -> str:
    return value.strip().lower()


# =========================
# WEAPON VALIDATION
# =========================

def weapon_matches_requirement(weapon_data: dict, ability_data: dict) -> bool:
    required_tags = [
        str(tag).lower()
        for tag in ability_data.get("weapon_tags", [])
        if tag
    ]

    if not required_tags:
        return True

    weapon_tags = [str(tag).lower() for tag in weapon_data.get("tags", [])]
    weapon_type = str(weapon_data.get("type", "")).lower()

    return any(tag in weapon_tags or tag == weapon_type for tag in required_tags)


# =========================
# WEAPON SELECTOR (INVENTORY ONLY)
# =========================

def select_weapon(character: dict, weapons_db: dict, ability_data: dict | None = None):
    """
    Picks ANY weapon from inventory or weapons list.
    DOES NOT require equip system.
    """

    owned = []

    for w in character.get("weapons", []):
        owned.append(normalize_id(w))

    for i in character.get("items", []):
        owned.append(normalize_id(i))

    # remove duplicates while preserving order
    owned = list(dict.fromkeys(owned))

    for weapon_id in owned:
        if weapon_id not in weapons_db:
            continue

        weapon_data = weapons_db[weapon_id]

        if ability_data and not weapon_matches_requirement(weapon_data, ability_data):
            continue

        return weapon_id, weapon_data

    return None, None


# =========================
# FORMULA RESOLVER
# =========================

def _resolve_formula(formula: str, character: dict, weapon_data: dict | None = None):
    """
    Handles:
    - normal formulas (1d20+STR)
    - weapon placeholder
    """

    if not isinstance(formula, str):
        return None

    # 🔥 SPECIAL CASE: weapon damage injection
    if formula.strip().lower() == "weapon":
        if weapon_data:
            weapon_formula = weapon_data.get("damage") or weapon_data.get("value")
            if weapon_formula:
                return evaluate_formula(weapon_formula, character)

        return None

    return evaluate_formula(formula, character)


# =========================
# CORE ACTION EXECUTOR
# =========================

def execute_action(character: dict, data: dict, weapons_db: dict | None = None):
    """
    Main action engine:
    - supports steps
    - supports attempt/value/damage
    - supports weapon injection
    """

    if not isinstance(data, dict):
        return {"error": "Invalid action data."}

    weapons_db = weapons_db or {}

    # =========================
    # REQUIRE WEAPON CHECK
    # =========================
    if data.get("requires_weapon"):
        _, weapon_data = select_weapon(character, weapons_db, data)
        if not weapon_data:
            return {"error": "This action requires a valid weapon in inventory."}
    else:
        _, weapon_data = select_weapon(character, weapons_db, data)

    # =========================
    # STEPS SYSTEM (MULTI ACTION)
    # =========================
    steps = data.get("steps")

    if isinstance(steps, list) and len(steps) > 0:

        step_results = []
        total = 0

        for i, step in enumerate(steps, start=1):

            repeat = int(step.get("repeat", 1) or 1)

            for r in range(repeat):

                result = execute_action(character, step, weapons_db)

                if result.get("error"):
                    return result

                result["step"] = i
                result["repeat"] = r + 1

                step_results.append(result)

                if result.get("final") is not None:
                    total += int(result["final"])

        return {
            "attempt": None,
            "value": None,
            "final": total,
            "steps": step_results
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
        "final": None
    }

    # =========================
    # ATTEMPT ROLL
    # =========================
    if attempt_formula:
        result["attempt"] = _resolve_formula(
            attempt_formula,
            character,
            weapon_data
        )

    # =========================
    # VALUE / DAMAGE ROLL
    # =========================
    if value_formula:
        result["value"] = _resolve_formula(
            value_formula,
            character,
            weapon_data
        )

    # =========================
    # FINAL RESULT
    # =========================
    if result["value"] is not None:
        result["final"] = result["value"]["total"]

    elif result["attempt"] is not None:
        result["final"] = result["attempt"]["total"]

    return result
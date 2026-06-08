from systems.formula_engine import evaluate_formula


def normalize_id(value: str) -> str:
    return str(value).strip().lower()


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
        for tag in (weapon_data.get("tags") or weapon_data.get("weapon_tags") or [])
    ]
    weapon_type = str(weapon_data.get("type", "")).lower()

    return any(tag in weapon_tags or tag == weapon_type for tag in required_tags)


def action_uses_weapon(data: dict) -> bool:
    if not isinstance(data, dict):
        return False

    if data.get("requires_weapon"):
        return True

    if data.get("weapon_tags"):
        return True

    for key in ("attempt", "value", "damage"):
        val = data.get(key)
        if isinstance(val, str) and normalize_id(val) == "weapon":
            return True

    steps = data.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if action_uses_weapon(step):
                return True

    return False


def select_weapon(
    character: dict,
    weapons_db: dict,
    ability_data: dict | None = None,
    preferred_weapon: str | None = None,
):
    owned = []

    for key in character.get("weapons", []):
        owned.append(normalize_id(key))

    for key in character.get("items", []):
        owned.append(normalize_id(key))

    owned = list(dict.fromkeys(owned))

    def is_valid_weapon(weapon_id: str):
        if weapon_id not in weapons_db:
            return False, None

        weapon_data = weapons_db[weapon_id]

        if ability_data and not weapon_matches_requirement(weapon_data, ability_data):
            return False, None

        return True, weapon_data

    if preferred_weapon:
        preferred = normalize_id(preferred_weapon)
        if preferred in owned:
            ok, weapon_data = is_valid_weapon(preferred)
            if ok:
                return preferred, weapon_data

    equipped = character.get("equipped_weapon")
    if equipped:
        equipped = normalize_id(equipped)
        if equipped in owned:
            ok, weapon_data = is_valid_weapon(equipped)
            if ok:
                return equipped, weapon_data

    for weapon_id in owned:
        ok, weapon_data = is_valid_weapon(weapon_id)
        if ok:
            return weapon_id, weapon_data

    return None, None


def _resolve_formula(formula: str, character: dict, weapon_data: dict | None = None):
    context = {}

    if weapon_data:
        weapon_formula = weapon_data.get("damage") or weapon_data.get("value")
        if weapon_formula:
            context["weapon_formula"] = weapon_formula

    return evaluate_formula(formula, character, context=context)


def execute_action(
    character: dict,
    data: dict,
    weapons_db: dict | None = None,
    preferred_weapon: str | None = None,
):
    if not isinstance(data, dict):
        return {"error": "Invalid data block."}

    weapons_db = weapons_db or {}

    needs_weapon = action_uses_weapon(data)

    weapon_id = None
    weapon_data = None

    if needs_weapon or preferred_weapon is not None:
        weapon_id, weapon_data = select_weapon(
            character,
            weapons_db,
            ability_data=data,
            preferred_weapon=preferred_weapon,
        )

    if data.get("requires_weapon") and not weapon_data:
        return {"error": "This action requires a valid weapon in inventory."}

    if needs_weapon and not weapon_data:
        return {"error": "This action needs a matching weapon in inventory."}

    steps = data.get("steps")

    if isinstance(steps, list) and steps:
        step_results = []
        total = 0

        for index, step in enumerate(steps, start=1):
            repeat = int(step.get("repeat", 1) or 1)

            for rep in range(repeat):
                child = execute_action(
                    character,
                    step,
                    weapons_db=weapons_db,
                    preferred_weapon=weapon_id,
                )

                if child.get("error"):
                    return child

                child["step"] = index
                child["repeat"] = rep + 1
                step_results.append(child)

                if child.get("final") is not None:
                    total += int(child["final"])

        return {
            "weapon_id": weapon_id,
            "weapon_data": weapon_data,
            "attempt": None,
            "value": None,
            "final": total,
            "steps": step_results,
        }

    attempt_formula = data.get("attempt")
    value_formula = data.get("value") or data.get("damage")

    if value_formula == "weapon":
        if not weapon_data:
            return {"error": "This action needs a matching weapon in inventory."}
        value_formula = weapon_data.get("damage") or weapon_data.get("value")

    if not attempt_formula and not value_formula:
        return {"error": "Action has no attempt or value defined."}

    result = {
        "weapon_id": weapon_id,
        "weapon_data": weapon_data,
        "attempt": None,
        "value": None,
        "final": None,
    }

    if attempt_formula:
        result["attempt"] = _resolve_formula(attempt_formula, character)

    if value_formula:
        result["value"] = _resolve_formula(value_formula, character)

    if result["value"] is not None:
        result["final"] = result["value"]["total"]
    elif result["attempt"] is not None:
        result["final"] = result["attempt"]["total"]

    return result
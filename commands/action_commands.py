import discord
from discord.ext import commands

from systems.save_system import load_character, save_character
from systems.database_loader import load_item, load_ability, load_weapon
from systems.formula_engine import (
    evaluate_formula,
    get_skill_map,
    normalize_skill_key,
)
from systems.action_engine import execute_action, select_weapon


def normalize_name(name: str):
    return " ".join(w.capitalize() for w in name.strip().split())


def normalize_id(value: str) -> str:
    return value.strip().lower()


def pretty_id(value: str) -> str:
    return value.replace("_", " ").title()


def is_admin(ctx) -> bool:
    return ctx.author.guild_permissions.administrator


def owns_any(character: dict, entry_id: str, list_names=("items", "abilities", "weapons")) -> bool:
    entry_id = normalize_id(entry_id)
    for list_name in list_names:
        if entry_id in [normalize_id(v) for v in character.get(list_name, [])]:
            return True
    return False


def format_roll_block(roll_result: dict) -> str:
    lines = [
        f"**Formula:** `{roll_result['formula']}`",
        f"**Expression:** `{roll_result['final_expression']}`",
    ]

    if roll_result.get("skills"):
        skill_lines = []
        for key, detail in roll_result["skills"].items():
            skill_lines.append(
                f"**{key}**: {detail['attribute']} {detail['raw']} → `{detail['bonus']:+d}` "
                f"(prof {detail['skill_level']})"
            )
        lines.append("**Skills:**")
        lines.extend(skill_lines)

    if roll_result.get("variables"):
        var_lines = []
        for key, detail in roll_result["variables"].items():
            raw = detail["raw"]
            if raw is None:
                var_lines.append(f"**{key}**: `{detail['mod']:+d}`")
            else:
                var_lines.append(f"**{key}**: {raw} → `{detail['mod']:+d}`")
        lines.append("**Variables:**")
        lines.extend(var_lines)

    if roll_result.get("dice"):
        dice_lines = []
        for die in roll_result["dice"]:
            dice_lines.append(f"`{die['expr']}` → `{die['rolls']}` = `{die['total']}`")
        lines.append("**Dice:**")
        lines.extend(dice_lines)

    lines.append(f"**Total:** `{roll_result['total']}`")
    return "\n".join(lines)


def add_roll_field(embed: discord.Embed, title: str, roll_result: dict):
    embed.add_field(
        name=title,
        value=format_roll_block(roll_result),
        inline=False,
    )


def build_data_info_embed(title: str, color: discord.Color, entry_id: str, data: dict):
    embed = discord.Embed(
        title=title,
        color=color,
    )

    embed.add_field(name="ID", value=f"`{entry_id}`", inline=False)
    embed.add_field(name="Type", value=f"`{data.get('type', 'none')}`", inline=True)

    if data.get("description"):
        embed.add_field(name="Description", value=data["description"], inline=False)

    if data.get("attempt"):
        embed.add_field(name="Attempt", value=f"`{data['attempt']}`", inline=False)

    if data.get("value"):
        embed.add_field(name="Value", value=f"`{data['value']}`", inline=False)

    if data.get("damage"):
        embed.add_field(name="Damage", value=f"`{data['damage']}`", inline=False)

    if data.get("requires_weapon") is not None:
        embed.add_field(name="Requires Weapon", value=str(bool(data["requires_weapon"])), inline=True)

    if data.get("weapon_tags"):
        embed.add_field(name="Weapon Tags", value=", ".join(data["weapon_tags"]), inline=False)

    return embed


def setup_action_commands(bot):

    @bot.command(name="roll")
    async def roll(ctx, name: str, *, formula: str):
        char = load_character(normalize_name(name))

        if not char:
            return await ctx.send("❌ Character not found.")

        try:
            result = evaluate_formula(formula, char)
        except (ValueError, KeyError) as e:
            return await ctx.send(f"❌ {e}")

        embed = discord.Embed(
            title=f"🎲 Roll — {char['name']}",
            color=discord.Color.gold(),
        )

        add_roll_field(embed, "Result", result)
        await ctx.send(embed=embed)

    @bot.command(name="check", aliases=["skillcheck"])
    async def check(ctx, name: str, skill: str, dc: int = None):
        char = load_character(normalize_name(name))

        if not char:
            return await ctx.send("❌ Character not found.")

        skill_key = normalize_skill_key(skill)
        skill_map = get_skill_map()

        if skill_key not in skill_map:
            valid = ", ".join(sorted(skill_map.keys()))
            return await ctx.send(f"❌ Unknown skill. Valid skills: `{valid}`")

        try:
            result = evaluate_formula(f"1d20+SKILL:{skill_key}", char)
        except (ValueError, KeyError) as e:
            return await ctx.send(f"❌ {e}")

        success = None
        if dc is not None:
            success = result["total"] >= dc

        embed = discord.Embed(
            title=f"🎯 Check — {char['name']}",
            color=discord.Color.green() if success is True else discord.Color.red() if success is False else discord.Color.gold(),
        )
        embed.add_field(name="Skill", value=f"`{skill_key}`", inline=False)

        detail = result.get("skills", {}).get(skill_key)
        if detail:
            embed.add_field(
                name="Breakdown",
                value=(
                    f"Attribute: `{detail['attribute']}`\n"
                    f"Raw: `{detail['raw']}` → Mod `{detail['mod']:+d}`\n"
                    f"Skill level: `{detail['skill_level']}`\n"
                    f"Proficiency bonus: `{detail['prof_bonus']:+d}`\n"
                    f"Total skill bonus: `{detail['bonus']:+d}`"
                ),
                inline=False,
            )

        add_roll_field(embed, "Roll", result)

        if dc is not None:
            embed.add_field(name="DC", value=f"`{dc}`", inline=True)
            embed.add_field(
                name="Outcome",
                value="✅ Success" if success else "❌ Fail",
                inline=True,
            )

        await ctx.send(embed=embed)

    @bot.command(name="use")
    async def use(ctx, name: str, item: str, dc: int = None):
        char = load_character(normalize_name(name))

        if not char:
            return await ctx.send("❌ Character not found.")

        item_id = normalize_id(item)
        if item_id not in [normalize_id(v) for v in char.get("items", [])]:
            return await ctx.send("❌ Item not owned.")

        data = load_item(item_id)
        if not data:
            return await ctx.send("❌ Item not found in database.")

        try:
            result = execute_action(char, data)
        except (ValueError, KeyError) as e:
            return await ctx.send(f"❌ {e}")

        if result.get("error"):
            return await ctx.send(f"❌ {result['error']}")

        embed = discord.Embed(
            title=f"🎒 Use — {data.get('name', pretty_id(item_id))}",
            description=data.get("description", ""),
            color=discord.Color.green(),
        )

        if result.get("attempt"):
            add_roll_field(embed, "Attempt", result["attempt"])

        if result.get("value"):
            add_roll_field(embed, "Value", result["value"])

        if result.get("steps"):
            step_lines = []
            for step in result["steps"]:
                step_line = [f"Step {step['step']}"]
                if step.get("attempt"):
                    step_line.append(f"ATK `{step['attempt']['total']}`")
                if step.get("value"):
                    step_line.append(f"VAL `{step['value']['total']}`")
                step_lines.append(" | ".join(step_line))
            embed.add_field(name="Steps", value="\n".join(step_lines), inline=False)

        if dc is not None and result.get("attempt"):
            success = result["attempt"]["total"] >= dc
            embed.add_field(name="DC", value=f"`{dc}`", inline=True)
            embed.add_field(name="Outcome", value="✅ Success" if success else "❌ Fail", inline=True)
        elif dc is not None and not result.get("attempt"):
            embed.add_field(name="DC", value=f"`{dc}`", inline=True)
            embed.add_field(name="Note", value="No attempt roll defined; DC ignored.", inline=False)

        embed.add_field(name="Final", value=f"`{result['final']}`", inline=False)

        await ctx.send(embed=embed)

    @bot.command(name="cast")
    async def cast(ctx, name: str, ability: str, dc: int = None):
        char = load_character(normalize_name(name))

        if not char:
            return await ctx.send("❌ Character not found.")

        ability_id = normalize_id(ability)
        if ability_id not in [normalize_id(v) for v in char.get("abilities", [])]:
            return await ctx.send("❌ Ability not learned.")

        data = load_ability(ability_id)
        if not data:
            return await ctx.send("❌ Ability not found in database.")

        weapons_db = {k: v for k, v in load_weapon.__globals__["load_json"]("data/weapons.json").items()} if False else None
        # ^ not used here; weapon selection is done below using a fresh load for clarity
        from systems.database_loader import load_json
        weapons_db = load_json("data/weapons.json")

        weapon_id, weapon_data = select_weapon(char, weapons_db, ability_data=data)

        needs_weapon_context = bool(data.get("requires_weapon")) or any(
            "weapon" in str(data.get(field, "")).lower() for field in ("attempt", "value", "damage")
        )

        if needs_weapon_context and weapon_data is None:
            return await ctx.send("❌ This ability requires a weapon, but none could be selected from the character inventory.")

        try:
            result = execute_action(char, data, weapons_db=weapon_data)
        except (ValueError, KeyError) as e:
            return await ctx.send(f"❌ {e}")

        if result.get("error"):
            return await ctx.send(f"❌ {result['error']}")

        embed = discord.Embed(
            title=f"🔮 Cast — {data.get('name', pretty_id(ability_id))}",
            description=data.get("description", ""),
            color=discord.Color.purple(),
        )

        if weapon_id:
            embed.add_field(name="Weapon Used", value=f"`{pretty_id(weapon_id)}`", inline=False)

        if result.get("attempt"):
            add_roll_field(embed, "Attempt", result["attempt"])

        if result.get("value"):
            add_roll_field(embed, "Value", result["value"])

        if result.get("steps"):
            step_lines = []
            for step in result["steps"]:
                step_line = [f"Step {step['step']}"]
                if step.get("attempt"):
                    step_line.append(f"ATK `{step['attempt']['total']}`")
                if step.get("value"):
                    step_line.append(f"VAL `{step['value']['total']}`")
                step_lines.append(" | ".join(step_line))
            embed.add_field(name="Steps", value="\n".join(step_lines), inline=False)

        if dc is not None and result.get("attempt"):
            success = result["attempt"]["total"] >= dc
            embed.add_field(name="DC", value=f"`{dc}`", inline=True)
            embed.add_field(name="Outcome", value="✅ Success" if success else "❌ Fail", inline=True)
        elif dc is not None and not result.get("attempt"):
            embed.add_field(name="DC", value=f"`{dc}`", inline=True)
            embed.add_field(name="Note", value="No attempt roll defined; DC ignored.", inline=False)

        embed.add_field(name="Final", value=f"`{result['final']}`", inline=False)

        await ctx.send(embed=embed)

    @bot.command(name="attack")
    async def attack(ctx, name: str, weapon: str, ac: int = None):
        char = load_character(normalize_name(name))

        if not char:
            return await ctx.send("❌ Character not found.")

        weapon_id = normalize_id(weapon)
        owned_weapons = [normalize_id(v) for v in char.get("weapons", [])]
        owned_items = [normalize_id(v) for v in char.get("items", [])]

        if weapon_id not in owned_weapons and weapon_id not in owned_items:
            return await ctx.send("❌ Weapon not owned.")

        data = load_weapon(weapon_id)
        if not data:
            return await ctx.send("❌ Weapon not found in database.")

        try:
            result = execute_action(char, data, weapons_db=data)
        except (ValueError, KeyError) as e:
            return await ctx.send(f"❌ {e}")

        if result.get("error"):
            return await ctx.send(f"❌ {result['error']}")

        success = None
        if ac is not None and result.get("attempt"):
            success = result["attempt"]["total"] >= ac

        embed = discord.Embed(
            title=f"⚔️ Attack — {data.get('name', pretty_id(weapon_id))}",
            description=data.get("description", ""),
            color=discord.Color.red() if success is False else discord.Color.gold(),
        )

        if result.get("attempt"):
            add_roll_field(embed, "Attempt", result["attempt"])

        if result.get("value"):
            add_roll_field(embed, "Damage", result["value"])

        if ac is not None and result.get("attempt"):
            embed.add_field(name="AC", value=f"`{ac}`", inline=True)
            embed.add_field(name="Outcome", value="✅ Hit" if success else "❌ Miss", inline=True)
        elif ac is not None and not result.get("attempt"):
            embed.add_field(name="AC", value=f"`{ac}`", inline=True)
            embed.add_field(name="Note", value="No attack roll defined; AC ignored.", inline=False)

        embed.add_field(name="Final", value=f"`{result['final']}`", inline=False)

        await ctx.send(embed=embed)

    @bot.command(name="additem")
    async def additem_cmd(ctx, name: str, item: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ You don't have permission.")

        char = load_character(normalize_name(name))
        if not char:
            return await ctx.send("❌ Character not found.")

        item_id = normalize_id(item)
        if not load_item(item_id):
            return await ctx.send("❌ Item not found in database.")

        char.setdefault("items", [])
        if item_id in [normalize_id(v) for v in char["items"]]:
            return await ctx.send("⚠ Item already in inventory.")

        char["items"].append(item_id)
        save_character(char)

        await ctx.send(f"📦 `{item_id}` added to **{char['name']}**.")

    @bot.command(name="removeitem")
    async def removeitem_cmd(ctx, name: str, item: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ You don't have permission.")

        char = load_character(normalize_name(name))
        if not char:
            return await ctx.send("❌ Character not found.")

        item_id = normalize_id(item)
        char.setdefault("items", [])

        if item_id not in [normalize_id(v) for v in char["items"]]:
            return await ctx.send("❌ Item not in inventory.")

        char["items"] = [v for v in char["items"] if normalize_id(v) != item_id]
        save_character(char)

        await ctx.send(f"🗑️ `{item_id}` removed from **{char['name']}**.")

    @bot.command(name="addability")
    async def addability_cmd(ctx, name: str, ability: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ You don't have permission.")

        char = load_character(normalize_name(name))
        if not char:
            return await ctx.send("❌ Character not found.")

        ability_id = normalize_id(ability)
        if not load_ability(ability_id):
            return await ctx.send("❌ Ability not found in database.")

        char.setdefault("abilities", [])
        if ability_id in [normalize_id(v) for v in char["abilities"]]:
            return await ctx.send("⚠ Ability already learned.")

        char["abilities"].append(ability_id)
        save_character(char)

        await ctx.send(f"✨ `{ability_id}` added to **{char['name']}**.")

    @bot.command(name="removeability")
    async def removeability_cmd(ctx, name: str, ability: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ You don't have permission.")

        char = load_character(normalize_name(name))
        if not char:
            return await ctx.send("❌ Character not found.")

        ability_id = normalize_id(ability)
        char.setdefault("abilities", [])

        if ability_id not in [normalize_id(v) for v in char["abilities"]]:
            return await ctx.send("❌ Ability not learned.")

        char["abilities"] = [v for v in char["abilities"] if normalize_id(v) != ability_id]
        save_character(char)

        await ctx.send(f"🗑️ `{ability_id}` removed from **{char['name']}**.")

    @bot.command(name="addweapon")
    async def addweapon_cmd(ctx, name: str, weapon: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ You don't have permission.")

        char = load_character(normalize_name(name))
        if not char:
            return await ctx.send("❌ Character not found.")

        weapon_id = normalize_id(weapon)
        if not load_weapon(weapon_id):
            return await ctx.send("❌ Weapon not found in database.")

        char.setdefault("weapons", [])
        if weapon_id in [normalize_id(v) for v in char["weapons"]]:
            return await ctx.send("⚠ Weapon already owned.")

        char["weapons"].append(weapon_id)
        save_character(char)

        await ctx.send(f"⚔️ `{weapon_id}` added to **{char['name']}**.")

    @bot.command(name="removeweapon")
    async def removeweapon_cmd(ctx, name: str, weapon: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ You don't have permission.")

        char = load_character(normalize_name(name))
        if not char:
            return await ctx.send("❌ Character not found.")

        weapon_id = normalize_id(weapon)
        char.setdefault("weapons", [])

        if weapon_id not in [normalize_id(v) for v in char["weapons"]]:
            return await ctx.send("❌ Weapon not owned.")

        char["weapons"] = [v for v in char["weapons"] if normalize_id(v) != weapon_id]
        save_character(char)

        await ctx.send(f"🗑️ `{weapon_id}` removed from **{char['name']}**.")

    @bot.command(name="iteminfo")
    async def iteminfo_cmd(ctx, item: str):
        item_id = normalize_id(item)
        data = load_item(item_id)

        if not data:
            return await ctx.send("❌ Item not found in database.")

        await ctx.send(embed=build_data_info_embed(
            f"📦 Item — {data.get('name', pretty_id(item_id))}",
            discord.Color.green(),
            item_id,
            data,
        ))

    @bot.command(name="abilityinfo")
    async def abilityinfo_cmd(ctx, ability: str):
        ability_id = normalize_id(ability)
        data = load_ability(ability_id)

        if not data:
            return await ctx.send("❌ Ability not found in database.")

        await ctx.send(embed=build_data_info_embed(
            f"✨ Ability — {data.get('name', pretty_id(ability_id))}",
            discord.Color.purple(),
            ability_id,
            data,
        ))

    @bot.command(name="weaponinfo")
    async def weaponinfo_cmd(ctx, weapon: str):
        weapon_id = normalize_id(weapon)
        data = load_weapon(weapon_id)

        if not data:
            return await ctx.send("❌ Weapon not found in database.")

        await ctx.send(embed=build_data_info_embed(
            f"⚔️ Weapon — {data.get('name', pretty_id(weapon_id))}",
            discord.Color.dark_red(),
            weapon_id,
            data,
        ))
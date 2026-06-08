import discord
from discord.ext import commands

from systems.save_system import load_character, save_character
from systems.database_loader import load_item, load_ability, load_weapon, load_json
from systems.formula_engine import (
    evaluate_formula,
    get_skill_map,
    normalize_skill_key,
)
from systems.action_engine import execute_action


def normalize_name(name: str) -> str:
    return " ".join(w.capitalize() for w in name.strip().split())


def normalize_id(value: str) -> str:
    return str(value).strip().lower()


def pretty_id(value: str) -> str:
    return str(value).replace("_", " ").title()


def is_admin(ctx) -> bool:
    return ctx.author.guild_permissions.administrator


# =========================
# GUILD SAVE/LOAD WRAPPERS
# =========================

def get_guild_id(ctx):
    guild = getattr(getattr(ctx, "message", None), "guild", None)
    if guild is None:
        guild = getattr(ctx, "guild", None)

    return str(getattr(guild, "id", "global"))


def load_guild_character(ctx, name: str):
    guild_id = get_guild_id(ctx)
    name = normalize_name(name)

    try:
        return load_character(name, guild_id)
    except TypeError:
        return load_character(f"{guild_id}:{name}")


def save_guild_character(ctx, char: dict):
    guild_id = get_guild_id(ctx)

    try:
        return save_character(char, guild_id)
    except TypeError:
        return save_character(char)


def format_roll_block(roll_result: dict) -> str:
    final_expression = roll_result.get("final_expression", roll_result.get("final", ""))
    lines = [
        f"**Formula:** `{roll_result.get('formula', '')}`",
        f"**Expression:** `{final_expression}`",
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

    tags = data.get("weapon_tags") or data.get("tags")
    if tags:
        embed.add_field(name="Weapon Tags", value=", ".join(tags), inline=False)

    return embed


def load_weapons_db():
    return load_json("data/weapons.json")


def build_step_lines(result: dict):
    lines = []
    for step in result.get("steps", []):
        parts = [f"Step {step.get('step', '?')}"]
        if step.get("attempt") and step["attempt"].get("total") is not None:
            parts.append(f"ATK `{step['attempt']['total']}`")
        if step.get("value") and step["value"].get("total") is not None:
            parts.append(f"VAL `{step['value']['total']}`")
        if step.get("final") is not None:
            parts.append(f"FINAL `{step['final']}`")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def build_weapon_embed(title: str, weapon_id: str, weapon_data: dict, equipped: bool = False):
    embed = discord.Embed(
        title=title,
        color=discord.Color.gold(),
    )

    embed.add_field(name="Weapon", value=f"`{pretty_id(weapon_id)}`", inline=True)
    embed.add_field(name="Type", value=f"`{weapon_data.get('type', 'none')}`", inline=True)
    embed.add_field(name="Equipped", value="Yes" if equipped else "No", inline=True)

    if weapon_data.get("damage"):
        embed.add_field(name="Damage", value=f"`{weapon_data['damage']}`", inline=False)

    if weapon_data.get("attempt"):
        embed.add_field(name="Attack Roll", value=f"`{weapon_data['attempt']}`", inline=False)

    tags = weapon_data.get("weapon_tags") or weapon_data.get("tags")
    if tags:
        embed.add_field(name="Tags", value=", ".join(tags), inline=False)

    return embed


def setup_action_commands(bot):

    @bot.command(name="roll")
    async def roll(ctx, name: str, *, formula: str):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        try:
            result = evaluate_formula(formula, char)
        except (ValueError, KeyError) as e:
            return await ctx.send(embed=discord.Embed(
                title="❌ Roll Error",
                description=str(e),
                color=discord.Color.red(),
            ))

        embed = discord.Embed(
            title=f"🎲 Roll — {char['name']}",
            color=discord.Color.gold(),
        )
        add_roll_field(embed, "Result", result)
        await ctx.send(embed=embed)

    @bot.command(name="check", aliases=["skillcheck"])
    async def check(ctx, name: str, skill: str, dc: int = None):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        skill_key = normalize_skill_key(skill)
        skill_map = get_skill_map()

        if skill_key not in skill_map:
            valid = ", ".join(sorted(skill_map.keys()))
            return await ctx.send(embed=discord.Embed(
                title="❌ Unknown Skill",
                description=f"Valid skills: `{valid}`",
                color=discord.Color.red(),
            ))

        try:
            result = evaluate_formula(f"1d20+SKILL:{skill_key}", char)
        except (ValueError, KeyError) as e:
            return await ctx.send(embed=discord.Embed(
                title="❌ Check Error",
                description=str(e),
                color=discord.Color.red(),
            ))

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
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        item_id = normalize_id(item)
        if item_id not in [normalize_id(v) for v in char.get("items", [])]:
            return await ctx.send(embed=discord.Embed(
                title="❌ Item Not Owned",
                description="That item is not in the character inventory.",
                color=discord.Color.red(),
            ))

        data = load_item(item_id)
        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Item Not Found",
                description="That item does not exist in the database.",
                color=discord.Color.red(),
            ))

        weapons_db = load_weapons_db()

        try:
            result = execute_action(char, data, weapons_db=weapons_db)
        except (ValueError, KeyError) as e:
            return await ctx.send(embed=discord.Embed(
                title="❌ Use Error",
                description=str(e),
                color=discord.Color.red(),
            ))

        if result.get("error"):
            return await ctx.send(embed=discord.Embed(
                title="❌ Use Error",
                description=result["error"],
                color=discord.Color.red(),
            ))

        embed = discord.Embed(
            title=f"🎒 Use — {data.get('name', pretty_id(item_id))}",
            description=data.get("description", ""),
            color=discord.Color.green(),
        )

        if result.get("weapon_id") and result.get("weapon_data"):
            embed.add_field(
                name="Weapon Used",
                value=f"`{pretty_id(result['weapon_id'])}`",
                inline=False,
            )

        if result.get("attempt"):
            add_roll_field(embed, "Attempt", result["attempt"])

        if result.get("value"):
            add_roll_field(embed, "Value", result["value"])

        if result.get("steps"):
            step_text = build_step_lines(result)
            if step_text:
                embed.add_field(name="Steps", value=step_text, inline=False)

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
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        ability_id = normalize_id(ability)
        if ability_id not in [normalize_id(v) for v in char.get("abilities", [])]:
            return await ctx.send(embed=discord.Embed(
                title="❌ Ability Not Learned",
                description="That ability is not known by the character.",
                color=discord.Color.red(),
            ))

        data = load_ability(ability_id)
        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Ability Not Found",
                description="That ability does not exist in the database.",
                color=discord.Color.red(),
            ))

        weapons_db = load_weapons_db()

        try:
            result = execute_action(char, data, weapons_db=weapons_db)
        except (ValueError, KeyError) as e:
            return await ctx.send(embed=discord.Embed(
                title="❌ Cast Error",
                description=str(e),
                color=discord.Color.red(),
            ))

        if result.get("error"):
            return await ctx.send(embed=discord.Embed(
                title="❌ Cast Error",
                description=result["error"],
                color=discord.Color.red(),
            ))

        embed = discord.Embed(
            title=f"🔮 Cast — {data.get('name', pretty_id(ability_id))}",
            description=data.get("description", ""),
            color=discord.Color.purple(),
        )

        if result.get("weapon_id") and result.get("weapon_data"):
            embed.add_field(
                name="Weapon Used",
                value=f"`{pretty_id(result['weapon_id'])}`",
                inline=False,
            )

        if result.get("attempt"):
            add_roll_field(embed, "Attempt", result["attempt"])

        if result.get("value"):
            add_roll_field(embed, "Value", result["value"])

        if result.get("steps"):
            step_text = build_step_lines(result)
            if step_text:
                embed.add_field(name="Steps", value=step_text, inline=False)

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
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        weapon_id = normalize_id(weapon)
        owned_weapons = [normalize_id(v) for v in char.get("weapons", [])]
        owned_items = [normalize_id(v) for v in char.get("items", [])]

        if weapon_id not in owned_weapons and weapon_id not in owned_items:
            return await ctx.send(embed=discord.Embed(
                title="❌ Weapon Not Owned",
                description="That weapon is not in the character inventory.",
                color=discord.Color.red(),
            ))

        data = load_weapon(weapon_id)
        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Weapon Not Found",
                description="That weapon does not exist in the database.",
                color=discord.Color.red(),
            ))

        weapons_db = load_weapons_db()

        try:
            result = execute_action(
                char,
                data,
                weapons_db=weapons_db,
                preferred_weapon=weapon_id,
            )
        except (ValueError, KeyError) as e:
            return await ctx.send(embed=discord.Embed(
                title="❌ Attack Error",
                description=str(e),
                color=discord.Color.red(),
            ))

        if result.get("error"):
            return await ctx.send(embed=discord.Embed(
                title="❌ Attack Error",
                description=result["error"],
                color=discord.Color.red(),
            ))

        success = None
        if ac is not None and result.get("attempt"):
            success = result["attempt"]["total"] >= ac

        embed = discord.Embed(
            title=f"⚔️ Attack — {pretty_id(weapon_id)}",
            description=data.get("description", ""),
            color=discord.Color.red() if success is False else discord.Color.gold(),
        )

        embed.add_field(name="Weapon", value=f"`{pretty_id(weapon_id)}`", inline=True)
        embed.add_field(name="Type", value=f"`{data.get('type', 'none')}`", inline=True)

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

    @bot.command(name="equip")
    async def equip(ctx, name: str, weapon: str):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        weapon_id = normalize_id(weapon)
        owned = [normalize_id(v) for v in char.get("weapons", [])] + [normalize_id(v) for v in char.get("items", [])]

        if weapon_id not in owned:
            return await ctx.send(embed=discord.Embed(
                title="❌ Weapon Not Owned",
                description="You can only equip a weapon that is already in the inventory.",
                color=discord.Color.red(),
            ))

        data = load_weapon(weapon_id)
        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Weapon Not Found",
                description="That weapon does not exist in the database.",
                color=discord.Color.red(),
            ))

        char["equipped_weapon"] = weapon_id
        save_guild_character(ctx, char)

        await ctx.send(embed=build_weapon_embed(
            title="⚔️ Weapon Equipped",
            weapon_id=weapon_id,
            weapon_data=data,
            equipped=True,
        ))

    @bot.command(name="unequip")
    async def unequip(ctx, name: str):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        char["equipped_weapon"] = None
        save_guild_character(ctx, char)

        await ctx.send(embed=discord.Embed(
            title="🫳 Weapon Unequipped",
            description=f"**{char['name']}** is no longer using an equipped weapon.",
            color=discord.Color.orange(),
        ))

    @bot.command(name="equipment")
    async def equipment(ctx, name: str):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        equipped = char.get("equipped_weapon")
        weapons_inv = char.get("weapons", [])
        items_inv = char.get("items", [])

        embed = discord.Embed(
            title=f"🧍 Equipment — {char['name']}",
            color=discord.Color.blurple(),
        )

        if equipped:
            equipped_data = load_weapon(normalize_id(equipped))
            if equipped_data:
                embed.add_field(
                    name="Equipped Weapon",
                    value=f"`{pretty_id(equipped)}`",
                    inline=False,
                )
                if equipped_data.get("damage"):
                    embed.add_field(
                        name="Equipped Damage",
                        value=f"`{equipped_data['damage']}`",
                        inline=False,
                    )
                if equipped_data.get("attempt"):
                    embed.add_field(
                        name="Equipped Attack",
                        value=f"`{equipped_data['attempt']}`",
                        inline=False,
                    )
            else:
                embed.add_field(name="Equipped Weapon", value=f"`{pretty_id(equipped)}`", inline=False)
        else:
            embed.add_field(name="Equipped Weapon", value="None", inline=False)

        embed.add_field(
            name="Weapons in Inventory",
            value="\n".join(f"• `{pretty_id(v)}`" for v in weapons_inv) or "None",
            inline=False,
        )

        embed.add_field(
            name="Items in Inventory",
            value="\n".join(f"• `{pretty_id(v)}`" for v in items_inv) or "None",
            inline=False,
        )

        await ctx.send(embed=embed)

    @bot.command(name="additem")
    async def additem_cmd(ctx, name: str, item: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        item_id = normalize_id(item)
        if not load_item(item_id):
            return await ctx.send(embed=discord.Embed(
                title="❌ Item Not Found",
                description="That item does not exist in the database.",
                color=discord.Color.red(),
            ))

        char.setdefault("items", [])
        if item_id in [normalize_id(v) for v in char["items"]]:
            return await ctx.send(embed=discord.Embed(
                title="⚠️ Already Owned",
                description="That item is already in the inventory.",
                color=discord.Color.gold(),
            ))

        char["items"].append(item_id)
        save_guild_character(ctx, char)

        await ctx.send(embed=discord.Embed(
            title="📦 Item Added",
            description=f"`{pretty_id(item_id)}` added to **{char['name']}**.",
            color=discord.Color.green(),
        ))

    @bot.command(name="removeitem")
    async def removeitem_cmd(ctx, name: str, item: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        item_id = normalize_id(item)
        char.setdefault("items", [])

        if item_id not in [normalize_id(v) for v in char["items"]]:
            return await ctx.send(embed=discord.Embed(
                title="❌ Item Not Owned",
                description="That item is not in the inventory.",
                color=discord.Color.red(),
            ))

        char["items"] = [v for v in char["items"] if normalize_id(v) != item_id]
        if normalize_id(char.get("equipped_weapon", "")) == item_id:
            char["equipped_weapon"] = None

        save_guild_character(ctx, char)

        await ctx.send(embed=discord.Embed(
            title="🗑️ Item Removed",
            description=f"`{pretty_id(item_id)}` removed from **{char['name']}**.",
            color=discord.Color.orange(),
        ))

    @bot.command(name="addability")
    async def addability_cmd(ctx, name: str, ability: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        ability_id = normalize_id(ability)
        if not load_ability(ability_id):
            return await ctx.send(embed=discord.Embed(
                title="❌ Ability Not Found",
                description="That ability does not exist in the database.",
                color=discord.Color.red(),
            ))

        char.setdefault("abilities", [])
        if ability_id in [normalize_id(v) for v in char["abilities"]]:
            return await ctx.send(embed=discord.Embed(
                title="⚠️ Already Learned",
                description="That ability is already learned.",
                color=discord.Color.gold(),
            ))

        char["abilities"].append(ability_id)
        save_guild_character(ctx, char)

        await ctx.send(embed=discord.Embed(
            title="✨ Ability Added",
            description=f"`{pretty_id(ability_id)}` added to **{char['name']}**.",
            color=discord.Color.green(),
        ))

    @bot.command(name="removeability")
    async def removeability_cmd(ctx, name: str, ability: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        ability_id = normalize_id(ability)
        char.setdefault("abilities", [])

        if ability_id not in [normalize_id(v) for v in char["abilities"]]:
            return await ctx.send(embed=discord.Embed(
                title="❌ Ability Not Learned",
                description="That ability is not learned.",
                color=discord.Color.red(),
            ))

        char["abilities"] = [v for v in char["abilities"] if normalize_id(v) != ability_id]
        save_guild_character(ctx, char)

        await ctx.send(embed=discord.Embed(
            title="🗑️ Ability Removed",
            description=f"`{pretty_id(ability_id)}` removed from **{char['name']}**.",
            color=discord.Color.orange(),
        ))

    @bot.command(name="addweapon")
    async def addweapon_cmd(ctx, name: str, weapon: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        weapon_id = normalize_id(weapon)
        if not load_weapon(weapon_id):
            return await ctx.send(embed=discord.Embed(
                title="❌ Weapon Not Found",
                description="That weapon does not exist in the database.",
                color=discord.Color.red(),
            ))

        char.setdefault("weapons", [])
        if weapon_id in [normalize_id(v) for v in char["weapons"]]:
            return await ctx.send(embed=discord.Embed(
                title="⚠️ Already Owned",
                description="That weapon is already in the inventory.",
                color=discord.Color.gold(),
            ))

        char["weapons"].append(weapon_id)
        save_guild_character(ctx, char)

        await ctx.send(embed=discord.Embed(
            title="⚔️ Weapon Added",
            description=f"`{pretty_id(weapon_id)}` added to **{char['name']}**.",
            color=discord.Color.green(),
        ))

    @bot.command(name="removeweapon")
    async def removeweapon_cmd(ctx, name: str, weapon: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send(embed=discord.Embed(
                title="❌ Character Not Found",
                description="The character does not exist.",
                color=discord.Color.red(),
            ))

        weapon_id = normalize_id(weapon)
        char.setdefault("weapons", [])

        if weapon_id not in [normalize_id(v) for v in char["weapons"]]:
            return await ctx.send(embed=discord.Embed(
                title="❌ Weapon Not Owned",
                description="That weapon is not in the inventory.",
                color=discord.Color.red(),
            ))

        char["weapons"] = [v for v in char["weapons"] if normalize_id(v) != weapon_id]
        if normalize_id(char.get("equipped_weapon", "")) == weapon_id:
            char["equipped_weapon"] = None

        save_guild_character(ctx, char)

        await ctx.send(embed=discord.Embed(
            title="🗑️ Weapon Removed",
            description=f"`{pretty_id(weapon_id)}` removed from **{char['name']}**.",
            color=discord.Color.orange(),
        ))

    @bot.command(name="iteminfo")
    async def iteminfo_cmd(ctx, item: str):
        item_id = normalize_id(item)
        data = load_item(item_id)

        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Item Not Found",
                description="That item does not exist in the database.",
                color=discord.Color.red(),
            ))

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
            return await ctx.send(embed=discord.Embed(
                title="❌ Ability Not Found",
                description="That ability does not exist in the database.",
                color=discord.Color.red(),
            ))

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
            return await ctx.send(embed=discord.Embed(
                title="❌ Weapon Not Found",
                description="That weapon does not exist in the database.",
                color=discord.Color.red(),
            ))

        await ctx.send(embed=build_data_info_embed(
            f"⚔️ Weapon — {data.get('name', pretty_id(weapon_id))}",
            discord.Color.dark_red(),
            weapon_id,
            data,
        ))
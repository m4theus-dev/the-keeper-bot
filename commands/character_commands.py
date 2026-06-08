import json
import os
import discord
from discord.ext import commands

from systems.save_system import (
    save_character,
    load_character,
    character_exists,
    get_character_path,
)
from systems.formula_engine import (
    get_mod,
    get_skill_bonus,
    get_skill_map,
    normalize_skill_key,
)


def is_admin(ctx) -> bool:
    return ctx.author.guild_permissions.administrator


def normalize_name(name: str):
    return " ".join(w.capitalize() for w in name.strip().split())


def pretty_id(value: str) -> str:
    return str(value).replace("_", " ").title()


def pretty_name_from_filename(filename: str):
    name = filename.replace(".json", "").replace("_", " ")
    return " ".join(w.capitalize() for w in name.split())


def parse_value(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def ensure_defaults(char: dict):
    char.setdefault("name", "Unknown")
    char.setdefault("attributes", {
        "STR": 10,
        "DEX": 10,
        "CON": 10,
        "INT": 10,
        "WIS": 10,
        "CHA": 10,
    })
    char.setdefault("skills", {})
    char.setdefault("items", [])
    char.setdefault("abilities", [])
    char.setdefault("weapons", [])
    char.setdefault("equipped_weapon", None)
    char.setdefault("level", 1)
    char.setdefault("prof_bonus", 2)
    char.setdefault("hp", 20)
    char.setdefault("max_hp", 20)
    char.setdefault("initiative", 0)
    return char


def recalc_derived_stats(char: dict, refill_hp: bool = False):
    char = ensure_defaults(char)

    level = max(int(char.get("level", 1)), 1)
    attrs = char.get("attributes", {})

    con_mod = get_mod(int(attrs.get("CON", 10)))
    dex_mod = get_mod(int(attrs.get("DEX", 10)))

    char["level"] = level
    char["prof_bonus"] = 2 + ((level - 1) // 4)
    char["initiative"] = dex_mod
    char["max_hp"] = max(20 + (con_mod * level), 1)

    if refill_hp:
        char["hp"] = char["max_hp"]
    else:
        current_hp = int(char.get("hp", char["max_hp"]))
        char["hp"] = max(0, min(current_hp, char["max_hp"]))

    return char


def build_sheet(data: dict):
    data = ensure_defaults(data)

    embed = discord.Embed(
        title=f"📜 Character Sheet — {data['name']}",
        color=discord.Color.blurple(),
    )

    attrs = data.get("attributes", {})
    skills = data.get("skills", {})
    items = data.get("items", [])
    abilities = data.get("abilities", [])
    weapons = data.get("weapons", [])
    equipped = data.get("equipped_weapon")

    attr_lines = []
    for key in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        raw = int(attrs.get(key, 10))
        attr_lines.append(f"**{key}**: {raw} ({get_mod(raw):+d})")

    embed.add_field(
        name="🧠 Attributes",
        value="\n".join(attr_lines),
        inline=False,
    )

    if skills:
        lines = []
        for s in sorted(skills.keys()):
            try:
                bonus, detail = get_skill_bonus(data, s)
                lvl = skills[s]
                lines.append(f"**{pretty_id(s)}** → L{lvl} | `{bonus:+d}`")
            except Exception:
                lines.append(f"**{pretty_id(s)}** → invalid")
        skill_value = "\n".join(lines)
    else:
        skill_value = "None"

    embed.add_field(
        name="🎯 Skills",
        value=skill_value,
        inline=False,
    )

    embed.add_field(
        name="🛡 Equipped Weapon",
        value=f"`{pretty_id(equipped)}`" if equipped else "None",
        inline=False,
    )

    embed.add_field(
        name="📦 Items",
        value="\n".join(f"• `{pretty_id(item)}`" for item in items) or "None",
        inline=True,
    )
    embed.add_field(
        name="⚔ Weapons",
        value="\n".join(f"• `{pretty_id(weapon)}`" for weapon in weapons) or "None",
        inline=True,
    )
    embed.add_field(
        name="✨ Abilities",
        value="\n".join(f"• `{pretty_id(ability)}`" for ability in abilities) or "None",
        inline=True,
    )

    embed.add_field(
        name="📊 Stats",
        value=(
            f"Level: {data.get('level', 1)}\n"
            f"HP: {data.get('hp', 0)} / {data.get('max_hp', 0)}\n"
            f"PROF: +{data.get('prof_bonus', 2)}\n"
            f"INIT: {data.get('initiative', 0):+d}"
        ),
        inline=False,
    )

    return embed


def setup_character_commands(bot):

    @bot.command(name="create")
    async def create(ctx, *, name: str):
        name = normalize_name(name)

        if character_exists(name):
            return await ctx.send(embed=discord.Embed(
                title="❌ Already Exists",
                description="That character already exists.",
                color=discord.Color.red(),
            ))

        data = {
            "name": name,
            "attributes": {
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            "skills": {},
            "items": [],
            "abilities": [],
            "weapons": [],
            "equipped_weapon": None,
            "level": 1,
            "prof_bonus": 2,
            "hp": 20,
            "max_hp": 20,
            "initiative": 0,
        }

        data = recalc_derived_stats(data, refill_hp=True)
        save_character(data)

        await ctx.send(embed=discord.Embed(
            title="✅ Character Created",
            description=f"**{name}** has entered the world.",
            color=discord.Color.green()
        ))

    @bot.command(name="sheet")
    async def sheet(ctx, *, name: str):
        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Not Found",
                description="That character does not exist.",
                color=discord.Color.red(),
            ))

        await ctx.send(embed=build_sheet(data))

    @bot.command(name="listchars")
    async def listchars(ctx):
        path = "saves/characters/"

        if not os.path.exists(path):
            return await ctx.send(embed=discord.Embed(
                title="📜 Character List",
                description="No characters found.",
                color=discord.Color.gold()
            ))

        files = [f for f in os.listdir(path) if f.endswith(".json")]

        if not files:
            return await ctx.send(embed=discord.Embed(
                title="📜 Character List",
                description="No characters found.",
                color=discord.Color.gold()
            ))

        names = [f"• `{pretty_name_from_filename(f)}`" for f in sorted(files)]

        embed = discord.Embed(
            title="📜 Character List",
            description="\n".join(names),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Total characters: {len(files)}")
        await ctx.send(embed=embed)

    @bot.command(name="edit")
    async def edit(ctx, name: str, field: str, *, value: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Not Found",
                description="That character does not exist.",
                color=discord.Color.red(),
            ))

        field = field.strip()
        if field.lower() == "name":
            return await ctx.send(embed=discord.Embed(
                title="❌ Not Allowed",
                description="Renaming characters is disabled.",
                color=discord.Color.red(),
            ))

        ref = data
        keys = field.split(".")

        for k in keys[:-1]:
            ref = ref.setdefault(k, {})

        ref[keys[-1]] = parse_value(value)

        if field == "level" or field.startswith("attributes."):
            data = recalc_derived_stats(data, refill_hp=False)

        save_character(data)

        await ctx.send(embed=discord.Embed(
            title="✏️ Character Updated",
            description=f"`{field}` updated for **{name}**.",
            color=discord.Color.orange()
        ))

    @bot.command(name="reload")
    async def reload(ctx, *, name: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Not Found",
                description="That character does not exist.",
                color=discord.Color.red(),
            ))

        data = recalc_derived_stats(data, refill_hp=True)
        save_character(data)

        await ctx.send(embed=discord.Embed(
            title="🔁 Character Reloaded",
            description=f"Derived stats recalculated for **{name}**.",
            color=discord.Color.blue()
        ))

    @bot.command(name="delete")
    async def delete(ctx, *, name: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        name = normalize_name(name)
        path = get_character_path(name)

        if not os.path.exists(path):
            return await ctx.send(embed=discord.Embed(
                title="❌ Not Found",
                description="That character does not exist.",
                color=discord.Color.red(),
            ))

        os.remove(path)

        await ctx.send(embed=discord.Embed(
            title="🗑️ Character Deleted",
            description=f"**{name}** has been removed.",
            color=discord.Color.red()
        ))

    @bot.command(name="setskill")
    async def setskill(ctx, name: str, skill: str, level: int):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        if level not in [0, 1, 2]:
            return await ctx.send(embed=discord.Embed(
                title="❌ Invalid Skill Level",
                description="Skill level must be 0, 1, or 2.",
                color=discord.Color.red(),
            ))

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Not Found",
                description="That character does not exist.",
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

        data.setdefault("skills", {})
        data["skills"][skill_key] = int(level)
        save_character(data)

        await ctx.send(embed=discord.Embed(
            title="🎯 Skill Updated",
            description=f"**{pretty_id(skill_key)}** set to level **{level}** for **{name}**.",
            color=discord.Color.blurple()
        ))

    @bot.command(name="removeskill")
    async def removeskill(ctx, name: str, skill: str):
        if not is_admin(ctx):
            return await ctx.send(embed=discord.Embed(
                title="⛔ No Permission",
                description="This command is admin only.",
                color=discord.Color.red(),
            ))

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Not Found",
                description="That character does not exist.",
                color=discord.Color.red(),
            ))

        skill_key = normalize_skill_key(skill)
        if skill_key not in data.get("skills", {}):
            return await ctx.send(embed=discord.Embed(
                title="❌ Skill Not Found",
                description="That skill is not set on the character.",
                color=discord.Color.red(),
            ))

        data["skills"].pop(skill_key, None)
        save_character(data)

        await ctx.send(embed=discord.Embed(
            title="🗑️ Skill Removed",
            description=f"**{pretty_id(skill_key)}** removed from **{name}**.",
            color=discord.Color.orange()
        ))

    @bot.command(name="skills")
    async def skills(ctx, *, name: str):
        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send(embed=discord.Embed(
                title="❌ Not Found",
                description="That character does not exist.",
                color=discord.Color.red(),
            ))

        skill_entries = data.get("skills", {})
        if not skill_entries:
            return await ctx.send(embed=discord.Embed(
                title=f"🎯 Skills — {name}",
                description="No skills set.",
                color=discord.Color.gold(),
            ))

        lines = []
        for s in sorted(skill_entries.keys()):
            try:
                bonus, detail = get_skill_bonus(data, s)
                lvl = int(skill_entries.get(s, 0))
                lines.append(f"**{pretty_id(s)}** → L{lvl} | `{bonus:+d}`")
            except Exception:
                lines.append(f"**{pretty_id(s)}** → invalid")

        embed = discord.Embed(
            title=f"🎯 Skills — {name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)
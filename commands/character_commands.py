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
from systems.formula_engine import get_mod, get_skill_bonus, get_skill_map, normalize_skill_key


def is_admin(ctx) -> bool:
    return ctx.author.guild_permissions.administrator


def normalize_name(name: str):
    return " ".join(w.capitalize() for w in name.strip().split())


def pretty_key(value: str) -> str:
    return value.replace("_", " ").title()


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
    skill_entries = data.get("skills", {})
    items = data.get("items", [])
    abilities = data.get("abilities", [])
    weapons = data.get("weapons", [])

    attr_lines = []
    for key in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        raw = int(attrs.get(key, 10))
        attr_lines.append(f"**{key}**: {raw} ({get_mod(raw):+d})")

    embed.add_field(
        name="🧠 Attributes",
        value="\n".join(attr_lines),
        inline=False,
    )

    if skill_entries:
        skill_lines = []
        for skill_name in sorted(skill_entries.keys()):
            try:
                bonus, detail = get_skill_bonus(data, skill_name)
                level = int(skill_entries.get(skill_name, 0))
                level_label = {
                    0: "Untrained",
                    1: "Proficient",
                    2: "Expertise",
                }.get(level, f"Level {level}")
                skill_lines.append(
                    f"**{skill_name}**: {level_label} → `{bonus:+d}` "
                    f"({detail['attribute']} {detail['raw']} → {detail['mod']:+d})"
                )
            except Exception:
                skill_lines.append(f"**{skill_name}**: invalid skill data")
        skill_value = "\n".join(skill_lines)
    else:
        skill_value = "None"

    embed.add_field(
        name="🎯 Skills",
        value=skill_value,
        inline=False,
    )

    embed.add_field(
        name="📦 Items",
        value="\n".join(f"• `{item}`" for item in items) or "None",
        inline=True,
    )
    embed.add_field(
        name="⚔ Weapons",
        value="\n".join(f"• `{weapon}`" for weapon in weapons) or "None",
        inline=True,
    )
    embed.add_field(
        name="✨ Abilities",
        value="\n".join(f"• `{ability}`" for ability in abilities) or "None",
        inline=True,
    )

    embed.add_field(
        name="📊 Stats",
        value=(
            f"**Level:** {data.get('level', 1)}\n"
            f"**HP:** {data.get('hp', 0)} / {data.get('max_hp', 0)}\n"
            f"**Proficiency:** +{data.get('prof_bonus', 2)}\n"
            f"**Initiative:** {data.get('initiative', 0):+d}"
        ),
        inline=False,
    )

    return embed


def setup_character_commands(bot):

    @bot.command(name="create")
    async def create(ctx, *, name: str):
        name = normalize_name(name)

        if character_exists(name):
            return await ctx.send("❌ Already exists.")

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
            return await ctx.send("❌ Not found.")

        await ctx.send(embed=build_sheet(data))

    @bot.command(name="edit")
    async def edit(ctx, name: str, field: str, *, value: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ You don't have permission.")

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Character not found.")

        field = field.strip()
        if field.lower() == "name":
            return await ctx.send("❌ Renaming characters is disabled. Create a new character instead.")

        keys = field.split(".")
        ref = data

        for key in keys[:-1]:
            if key not in ref or not isinstance(ref[key], dict):
                ref[key] = {}
            ref = ref[key]

        final_key = keys[-1]
        parsed_value = parse_value(value)

        ref[final_key] = parsed_value

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
            return await ctx.send("⛔ You don't have permission.")

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Character not found.")

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
            return await ctx.send("⛔ You don't have permission.")

        name = normalize_name(name)
        path = get_character_path(name)

        if not os.path.exists(path):
            return await ctx.send("❌ Character not found.")

        os.remove(path)

        await ctx.send(embed=discord.Embed(
            title="🗑️ Character Deleted",
            description=f"**{name}** has been removed.",
            color=discord.Color.red()
        ))

    @bot.command(name="setskill")
    async def setskill(ctx, name: str, skill: str, level: int):
        if not is_admin(ctx):
            return await ctx.send("⛔ You don't have permission.")

        if level not in [0, 1, 2]:
            return await ctx.send("❌ Skill level must be 0, 1 or 2.")

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Character not found.")

        skill_key = normalize_skill_key(skill)
        skill_map = get_skill_map()

        if skill_key not in skill_map:
            valid = ", ".join(sorted(skill_map.keys()))
            return await ctx.send(f"❌ Unknown skill. Valid skills: `{valid}`")

        data.setdefault("skills", {})
        data["skills"][skill_key] = int(level)
        save_character(data)

        await ctx.send(embed=discord.Embed(
            title="🎯 Skill Updated",
            description=f"**{skill_key}** set to level **{level}** for **{name}**.",
            color=discord.Color.blurple()
        ))

    @bot.command(name="removeskill")
    async def removeskill(ctx, name: str, skill: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ You don't have permission.")

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Character not found.")

        skill_key = normalize_skill_key(skill)
        if skill_key not in data.get("skills", {}):
            return await ctx.send("❌ Skill not found.")

        del data["skills"][skill_key]
        save_character(data)

        await ctx.send(embed=discord.Embed(
            title="🗑️ Skill Removed",
            description=f"**{skill_key}** removed from **{name}**.",
            color=discord.Color.orange()
        ))

    @bot.command(name="skills")
    async def skills(ctx, *, name: str):
        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Character not found.")

        skill_entries = data.get("skills", {})
        if not skill_entries:
            return await ctx.send("No skills set.")

        embed = discord.Embed(
            title=f"🎯 Skills — {name}",
            color=discord.Color.gold()
        )

        lines = []
        for skill_name in sorted(skill_entries.keys()):
            try:
                bonus, detail = get_skill_bonus(data, skill_name)
                level = int(skill_entries.get(skill_name, 0))
                level_label = {
                    0: "Untrained",
                    1: "Proficient",
                    2: "Expertise",
                }.get(level, f"Level {level}")
                lines.append(
                    f"**{skill_name}** → {level_label} | `{bonus:+d}` "
                    f"({detail['attribute']} {detail['raw']} → {detail['mod']:+d})"
                )
            except Exception:
                lines.append(f"**{skill_name}** → invalid skill data")

        embed.description = "\n".join(lines)
        await ctx.send(embed=embed)
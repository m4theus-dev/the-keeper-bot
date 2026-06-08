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


# =========================
# ADMIN CHECK
# =========================

def is_admin(ctx) -> bool:
    return ctx.author.guild_permissions.administrator


# =========================
# NORMALIZATION
# =========================

def normalize_name(name: str):
    return " ".join(w.capitalize() for w in name.strip().split())


def pretty_name_from_filename(filename: str) -> str:
    name = filename.replace(".json", "")
    return " ".join(w.capitalize() for w in name.split())


def parse_value(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


# =========================
# DEFAULTS
# =========================

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


# =========================
# SHEET
# =========================

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
                lines.append(
                    f"**{s}** → L{lvl} | `{bonus:+d}`"
                )
            except:
                lines.append(f"**{s}** → invalid")
        skill_value = "\n".join(lines)
    else:
        skill_value = "None"

    embed.add_field(
        name="🎯 Skills",
        value=skill_value,
        inline=False,
    )

    embed.add_field(name="📦 Items", value="\n".join(items) or "None", inline=True)
    embed.add_field(name="⚔ Weapons", value="\n".join(weapons) or "None", inline=True)
    embed.add_field(name="✨ Abilities", value="\n".join(abilities) or "None", inline=True)

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


# =========================
# COMMANDS
# =========================

def setup_character_commands(bot):

    # =========================
    # CREATE
    # =========================
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

        await ctx.send(f"✅ Created {name}")

    # =========================
    # SHEET
    # =========================
    @bot.command(name="sheet")
    async def sheet(ctx, *, name: str):
        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Not found.")

        await ctx.send(embed=build_sheet(data))

    # =========================
    # LIST CHARS (NEW)
    # =========================
    @bot.command(name="listchars")
    async def listchars(ctx):
        path = "saves/characters/"

        if not os.path.exists(path):
            return await ctx.send("No characters found.")

        files = [f for f in os.listdir(path) if f.endswith(".json")]

        if not files:
            return await ctx.send("No characters found.")

        embed = discord.Embed(
            title="📜 Character List",
            color=discord.Color.gold()
        )

        names = []
        for f in sorted(files):
            names.append(f"• {pretty_name_from_filename(f)}")

        embed.description = "\n".join(names)

        await ctx.send(embed=embed)

    # =========================
    # EDIT
    # =========================
    @bot.command(name="edit")
    async def edit(ctx, name: str, field: str, *, value: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ No permission.")

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Not found.")

        ref = data
        keys = field.split(".")

        for k in keys[:-1]:
            ref = ref.setdefault(k, {})

        ref[keys[-1]] = parse_value(value)

        save_character(data)
        await ctx.send("✅ Updated.")

    # =========================
    # RELOAD
    # =========================
    @bot.command(name="reload")
    async def reload(ctx, *, name: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ No permission.")

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Not found.")

        data = recalc_derived_stats(data, refill_hp=True)
        save_character(data)

        await ctx.send("🔁 Reloaded.")

    # =========================
    # DELETE
    # =========================
    @bot.command(name="delete")
    async def delete(ctx, *, name: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ No permission.")

        name = normalize_name(name)
        path = get_character_path(name)

        if not os.path.exists(path):
            return await ctx.send("❌ Not found.")

        os.remove(path)
        await ctx.send("🗑️ Deleted.")

    # =========================
    # SKILLS
    # =========================
    @bot.command(name="skills")
    async def skills(ctx, *, name: str):
        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Not found.")

        await ctx.send(embed=build_sheet(data))

    # =========================
    # SET SKILL
    # =========================
    @bot.command(name="setskill")
    async def setskill(ctx, name: str, skill: str, level: int):
        if not is_admin(ctx):
            return await ctx.send("⛔ No permission.")

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Not found.")

        data.setdefault("skills", {})
        data["skills"][skill.upper()] = level

        save_character(data)
        await ctx.send("🎯 Skill updated.")

    # =========================
    # REMOVE SKILL
    # =========================
    @bot.command(name="removeskill")
    async def removeskill(ctx, name: str, skill: str):
        if not is_admin(ctx):
            return await ctx.send("⛔ No permission.")

        name = normalize_name(name)
        data = load_character(name)

        if not data:
            return await ctx.send("❌ Not found.")

        data["skills"].pop(skill.upper(), None)

        save_character(data)
        await ctx.send("🗑️ Skill removed.")
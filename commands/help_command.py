import discord
from discord.ext import commands

from systems.formula_engine import get_skill_map


def normalize_topic(topic: str) -> str:
    return topic.strip().lower().replace("-", "_").replace(" ", "_")


COMMANDS_HELP = {
    "create": {
        "desc": "Creates a new character.",
        "usage": "/create <name>",
        "args": "name → character name (use quotes if needed)",
        "example": '/create "Ed Baiano"',
        "notes": "Starts with base attributes and default HP."
    },

    "sheet": {
        "desc": "Displays the full character sheet.",
        "usage": "/sheet <name>",
        "args": "name → character name",
        "example": '/sheet "Ed Baiano"',
        "notes": "Shows attributes, skills, items, weapons, abilities, and equipped weapon."
    },

    "edit": {
        "desc": "Edits character fields (admin only).",
        "usage": "/edit <name> <field> <value>",
        "args": "field → attributes.STR | level | hp etc.",
        "example": '/edit "Ed Baiano" attributes.STR 15',
        "notes": "Admin only. Direct data mutation."
    },

    "reload": {
        "desc": "Recalculates derived stats.",
        "usage": "/reload <name>",
        "args": "name → character name",
        "example": '/reload "Ed Baiano"',
        "notes": "Recomputes HP, initiative, and proficiency."
    },

    "delete": {
        "desc": "Deletes a character (admin only).",
        "usage": "/delete <name>",
        "args": "name → character name",
        "example": '/delete "Ed Baiano"',
        "notes": "Permanent deletion."
    },

    "listchars": {
        "desc": "Lists all saved characters.",
        "usage": "/listchars",
        "args": "none",
        "example": "/listchars",
        "notes": "Reads from saves/characters/"
    },

    "setskill": {
        "desc": "Sets skill proficiency level.",
        "usage": "/setskill <name> <skill> <level>",
        "args": "level → 0 (none), 1 (proficient), 2 (expertise)",
        "example": '/setskill "Ed Baiano" athletics 2',
        "notes": "Admin only."
    },

    "removeskill": {
        "desc": "Removes a skill.",
        "usage": "/removeskill <name> <skill>",
        "args": "skill → skill name",
        "example": '/removeskill "Ed Baiano" stealth',
        "notes": "Admin only."
    },

    "skills": {
        "desc": "Shows character skills.",
        "usage": "/skills <name>",
        "args": "name → character name",
        "example": '/skills "Ed Baiano"',
        "notes": "Uses the 0/1/2 proficiency system."
    },

    "check": {
        "desc": "Skill check (d20 + attribute + proficiency).",
        "usage": "/check <name> <skill> [DC]",
        "args": "skill → athletics, stealth, etc | DC optional",
        "example": '/check "Ed Baiano" acrobatics 15',
        "notes": "Uses the full skill mapping from data/skills.json."
    },

    "roll": {
        "desc": "Rolls a custom formula.",
        "usage": "/roll <name> <formula>",
        "args": "formula → STR, DEX, PROF, LEVEL, dice, SKILL:ATHLETICS",
        "example": '/roll "Ed Baiano" 1d20+DEX+PROF',
        "notes": "Supports dice, variables, and skill injection."
    },

    "use": {
        "desc": "Uses an item from inventory.",
        "usage": "/use <name> <item> [DC]",
        "args": "item → must exist in inventory | DC optional",
        "example": '/use "Ed Baiano" health_potion 12',
        "notes": "Reads attempt/value from items.json."
    },

    "cast": {
        "desc": "Casts an ability/spell.",
        "usage": "/cast <name> <ability> [DC]",
        "args": "ability → learned ability | DC optional",
        "example": '/cast "Ed Baiano" fireball 15',
        "notes": "Uses ability steps and weapon requirements when needed."
    },

    "attack": {
        "desc": "Attacks using a weapon.",
        "usage": "/attack <name> <weapon> [AC]",
        "args": "weapon → owned weapon | AC optional",
        "example": '/attack "Ed Baiano" longsword 15',
        "notes": "AC = Armor Class."
    },

    "equip": {
        "desc": "Equips a weapon.",
        "usage": "/equip <name> <weapon>",
        "args": "weapon → owned weapon",
        "example": '/equip "Ed Baiano" dagger',
        "notes": "Sets the active weapon used as priority for skills and attacks."
    },

    "unequip": {
        "desc": "Removes the equipped weapon.",
        "usage": "/unequip <name>",
        "args": "name → character name",
        "example": '/unequip "Ed Baiano"',
        "notes": "Does not remove the weapon from inventory."
    },

    "equipment": {
        "desc": "Shows current equipment.",
        "usage": "/equipment <name>",
        "args": "name → character name",
        "example": '/equipment "Ed Baiano"',
        "notes": "Shows equipped weapon and inventory weapons."
    },

    "additem": {
        "desc": "Adds item to character.",
        "usage": "/additem <name> <item>",
        "args": "item → from items.json",
        "example": '/additem "Ed Baiano" health_potion',
        "notes": "Admin only."
    },

    "removeitem": {
        "desc": "Removes item from character.",
        "usage": "/removeitem <name> <item>",
        "args": "item → inventory item",
        "example": '/removeitem "Ed Baiano" health_potion',
        "notes": "Admin only."
    },

    "addability": {
        "desc": "Adds ability to character.",
        "usage": "/addability <name> <ability>",
        "args": "ability → from abilities.json",
        "example": '/addability "Ed Baiano" fireball',
        "notes": "Admin only."
    },

    "removeability": {
        "desc": "Removes ability from character.",
        "usage": "/removeability <name> <ability>",
        "args": "ability → learned ability",
        "example": '/removeability "Ed Baiano" fireball',
        "notes": "Admin only."
    },

    "addweapon": {
        "desc": "Adds weapon to character.",
        "usage": "/addweapon <name> <weapon>",
        "args": "weapon → from weapons.json",
        "example": '/addweapon "Ed Baiano" longsword',
        "notes": "Admin only."
    },

    "removeweapon": {
        "desc": "Removes weapon from character.",
        "usage": "/removeweapon <name> <weapon>",
        "args": "weapon → inventory weapon",
        "example": '/removeweapon "Ed Baiano" longsword',
        "notes": "Admin only."
    },

    "iteminfo": {
        "desc": "Shows item data from database.",
        "usage": "/iteminfo <item>",
        "args": "item → items.json key",
        "example": "/iteminfo health_potion",
        "notes": "Displays attempt/value when available."
    },

    "abilityinfo": {
        "desc": "Shows ability data from database.",
        "usage": "/abilityinfo <ability>",
        "args": "ability → abilities.json key",
        "example": "/abilityinfo fireball",
        "notes": "Shows attempt, value, and requirements."
    },

    "weaponinfo": {
        "desc": "Shows weapon data from database.",
        "usage": "/weaponinfo <weapon>",
        "args": "weapon → weapons.json key",
        "example": "/weaponinfo longsword",
        "notes": "Shows attack and damage formulas."
    },
}


HELP_SECTIONS = {
    "core": {
        "title": "📜 Core System",
        "summary": "Character creation, editing, reload, deletion, and listing.",
        "commands": ["create", "sheet", "edit", "reload", "delete", "listchars"],
    },
    "skills": {
        "title": "🎯 Skills System",
        "summary": "Skill proficiency and checks.",
        "commands": ["setskill", "removeskill", "skills", "check"],
    },
    "combat": {
        "title": "⚔️ Combat System",
        "summary": "Rolls, attacks, item use, and casting.",
        "commands": ["roll", "use", "cast", "attack"],
    },
    "equipment": {
        "title": "🛡 Equipment System",
        "summary": "Equip, unequip, and inspect weapons.",
        "commands": ["equip", "unequip", "equipment"],
    },
    "data": {
        "title": "🗃️ Data System",
        "summary": "Manage items, abilities, and weapons.",
        "commands": ["additem", "removeitem", "addability", "removeability", "addweapon", "removeweapon"],
    },
    "info": {
        "title": "ℹ️ Database Info",
        "summary": "Inspect raw JSON data.",
        "commands": ["iteminfo", "abilityinfo", "weaponinfo"],
    },
}


def build_overview():
    embed = discord.Embed(
        title="📖 The Keeper — Help",
        description="Use `/help <section>` or `/help <command>`.",
        color=discord.Color.blue(),
    )

    for k, v in HELP_SECTIONS.items():
        embed.add_field(
            name=v["title"],
            value=f"{v['summary']}\n`/help {k}`",
            inline=False
        )

    return embed


def build_section(key):
    section = HELP_SECTIONS[key]

    embed = discord.Embed(
        title=section["title"],
        description=section["summary"],
        color=discord.Color.blurple()
    )

    for cmd in section["commands"]:
        info = COMMANDS_HELP[cmd]
        embed.add_field(
            name=f"/{cmd}",
            value=info["desc"],
            inline=False
        )

    if key == "skills":
        skill_map = get_skill_map()
        embed.add_field(
            name="Skill Mapping",
            value="\n".join([f"{k} → {v}" for k, v in skill_map.items()]),
            inline=False
        )

    if key == "combat":
        embed.add_field(
            name="Action Rules",
            value=(
                "`attempt` = test roll\n"
                "`value` / `damage` = effect or damage\n"
                "If `attempt` is missing, the command goes straight to `value`.\n"
                "If `value` is missing, only `attempt` is rolled.\n"
                "`DC` is difficulty class, `AC` is armor class."
            ),
            inline=False
        )

    if key == "equipment":
        embed.add_field(
            name="Priority",
            value=(
                "1. Equipped weapon\n"
                "2. Preferred weapon from the command\n"
                "3. First compatible weapon in inventory"
            ),
            inline=False
        )

    return embed


def build_command(key):
    cmd = COMMANDS_HELP[key]

    embed = discord.Embed(
        title=f"📘 /{key}",
        description=cmd["desc"],
        color=discord.Color.blurple()
    )

    embed.add_field(name="Usage", value=cmd["usage"], inline=False)
    embed.add_field(name="Arguments", value=cmd["args"], inline=False)
    embed.add_field(name="Example", value=cmd["example"], inline=False)

    if cmd.get("notes"):
        embed.add_field(name="Notes", value=cmd["notes"], inline=False)

    return embed


def setup_help(bot):

    @bot.command(name="help")
    async def help_cmd(ctx, *, topic: str = None):

        if not topic:
            return await ctx.send(embed=build_overview())

        key = normalize_topic(topic)

        if key in HELP_SECTIONS:
            return await ctx.send(embed=build_section(key))

        if key in COMMANDS_HELP:
            return await ctx.send(embed=build_command(key))

        await ctx.send(embed=discord.Embed(
            title="❌ Not Found",
            description="Use `/help` to see available sections.",
            color=discord.Color.red()
        ))
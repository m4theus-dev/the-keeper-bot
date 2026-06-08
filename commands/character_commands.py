import os
import discord

from systems.save_system import (
    save_character,
    load_character,
    character_exists,
    get_character_path,
)

# =========================
# ADMIN CHECK
# =========================

def is_admin(ctx: discord.Context) -> bool:
    return ctx.author.guild_permissions.administrator


# =========================
# QOL: NAME NORMALIZER
# =========================

def normalize_name(name: str) -> str:
    return " ".join(word.capitalize() for word in name.strip().split())


# =========================
# QOL: SAFE FILE NAME
# =========================

def safe_name(name: str) -> str:
    return name.lower().replace(" ", "_")


# =========================
# EMBED HELPERS
# =========================

def build_character_embed(data: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"📜 Character Sheet — {data['name']}",
        color=discord.Color.blurple()
    )

    attrs = data.get("attributes", {})
    attr_text = "\n".join([f"**{k}**: {v}" for k, v in attrs.items()]) or "None"

    skills = data.get("skills", {})
    skill_text = "\n".join([f"**{k}**: {v}" for k, v in skills.items()]) or "None"

    inventory = data.get("inventory", [])
    inv_text = ", ".join(inventory) if inventory else "Empty"

    embed.add_field(name="🧠 Attributes", value=attr_text, inline=False)
    embed.add_field(name="🎯 Skills", value=skill_text, inline=False)
    embed.add_field(name="🎒 Inventory", value=inv_text, inline=False)

    embed.add_field(
        name="📊 Stats",
        value=(
            f"**Level:** {data.get('level', 1)}\n"
            f"**HP:** {data.get('hp', 0)} / {data.get('max_hp', 0)}\n"
            f"**Proficiency:** +{data.get('prof_bonus', 0)}"
        ),
        inline=False
    )

    return embed


# =========================
# COMMANDS SETUP
# =========================

def setup_character_commands(bot):

    # =========================
    # UNKNOWN COMMAND FEEDBACK (QOL)
    # =========================
    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, discord.ext.commands.CommandNotFound):
            await ctx.send("❌ Command not found. Use `!help` to see available commands.")
            return

        raise error  # outros erros normais


    # =========================
    # CREATE CHARACTER
    # =========================
    @bot.command(name="create")
    async def create(ctx, name: str):

        name = " ".join(word.capitalize() for word in name.strip().split())
        file_name = safe_name(name)

        if character_exists(file_name):
            await ctx.send("❌ Character already exists.")
            return

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
            "abilities": [],
            "inventory": [],
            "level": 1,
            "prof_bonus": 2,
            "hp": 10,
            "max_hp": 10,
        }

        save_character(data)

        embed = discord.Embed(
            title="✅ Character Created",
            description=f"**{name}** has entered the world.",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)


    # =========================
    # DELETE CHARACTER (ADMIN ONLY)
    # =========================
    @bot.command(name="delete")
    async def delete(ctx, name: str):

        if not is_admin(ctx):
            await ctx.send("⛔ You don't have permission.")
            return

        name = normalize_name(name)
        path = get_character_path(name)

        if not os.path.exists(path):
            await ctx.send("❌ Character not found.")
            return

        os.remove(path)

        embed = discord.Embed(
            title="🗑️ Character Deleted",
            description=f"**{name}** has been removed.",
            color=discord.Color.red()
        )

        await ctx.send(embed=embed)


    # =========================
    # EDIT CHARACTER (ADMIN ONLY)
    # =========================
    @bot.command(name="edit")
    async def edit(ctx, name: str, field: str, value: str):

        if not is_admin(ctx):
            await ctx.send("⛔ You don't have permission.")
            return

        name = normalize_name(name)

        data = load_character(name)

        if not data:
            await ctx.send("❌ Character not found.")
            return

        keys = field.split(".")
        ref = data

        for k in keys[:-1]:
            if k not in ref:
                await ctx.send("❌ Invalid field path.")
                return
            ref = ref[k]

        final_key = keys[-1]

        if value.isdigit():
            value = int(value)

        ref[final_key] = value
        save_character(data)

        embed = discord.Embed(
            title="✏️ Character Updated",
            description=f"`{field}` updated for **{name}**.",
            color=discord.Color.orange()
        )

        await ctx.send(embed=embed)


    # =========================
    # VIEW CHARACTER SHEET
    # =========================
    @bot.command(name="sheet")
    async def sheet(ctx, name: str):

        name = normalize_name(name)

        data = load_character(name)

        if not data:
            await ctx.send("❌ Character not found.")
            return

        await ctx.send(embed=build_character_embed(data))


    # =========================
    # LIST ALL CHARACTERS
    # =========================
    @bot.command(name="listchars")
    async def listchars(ctx):

        folder = "saves/characters/"

        if not os.path.exists(folder):
            await ctx.send("No characters found.")
            return

        files = [
            f.replace(".json", "")
            for f in os.listdir(folder)
            if f.endswith(".json")
        ]

        if not files:
            await ctx.send("No characters found.")
            return


        def format_name(name: str) -> str:
            return " ".join(word.capitalize() for word in name.replace("_", " ").split())


        pretty_names = []
        for file_name in files:
            pretty_names.append(format_name(file_name))


        embed = discord.Embed(
            title="📚 Character List",
            description="\n".join([f"• **{n}**" for n in pretty_names]),
            color=discord.Color.blue()
        )

        embed.set_footer(text=f"Total characters: {len(pretty_names)}")

        await ctx.send(embed=embed)
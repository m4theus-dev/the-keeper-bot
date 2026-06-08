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


# =========================
# NORMALIZATION HELPERS
# =========================

def normalize_name(name: str) -> str:
    return " ".join(w.capitalize() for w in name.strip().split())


def normalize_id(value: str) -> str:
    return str(value).strip().lower()


def pretty_id(value: str) -> str:
    return str(value).replace("_", " ").title()


# =========================
# GUILD SAVE ISOLATION
# =========================
# Usa o ID da guilda onde a mensagem do comando foi enviada.
# Em DM, cai para "global".

def get_message_guild_id(ctx):
    guild = getattr(getattr(ctx, "message", None), "guild", None)
    if guild is None:
        guild = getattr(ctx, "guild", None)

    return str(getattr(guild, "id", "global"))


def load_guild_character(ctx, name: str):
    guild_id = get_message_guild_id(ctx)

    # Compatível com a assinatura nova: load_character(name, guild_id)
    try:
        return load_character(normalize_name(name), guild_id)
    except TypeError:
        # Fallback caso seu sistema ainda use chave única concatenada
        return load_character(f"{guild_id}:{normalize_name(name)}")


def save_guild_character(ctx, char: dict):
    guild_id = get_message_guild_id(ctx)

    # Compatível com a assinatura nova: save_character(char, guild_id)
    try:
        return save_character(char, guild_id)
    except TypeError:
        return save_character(char)


# =========================
# UTILITIES
# =========================

def is_admin(ctx) -> bool:
    return ctx.author.guild_permissions.administrator


def load_weapons_db():
    return load_json("data/weapons.json")


def pretty_list(values):
    return "\n".join(f"• `{pretty_id(v)}`" for v in values) if values else "None"


def build_embed(title, color, description=None):
    return discord.Embed(
        title=title,
        description=description or "",
        color=color
    )


# =========================
# ROLL FORMATTER
# =========================

def format_roll(result: dict) -> str:
    lines = [
        f"**Formula:** `{result.get('formula', '')}`",
        f"**Result:** `{result.get('total')}`",
    ]

    if result.get("dice"):
        lines.append("\n**Dice:**")
        for d in result["dice"]:
            lines.append(f"`{d['expr']}` → {d['rolls']} = `{d['total']}`")

    return "\n".join(lines)


def add_roll(embed, title, result):
    embed.add_field(name=title, value=format_roll(result), inline=False)


# =========================
# WEAPON EMBED
# =========================

def build_weapon_embed(title, weapon_id, data, equipped=False):
    embed = build_embed(title, discord.Color.gold())

    embed.add_field(name="Weapon", value=f"`{pretty_id(weapon_id)}`", inline=True)
    embed.add_field(name="Equipped", value="Yes" if equipped else "No", inline=True)

    if data.get("damage"):
        embed.add_field(name="Damage", value=f"`{data['damage']}`", inline=False)

    if data.get("attempt"):
        embed.add_field(name="Attack", value=f"`{data['attempt']}`", inline=False)

    return embed


# =========================
# ACTION SETUP
# =========================

def setup_action_commands(bot):

    # =========================
    # ATTACK
    # =========================
    @bot.command(name="attack")
    async def attack(ctx, name: str, weapon: str, ac: int = None):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send("❌ Character not found.")

        weapon_id = normalize_id(weapon)

        if weapon_id not in [normalize_id(v) for v in char.get("weapons", [])]:
            return await ctx.send("❌ Weapon not owned.")

        data = load_weapon(weapon_id)
        if not data:
            return await ctx.send("❌ Weapon not found.")

        result = execute_action(
            char,
            data,
            weapons_db=load_weapons_db(),
            preferred_weapon=weapon_id
        )

        embed = build_embed(
            f"⚔️ Attack — {pretty_id(weapon_id)}",
            discord.Color.red()
        )

        if result.get("attempt"):
            add_roll(embed, "Attack Roll", result["attempt"])

        if result.get("value"):
            add_roll(embed, "Damage", result["value"])

        if ac is not None:
            hit = result["attempt"]["total"] >= ac if result.get("attempt") else False
            embed.add_field(name="AC", value=str(ac), inline=True)
            embed.add_field(name="Result", value="Hit" if hit else "Miss", inline=True)

        await ctx.send(embed=embed)

    # =========================
    # EQUIP
    # =========================
    @bot.command(name="equip")
    async def equip(ctx, name: str, weapon: str):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send("❌ Character not found.")

        weapon_id = normalize_id(weapon)

        owned = [
            normalize_id(v)
            for v in (char.get("weapons", []) + char.get("items", []))
        ]

        if weapon_id not in owned:
            return await ctx.send("❌ You don't own this weapon.")

        data = load_weapon(weapon_id)
        if not data:
            return await ctx.send("❌ Weapon not found in database.")

        # Apenas 1 arma equipada por personagem por guilda
        char["equipped_weapon"] = weapon_id

        save_guild_character(ctx, char)

        await ctx.send(embed=build_weapon_embed(
            "⚔️ Equipped Weapon",
            weapon_id,
            data,
            equipped=True
        ))

    # =========================
    # UNEQUIP
    # =========================
    @bot.command(name="unequip")
    async def unequip(ctx, name: str):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send("❌ Character not found.")

        char["equipped_weapon"] = None
        save_guild_character(ctx, char)

        await ctx.send("🫳 Weapon unequipped.")

    # =========================
    # EQUIPMENT STATUS
    # =========================
    @bot.command(name="equipment")
    async def equipment(ctx, name: str):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send("❌ Character not found.")

        equipped = char.get("equipped_weapon")

        embed = build_embed(
            f"🧍 Equipment — {char['name']}",
            discord.Color.blurple()
        )

        if equipped:
            embed.add_field(
                name="Equipped Weapon",
                value=f"`{pretty_id(equipped)}`",
                inline=False
            )
        else:
            embed.add_field(
                name="Equipped Weapon",
                value="None",
                inline=False
            )

        embed.add_field(
            name="Weapons",
            value=pretty_list(char.get("weapons")),
            inline=False
        )

        embed.add_field(
            name="Items",
            value=pretty_list(char.get("items")),
            inline=False
        )

        await ctx.send(embed=embed)

    # =========================
    # USE ITEM
    # =========================
    @bot.command(name="use")
    async def use(ctx, name: str, item: str, dc: int = None):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send("❌ Character not found.")

        item_id = normalize_id(item)

        if item_id not in [normalize_id(v) for v in char.get("items", [])]:
            return await ctx.send("❌ Item not owned.")

        data = load_item(item_id)
        if not data:
            return await ctx.send("❌ Item not found.")

        result = execute_action(char, data, weapons_db=load_weapons_db())

        embed = build_embed(
            f"🎒 Use — {pretty_id(item_id)}",
            discord.Color.green()
        )

        if result.get("attempt"):
            add_roll(embed, "Attempt", result["attempt"])

        if result.get("value"):
            add_roll(embed, "Value", result["value"])

        embed.add_field(name="Final", value=str(result["final"]), inline=False)

        await ctx.send(embed=embed)

    # =========================
    # CAST
    # =========================
    @bot.command(name="cast")
    async def cast(ctx, name: str, ability: str, dc: int = None):
        char = load_guild_character(ctx, name)
        if not char:
            return await ctx.send("❌ Character not found.")

        ability_id = normalize_id(ability)

        if ability_id not in [normalize_id(v) for v in char.get("abilities", [])]:
            return await ctx.send("❌ Ability not learned.")

        data = load_ability(ability_id)
        if not data:
            return await ctx.send("❌ Ability not found.")

        result = execute_action(char, data, weapons_db=load_weapons_db())

        embed = build_embed(
            f"🔮 Cast — {pretty_id(ability_id)}",
            discord.Color.purple()
        )

        if result.get("attempt"):
            add_roll(embed, "Attempt", result["attempt"])

        if result.get("value"):
            add_roll(embed, "Value", result["value"])

        embed.add_field(name="Final", value=str(result["final"]), inline=False)

        await ctx.send(embed=embed)
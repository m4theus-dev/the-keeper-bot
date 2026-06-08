import discord
from discord.ext import commands

from systems.formula_engine import get_skill_map


def normalize_topic(topic: str) -> str:
    return topic.strip().lower().replace("-", "_").replace(" ", "_")


COMMANDS_HELP = {
    "create": {
        "desc": "Cria um personagem novo.",
        "usage": "/create <name>",
        "args": "name → nome do personagem. Use aspas se tiver espaço.",
        "example": '/create "Ed Baiano"',
        "notes": "Cria com atributos base e HP inicial calculado."
    },
    "sheet": {
        "desc": "Mostra a ficha completa do personagem.",
        "usage": "/sheet <name>",
        "args": "name → nome do personagem.",
        "example": '/sheet "Ed Baiano"',
        "notes": "Mostra atributos, skills, itens, armas, magias e stats derivados."
    },
    "edit": {
        "desc": "Edita level, atributos e outros campos do personagem.",
        "usage": "/edit <name> <field> <value>",
        "args": "field → ex.: attributes.STR ou level | value → novo valor",
        "example": '/edit "Ed Baiano" attributes.STR 15',
        "notes": "Admin only. Renomear personagem não é permitido."
    },
    "reload": {
        "desc": "Recalcula HP, HP máximo, iniciativa e proficiência.",
        "usage": "/reload <name>",
        "args": "name → nome do personagem.",
        "example": '/reload "Ed Baiano"',
        "notes": "Admin only. Usa level e atributos atuais."
    },
    "delete": {
        "desc": "Apaga um personagem.",
        "usage": "/delete <name>",
        "args": "name → nome do personagem.",
        "example": '/delete "Ed Baiano"',
        "notes": "Admin only."
    },
    "listchars": {
        "desc": "Lista todos os personagens salvos.",
        "usage": "/listchars",
        "args": "none",
        "example": "/listchars",
        "notes": "Mostra os nomes detectados em `saves/characters/`."
    },
    "setskill": {
        "desc": "Define nível de proficiência de uma perícia.",
        "usage": "/setskill <name> <skill> <level>",
        "args": "skill → perícia | level → 0, 1 ou 2",
        "example": '/setskill "Ed Baiano" athletics 2',
        "notes": "Admin only. 0 = untrained, 1 = proficient, 2 = expertise."
    },
    "removeskill": {
        "desc": "Remove uma perícia do personagem.",
        "usage": "/removeskill <name> <skill>",
        "args": "skill → perícia.",
        "example": '/removeskill "Ed Baiano" stealth',
        "notes": "Admin only."
    },
    "skills": {
        "desc": "Mostra as perícias do personagem.",
        "usage": "/skills <name>",
        "args": "name → nome do personagem.",
        "example": '/skills "Ed Baiano"',
        "notes": "Usa o sistema 0/1/2 e calcula o bônus total."
    },
    "check": {
        "desc": "Faz teste de perícia com d20 + skill.",
        "usage": "/check <name> <skill> [DC]",
        "args": "skill → perícia oficial | DC opcional no final",
        "example": '/check "Ed Baiano" acrobatics 15',
        "notes": "Usa todas as 18 perícias padrão do data/skills.json."
    },
    "roll": {
        "desc": "Rola uma fórmula qualquer com variáveis e dados.",
        "usage": "/roll <name> <formula>",
        "args": "formula → pode usar STR, DEX, PROF, LEVEL, dados e SKILL:ATHLETICS",
        "example": '/roll "Ed Baiano" 1d20+DEX+PROF',
        "notes": "SKILL:... já inclui atributo + proficiência; não some PROF de novo a menos que queira duplicar."
    },
    "use": {
        "desc": "Usa um item do inventário.",
        "usage": "/use <name> <item> [DC]",
        "args": "item → item em `items.json` e no inventário | DC opcional",
        "example": '/use "Ed Baiano" health_potion 12',
        "notes": "Se o item tiver attempt e value, os dois aparecem no embed. Se faltar attempt, vai direto pro value."
    },
    "cast": {
        "desc": "Usa uma habilidade/magia aprendida.",
        "usage": "/cast <name> <ability> [DC]",
        "args": "ability → ability em `abilities.json` e aprendido pelo personagem | DC opcional",
        "example": '/cast "Ed Baiano" fireball 15',
        "notes": "Se a habilidade exigir arma, o bot tenta escolher uma arma válida do personagem."
    },
    "attack": {
        "desc": "Faz um ataque com arma.",
        "usage": "/attack <name> <weapon> [AC]",
        "args": "weapon → arma no inventário | AC opcional",
        "example": '/attack "Ed Baiano" longsword 15',
        "notes": "AC = Armor Class. Se não houver attack roll na arma, o AC é ignorado."
    },
    "additem": {
        "desc": "Adiciona item ao personagem.",
        "usage": "/additem <name> <item>",
        "args": "item → item em `items.json`.",
        "example": '/additem "Ed Baiano" health_potion',
        "notes": "Admin only."
    },
    "removeitem": {
        "desc": "Remove item do personagem.",
        "usage": "/removeitem <name> <item>",
        "args": "item → item do inventário.",
        "example": '/removeitem "Ed Baiano" health_potion',
        "notes": "Admin only."
    },
    "addability": {
        "desc": "Adiciona habilidade ao personagem.",
        "usage": "/addability <name> <ability>",
        "args": "ability → ability em `abilities.json`.",
        "example": '/addability "Ed Baiano" fireball',
        "notes": "Admin only."
    },
    "removeability": {
        "desc": "Remove habilidade do personagem.",
        "usage": "/removeability <name> <ability>",
        "args": "ability → habilidade aprendida.",
        "example": '/removeability "Ed Baiano" fireball',
        "notes": "Admin only."
    },
    "addweapon": {
        "desc": "Adiciona arma ao personagem.",
        "usage": "/addweapon <name> <weapon>",
        "args": "weapon → weapon em `weapons.json`.",
        "example": '/addweapon "Ed Baiano" longsword',
        "notes": "Admin only."
    },
    "removeweapon": {
        "desc": "Remove arma do personagem.",
        "usage": "/removeweapon <name> <weapon>",
        "args": "weapon → arma do inventário.",
        "example": '/removeweapon "Ed Baiano" longsword',
        "notes": "Admin only."
    },
    "iteminfo": {
        "desc": "Mostra os dados de um item do JSON.",
        "usage": "/iteminfo <item>",
        "args": "item → item em `items.json`.",
        "example": "/iteminfo health_potion",
        "notes": "Mostra nome, descrição, tipo, attempt e value."
    },
    "abilityinfo": {
        "desc": "Mostra os dados de uma habilidade do JSON.",
        "usage": "/abilityinfo <ability>",
        "args": "ability → habilidade em `abilities.json`.",
        "example": "/abilityinfo fireball",
        "notes": "Mostra nome, descrição, tipo, attempt, value e requires_weapon."
    },
    "weaponinfo": {
        "desc": "Mostra os dados de uma arma do JSON.",
        "usage": "/weaponinfo <weapon>",
        "args": "weapon → arma em `weapons.json`.",
        "example": "/weaponinfo longsword",
        "notes": "Mostra nome, tipo, attempt e damage."
    },
}


HELP_SECTIONS = {
    "core": {
        "title": "📜 Core Commands",
        "summary": "Create, sheet, edit, reload, delete and list characters.",
        "commands": ["create", "sheet", "edit", "reload", "delete", "listchars"],
    },
    "skills": {
        "title": "🎯 Skills & Checks",
        "summary": "Skill levels, full skill map, and skill checks.",
        "commands": ["setskill", "removeskill", "skills", "check"],
    },
    "combat": {
        "title": "⚔️ Combat / Action Commands",
        "summary": "Rolls, item use, casting and weapon attacks.",
        "commands": ["roll", "use", "cast", "attack"],
    },
    "data": {
        "title": "🗃️ Data Editing",
        "summary": "Add or remove items, abilities and weapons from characters.",
        "commands": ["additem", "removeitem", "addability", "removeability", "addweapon", "removeweapon"],
    },
    "info": {
        "title": "ℹ️ Database Info",
        "summary": "Inspect the raw JSON data for items, abilities and weapons.",
        "commands": ["iteminfo", "abilityinfo", "weaponinfo"],
    },
}


def build_overview_embed():
    embed = discord.Embed(
        title="📖 RPG Bot Help",
        description="Use text commands with the `/` prefix, like `/help core` or `/help attack`.\n\nNo literal flags are used. The optional number at the end is treated as DC or AC.",
        color=discord.Color.blue(),
    )

    for key, section in HELP_SECTIONS.items():
        embed.add_field(
            name=section["title"],
            value=f"{section['summary']}\nUse `/help {key}`",
            inline=False,
        )

    embed.set_footer(text="Use quotes for names with spaces: /sheet \"Ed Baiano\"")
    return embed


def build_section_embed(section_key: str):
    section = HELP_SECTIONS[section_key]
    embed = discord.Embed(
        title=section["title"],
        description=section["summary"],
        color=discord.Color.blurple(),
    )

    for cmd_name in section["commands"]:
        info = COMMANDS_HELP[cmd_name]
        embed.add_field(
            name=f"/{cmd_name}",
            value=f"{info['desc']}\n`{info['usage']}`",
            inline=False,
        )

    if section_key == "skills":
        skill_map = get_skill_map()
        skill_lines = [f"**{k}** → `{v}`" for k, v in sorted(skill_map.items())]
        embed.add_field(
            name="Standard Skills",
            value="\n".join(skill_lines),
            inline=False,
        )
        embed.add_field(
            name="Skill Levels",
            value="`0` = untrained | `1` = proficient | `2` = expertise",
            inline=False,
        )

    if section_key == "combat":
        embed.add_field(
            name="How it works",
            value=(
                "`attempt` = test roll\n"
                "`value` / `damage` = effect or damage\n"
                "If `attempt` is missing, the command goes straight to `value`.\n"
                "If `value` is missing, only `attempt` is rolled.\n"
                "`DC` is class difficulty, `AC` is armor class."
            ),
            inline=False,
        )

    if section_key == "data":
        embed.add_field(
            name="Permission",
            value="These commands are Admin only.",
            inline=False,
        )

    return embed


def build_command_embed(command_key: str):
    info = COMMANDS_HELP[command_key]
    embed = discord.Embed(
        title=f"📘 Help — /{command_key}",
        description=info["desc"],
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Usage", value=info["usage"], inline=False)
    embed.add_field(name="Arguments", value=info["args"], inline=False)
    embed.add_field(name="Example", value=info["example"], inline=False)

    if info.get("notes"):
        embed.add_field(name="Notes", value=info["notes"], inline=False)

    if "Admin only" in info.get("notes", ""):
        embed.add_field(name="Permission", value="Admin only", inline=False)

    return embed


def setup_help(bot):

    @bot.command(name="help")
    async def help_cmd(ctx, *, topic: str = None):
        if not topic:
            return await ctx.send(embed=build_overview_embed())

        key = normalize_topic(topic)

        if key in HELP_SECTIONS:
            return await ctx.send(embed=build_section_embed(key))

        if key in COMMANDS_HELP:
            return await ctx.send(embed=build_command_embed(key))

        if key == "skill_check":
            return await ctx.send(embed=build_command_embed("check"))

        await ctx.send(embed=discord.Embed(
            title="❌ Help topic not found",
            description="Use `/help` to see all sections or `/help <command>` for details.",
            color=discord.Color.red(),
        ))
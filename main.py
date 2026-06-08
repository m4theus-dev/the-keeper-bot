import json
import discord
from discord.ext import commands

from commands.character_commands import setup_character_commands


# =========================
# CONFIG LOAD
# =========================

CONFIG_PATH = "config/config.json"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

TOKEN = config["token"]


# =========================
# BOT SETUP
# =========================

intents = discord.Intents.default()
intents.message_content = True  # IMPORTANTE para prefix commands

bot = commands.Bot(command_prefix="/", intents=intents)


# =========================
# EVENTS
# =========================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


# =========================
# LOAD COMMANDS
# =========================

setup_character_commands(bot)


# =========================
# RUN BOT
# =========================

bot.run(TOKEN)
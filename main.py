import json
import discord
from discord.ext import commands

with open("config/config.json", "r") as f:
    config = json.load(f)

TOKEN = config["token"]

intents = discord.Intents.default()
intents.message_content = True  # importante para comandos com prefixo !

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")


bot.run(TOKEN)
import json
import discord
from discord.ext import commands

from commands.character_commands import setup_character_commands
from commands.action_commands import setup_action_commands
from commands.help_command import setup_help


with open("config/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TOKEN = config["token"]

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `/help`.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing arguments. Use `/help <command>`.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument format. Use quotes for names with spaces and numbers for DC/AC.")
        return

    raise error


setup_character_commands(bot)
setup_action_commands(bot)
setup_help(bot)

bot.run(TOKEN)
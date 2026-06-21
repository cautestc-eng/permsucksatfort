import discord
from discord.ext import commands
from discord import app_commands
import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(os.path.join(LOG_DIR, "bot.log"), maxBytes=5 * 1024 * 1024, backupCount=3),
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger("OrlandoBot")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        logger.error("config.json not found! Copy config.json.example to config.json and configure it.")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


config = load_config()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.bans = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")

    from database import initialize_database
    initialize_database()

    status_text = config.get("bot_status", "with SSU | /help")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name=status_text)
    )

    await bot.tree.sync()
    logger.info(f"Slash commands synced for {len(bot.tree.get_commands())} commands")

    from utils import find_assets
    assets = find_assets()
    logger.info(f"Found assets: {', '.join([f'{k}={v}' for k, v in assets.items() if v]) or 'none'}")

    keep_alive = config.get("replit_keep_alive", True)
    if keep_alive:
        from keep_alive import start as start_keep_alive
        start_keep_alive()
        logger.info("Keep-alive web server started")

    print(f"\n{'='*50}")
    print(f"  Orlando Moderation Bot is online!")
    print(f"  Logged in as: {bot.user}")
    print(f"  Servers: {len(bot.guilds)}")
    print(f"{'='*50}\n")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.error(f"Command error in {interaction.command}: {error}")

    if isinstance(error, app_commands.CommandOnCooldown):
        embed = discord.Embed(title="Command on Cooldown", description=f"Try again in {error.retry_after:.0f}s.", color=0xfee75c)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    if isinstance(error, app_commands.CheckFailure):
        embed = discord.Embed(title="Permission Denied", description="You don't have permission to use this command.", color=0xed4245)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    embed = discord.Embed(title="Error", description=f"An error occurred: {str(error)}", color=0xed4245)
    try:
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except:
        try:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except:
            pass


async def load_cogs():
    cogs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cogs")
    if not os.path.exists(cogs_dir):
        os.makedirs(cogs_dir)
        logger.info(f"Created cogs directory")

    cog_files = [f for f in os.listdir(cogs_dir) if f.endswith(".py") and f != "__init__.py"]
    for cog in cog_files:
        try:
            await bot.load_extension(f"cogs.{cog[:-3]}")
            logger.info(f"Loaded cog: {cog[:-3]}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog}: {e}")

    await bot.tree.sync()


if __name__ == "__main__":
    if not TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        logger.error("Create a .env file with: DISCORD_TOKEN=your_token_here")
        sys.exit(1)

    if not os.path.exists(CONFIG_PATH):
        if os.path.exists(CONFIG_PATH + ".example"):
            import shutil
            shutil.copy(CONFIG_PATH + ".example", CONFIG_PATH)
            logger.info(f"Created config.json from config.json.example")
            logger.warning("Edit config.json with your server settings before running!")
            sys.exit(0)

    import asyncio
    asyncio.run(load_cogs())
    bot.run(TOKEN)

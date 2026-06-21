import json
import os
import logging
import random
import string
from datetime import datetime
import discord
from discord.ext import commands

logger = logging.getLogger("OrlandoBot.Utils")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config():
    if not os.path.exists(CONFIG_PATH):
        logger.error("config.json not found! Copy config.json.example to config.json and configure it.")
        return {}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)


def get_asset_path(filename):
    path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(path):
        return path
    return None


def find_assets():
    assets = {
        "ssu_banner": None,
        "ssd_banner": None,
        "logo": None,
        "boost": None,
        "vote": None,
    }
    for f in os.listdir(ASSETS_DIR):
        if not f.lower().endswith(".png"):
            continue
        lower = f.lower()
        if "startup" in lower or ("ssu" in lower and "banner" in lower):
            assets["ssu_banner"] = os.path.join(ASSETS_DIR, f)
        elif "shutdown" in lower or ("ssd" in lower and "banner" in lower):
            assets["ssd_banner"] = os.path.join(ASSETS_DIR, f)
        elif "logo" in lower:
            assets["logo"] = os.path.join(ASSETS_DIR, f)
        elif "boost" in lower:
            assets["boost"] = os.path.join(ASSETS_DIR, f)
        elif "vote" in lower:
            assets["vote"] = os.path.join(ASSETS_DIR, f)

    if assets["ssu_banner"] is None:
        for f in os.listdir(ASSETS_DIR):
            if f.lower().endswith(".png") and assets["ssu_banner"] is None:
                assets["ssu_banner"] = os.path.join(ASSETS_DIR, f)
                break
    if assets["logo"] is None:
        for f in os.listdir(ASSETS_DIR):
            if f.lower().endswith(".png") and assets["logo"] is None:
                assets["logo"] = os.path.join(ASSETS_DIR, f)
                break

    return assets


async def upload_asset_to_discord(bot, filepath, guild_id):
    if not filepath or not os.path.exists(filepath):
        return None
    guild = bot.get_guild(guild_id)
    if not guild:
        return None
    try:
        with open(filepath, "rb") as f:
            file = discord.File(f, filename=os.path.basename(filepath))
        return file
    except Exception as e:
        logger.error(f"Failed to upload asset: {e}")
        return None


def create_embed(title="", description="", color=None, config=None):
    if color is None:
        color = 0x2b2d31
    if config and "embed_colors" in config and "primary" in config["embed_colors"]:
        color = config["embed_colors"]["primary"]
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.utcnow())
    return embed


def has_role_or_higher(member, required_roles, config):
    if not config or "roles" not in config:
        return False
    role_ids = config["roles"]
    if member.guild_permissions.administrator:
        return True
    hierarchy = ["trial_moderator", "moderator", "supervisor", "administrator", "management"]
    req_idx = -1
    for i, r in enumerate(hierarchy):
        if r == required_roles:
            req_idx = i
            break
    if req_idx == -1:
        return False
    for i in range(req_idx, len(hierarchy)):
        role_id = role_ids.get(hierarchy[i], 0)
        if role_id and member.get_role(role_id):
            return True
    return False


def get_role_id(config, role_name):
    if not config or "roles" not in config:
        return 0
    return config["roles"].get(role_name, 0)


def get_channel_id(config, channel_name):
    if not config or "channels" not in config:
        return 0
    return config["channels"].get(channel_name, 0)


def format_duration(seconds):
    seconds = int(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def generate_id(prefix, count):
    return f"{prefix}-{count:06d}"


def get_threshold_message(points, config):
    thresholds = config.get("thresholds", {})
    if points >= thresholds.get("termination_recommendation", 15):
        return "Termination Recommendation"
    if points >= thresholds.get("suspension_recommendation", 10):
        return "Staff Suspension Recommendation"
    if points >= thresholds.get("final_warning", 8):
        return "Final Warning"
    if points >= thresholds.get("official_warning", 5):
        return "Official Warning"
    if points >= thresholds.get("reminder", 3):
        return "Staff Reminder"
    return None


INFRACTION_CATEGORIES = {
    "Verbal Warning": 1,
    "Minor Warning": 2,
    "Moderate Warning": 3,
    "Major Warning": 5,
    "Failure To Moderate": 3,
    "Abuse Of Powers": 5,
    "Inactivity": 2,
    "Disrespect": 3,
    "SSU Violations": 2,
    "Custom": 0,
}

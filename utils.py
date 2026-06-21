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


PERMISSION_HIERARCHY = ["trial_moderator", "moderator", "supervisor", "administrator", "management"]

PERMISSION_STEPS = {
    "trial_moderator": {
        "level": 1,
        "label": "Trial Moderator",
        "perms": ["view_infractions", "view_stats", "view_history"],
    },
    "moderator": {
        "level": 2,
        "label": "Moderator",
        "perms": ["warn", "kick", "timeout", "issue_infractions", "purge", "nickname", "note", "slowmode"],
    },
    "supervisor": {
        "level": 3,
        "label": "Supervisor",
        "perms": ["manage_infractions", "start_ssu", "end_ssu", "lock_channels", "ssu_actions"],
    },
    "administrator": {
        "level": 4,
        "label": "Administrator",
        "perms": ["ban", "unban", "remove_infractions", "manage_sessions", "manage_config", "manage_appeals"],
    },
    "management": {
        "level": 5,
        "label": "Management",
        "perms": ["all"],
    },
}

ALL_PERMISSIONS = set()
for role_config in PERMISSION_STEPS.values():
    ALL_PERMISSIONS.update(role_config["perms"])


def get_member_level(member, config):
    if not config or "roles" not in config:
        return 0
    if member.guild_permissions.administrator:
        return 5
    role_ids = config["roles"]
    highest_level = 0
    for role_name, role_config in PERMISSION_STEPS.items():
        role_id = role_ids.get(role_name, 0)
        if role_id and member.get_role(role_id):
            if role_config["level"] > highest_level:
                highest_level = role_config["level"]
    return highest_level


def has_permission(member, permission, config):
    level = get_member_level(member, config)
    if level >= 5:
        return True
    for role_name, role_config in PERMISSION_STEPS.items():
        if role_config["level"] <= level:
            if "all" in role_config["perms"]:
                return True
            if permission in role_config["perms"]:
                return True
    return False


def get_member_role_label(member, config):
    level = get_member_level(member, config)
    for role_name, role_config in reversed(PERMISSION_STEPS.items()):
        if role_config["level"] == level:
            return role_config["label"]
    return "Member"


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

ACTION_COLORS = {
    "promotion": 0x57f287,
    "demotion": 0xe67e22,
    "warning": 0xfee75c,
    "infraction": 0xe67e22,
    "suspension": 0xed4245,
    "termination": 0x8b0000,
    "ssu": 0x5865f2,
    "ssd": 0x808080,
}


def build_staff_action_embed(action_type, title, fields, action_id, moderator, config, target=None, thumbnail_url=None):
    color = ACTION_COLORS.get(action_type, 0x2b2d31)
    server_name = config.get("server_name", "Server")
    mod_label = get_member_role_label(moderator, config)

    embed = discord.Embed(
        title="",
        description=f"**Signed, {mod_label} | {moderator.display_name}**\n\n**{title}**",
        color=color,
        timestamp=datetime.utcnow()
    )

    bullet_text = ""
    for label, value in fields:
        bullet_text += f"• **{label}:** {value}\n"

    embed.description += f"\n\n{bullet_text}"

    if target:
        embed.set_thumbnail(url=target.display_avatar.url)
    elif thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    embed.set_footer(text=f"{server_name} • {action_id}")
    return embed


def build_infraction_embed(action_id, moderator, target_user, category, reason, points, evidence, total_points, config):
    mod_label = get_member_role_label(moderator, config)
    server_name = config.get("server_name", "Server")

    embed = discord.Embed(
        title="",
        description=f"**Signed, {mod_label} | {moderator.display_name}**\n\n**Staff Infraction**",
        color=ACTION_COLORS["infraction"],
        timestamp=datetime.utcnow()
    )

    embed.description += f"\n\n• **Staff Member:** {target_user.mention}\n"
    embed.description += f"• **Category:** {category}\n"
    embed.description += f"• **Points:** {points}\n"
    embed.description += f"• **Reason:** {reason}\n"
    if evidence:
        embed.description += f"• **Evidence:** {evidence}\n"
    embed.description += f"• **Active Points:** {total_points}"

    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.set_footer(text=f"{server_name} • {action_id}")
    return embed


def build_warning_embed(action_id, moderator, target_user, reason, points, config):
    mod_label = get_member_role_label(moderator, config)
    server_name = config.get("server_name", "Server")

    embed = discord.Embed(
        title="",
        description=f"**Signed, {mod_label} | {moderator.display_name}**\n\n**Staff Warning**",
        color=ACTION_COLORS["warning"],
        timestamp=datetime.utcnow()
    )

    embed.description += f"\n\n• **Staff Member:** {target_user.mention}\n"
    embed.description += f"• **Points:** {points}\n"
    embed.description += f"• **Reason:** {reason}\n"

    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.set_footer(text=f"{server_name} • {action_id}")
    return embed


def build_promotion_embed(action_id, moderator, target_user, previous_role, new_role, reason, config):
    mod_label = get_member_role_label(moderator, config)
    server_name = config.get("server_name", "Server")

    embed = discord.Embed(
        title="",
        description=f"**Signed, {mod_label} | {moderator.display_name}**\n\n**Staff Promotion**",
        color=ACTION_COLORS["promotion"],
        timestamp=datetime.utcnow()
    )

    embed.description += f"\n\n• **Staff Member:** {target_user.mention}\n"
    embed.description += f"• **Previous Role:** {previous_role}\n"
    embed.description += f"• **New Role:** {new_role}\n"
    embed.description += f"• **Reason:** {reason}"

    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.set_footer(text=f"{server_name} • {action_id}")
    return embed


def build_demotion_embed(action_id, moderator, target_user, previous_role, new_role, reason, config):
    mod_label = get_member_role_label(moderator, config)
    server_name = config.get("server_name", "Server")

    embed = discord.Embed(
        title="",
        description=f"**Signed, {mod_label} | {moderator.display_name}**\n\n**Staff Demotion**",
        color=ACTION_COLORS["demotion"],
        timestamp=datetime.utcnow()
    )

    embed.description += f"\n\n• **Staff Member:** {target_user.mention}\n"
    embed.description += f"• **Previous Role:** {previous_role}\n"
    embed.description += f"• **New Role:** {new_role}\n"
    embed.description += f"• **Reason:** {reason}"

    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.set_footer(text=f"{server_name} • {action_id}")
    return embed


def build_suspension_embed(action_id, moderator, target_user, duration_days, reason, related_infraction, config):
    mod_label = get_member_role_label(moderator, config)
    server_name = config.get("server_name", "Server")

    embed = discord.Embed(
        title="",
        description=f"**Signed, {mod_label} | {moderator.display_name}**\n\n**Staff Suspension**",
        color=ACTION_COLORS["suspension"],
        timestamp=datetime.utcnow()
    )

    embed.description += f"\n\n• **Staff Member:** {target_user.mention}\n"
    embed.description += f"• **Duration:** {duration_days} Days\n"
    embed.description += f"• **Reason:** {reason}\n"
    if related_infraction:
        embed.description += f"• **Related Infraction:** {related_infraction}"

    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.set_footer(text=f"{server_name} • {action_id}")
    return embed


def build_termination_embed(action_id, moderator, target_user, total_points, active_infractions, reason, config):
    mod_label = get_member_role_label(moderator, config)
    server_name = config.get("server_name", "Server")

    embed = discord.Embed(
        title="",
        description=f"**Signed, {mod_label} | {moderator.display_name}**\n\n**Staff Termination**",
        color=ACTION_COLORS["termination"],
        timestamp=datetime.utcnow()
    )

    embed.description += f"\n\n• **Staff Member:** {target_user.mention}\n"
    embed.description += f"• **Total Points:** {total_points}\n"
    embed.description += f"• **Active Infractions:** {active_infractions}\n"
    embed.description += f"• **Reason:** {reason}"

    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.set_footer(text=f"{server_name} • {action_id}")
    return embed

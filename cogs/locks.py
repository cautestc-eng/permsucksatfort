import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging

from database import get_connection, get_next_action_id, ensure_user, ensure_staff_stats
from utils import load_config, create_embed, has_role_or_higher, get_channel_id

logger = logging.getLogger("OrlandoBot.Locks")


class ChannelLocks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.locked_channels = {}

    def reload_config(self):
        self.config = load_config()

    async def log_lock_action(self, guild, moderator, channel, action, reason):
        self.reload_config()
        lock_log_id = get_channel_id(self.config, "lock_log")
        if not lock_log_id:
            return
        log_channel = guild.get_channel(lock_log_id)
        if not log_channel:
            return
        color = 0xed4245 if "Lock" in action else 0x57f287
        embed = create_embed(
            f"{action} | {channel.name}",
            f"**Channel:** {channel.mention}\n**Moderator:** {moderator.mention}\n**Reason:** {reason}",
            color, self.config
        )
        await log_channel.send(embed=embed)

    @app_commands.command(name="lock", description="Lock a channel")
    @app_commands.describe(channel="Channel to lock (defaults to current)", reason="Reason for locking")
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "No reason provided"):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "supervisor", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Supervisor+ to lock channels.", 0xed4245, self.config),
                ephemeral=True
            )
        if not interaction.guild.me.guild_permissions.manage_channels:
            return await interaction.response.send_message(
                embed=create_embed("Error", "I don't have permission to manage channels.", 0xed4245, self.config),
                ephemeral=True
            )

        channel = channel or interaction.channel
        action_id = get_next_action_id()
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)

        self.locked_channels[channel.id] = True

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, interaction.guild.id, "Lock", reason, channel.id)
        )
        cursor.execute("UPDATE staff_stats SET locks_performed = locks_performed + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        cursor.execute("UPDATE users SET locks_performed = locks_performed + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        lock_msg = self.config.get("lock_message", "This channel has been locked by a moderator.")
        embed = create_embed("Channel Locked", f"**Channel:** {channel.mention}\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}\n**Action ID:** `{action_id}`\n\n{lock_msg}", 0xed4245, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_lock_action(interaction.guild, interaction.user, channel, "Lock", reason)

    @app_commands.command(name="unlock", description="Unlock a channel")
    @app_commands.describe(channel="Channel to unlock (defaults to current)", reason="Reason for unlocking")
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "No reason provided"):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "supervisor", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Supervisor+ to unlock channels.", 0xed4245, self.config),
                ephemeral=True
            )
        if not interaction.guild.me.guild_permissions.manage_channels:
            return await interaction.response.send_message(
                embed=create_embed("Error", "I don't have permission to manage channels.", 0xed4245, self.config),
                ephemeral=True
            )

        channel = channel or interaction.channel
        action_id = get_next_action_id()
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)

        self.locked_channels.pop(channel.id, None)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, interaction.guild.id, "Unlock", reason, channel.id)
        )
        cursor.execute("UPDATE staff_stats SET moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = create_embed("Channel Unlocked", f"**Channel:** {channel.mention}\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}\n**Action ID:** `{action_id}`", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_lock_action(interaction.guild, interaction.user, channel, "Unlock", reason)

    @app_commands.command(name="slowmode", description="Set slowmode on a channel")
    @app_commands.describe(seconds="Slowmode in seconds (0 to disable)", channel="Channel (defaults to current)", reason="Reason")
    async def slowmode(self, interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None, reason: str = "No reason provided"):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "moderator", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Moderator+ to set slowmode.", 0xed4245, self.config),
                ephemeral=True
            )
        if not interaction.guild.me.guild_permissions.manage_channels:
            return await interaction.response.send_message(
                embed=create_embed("Error", "I don't have permission.", 0xed4245, self.config),
                ephemeral=True
            )

        channel = channel or interaction.channel
        seconds = max(0, min(seconds, 21600))

        await channel.edit(slowmode_delay=seconds, reason=reason)

        action_id = get_next_action_id()
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, interaction.guild.id, "Slowmode", f"{reason} | {seconds}s", channel.id)
        )
        conn.commit()
        conn.close()

        embed = create_embed("Slowmode Updated", f"**Channel:** {channel.mention}\n**Slowmode:** {seconds} seconds\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0x5865f2, self.config)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ChannelLocks(bot))

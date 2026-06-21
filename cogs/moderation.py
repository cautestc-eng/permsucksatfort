import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging

from database import get_connection, get_next_action_id, ensure_user, ensure_staff_stats
from utils import load_config, create_embed, has_permission, get_channel_id, format_duration

logger = logging.getLogger("OrlandoBot.Moderation")


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

    async def log_action(self, guild, action_id, moderator, target, action, reason):
        log_channel_id = get_channel_id(self.config, "mod_log")
        if not log_channel_id:
            return
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return
        color = 0xed4245 if action in ("Ban",) else 0x57f287
        embed = create_embed(f"{action} | {action_id}", f"**Target:** {target.mention} (`{target.id}`)\n**Moderator:** {moderator.mention}\n**Reason:** {reason}", color, self.config)
        await log_channel.send(embed=embed)

    async def log_to_ban_log(self, guild, moderator, target, action, reason):
        ban_log_id = get_channel_id(self.config, "ban_log")
        if not ban_log_id:
            return
        log_channel = guild.get_channel(ban_log_id)
        if not log_channel:
            return
        embed = create_embed(f"{action} | {target}", f"**Target:** {target.mention} (`{target.id}`)\n**Moderator:** {moderator.mention}\n**Reason:** {reason}", 0xed4245, self.config)
        await log_channel.send(embed=embed)

    @app_commands.command(name="ban", description="Ban a member")
    @app_commands.describe(member="Member to ban", reason="Reason", delete_days="Delete message history (0-7)")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str, delete_days: int = 0):
        self.reload_config()
        if not has_permission(interaction.user, "ban", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Administrator+ to ban.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot ban yourself.", 0xed4245, self.config), ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(embed=create_embed("Error", "Cannot ban higher or equal role.", 0xed4245, self.config), ephemeral=True)
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message(embed=create_embed("Error", "I lack ban permission.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_action_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
                       (action_id, interaction.user.id, member.id, "Ban", reason))
        cursor.execute("UPDATE staff_stats SET bans = bans + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?", (interaction.user.id,))
        cursor.execute("UPDATE users SET bans = bans + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?", (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = create_embed("Member Banned", f"**Member:** {member.mention}\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0xed4245, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, member, "Ban", reason)
        await self.log_to_ban_log(interaction.guild, interaction.user, member, "Ban", reason)
        await member.ban(reason=reason, delete_message_days=delete_days)

    @app_commands.command(name="unban", description="Unban a user")
    @app_commands.describe(user_id="User ID to unban", reason="Reason")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str):
        self.reload_config()
        if not has_permission(interaction.user, "ban", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Administrator+ to unban.", 0xed4245, self.config), ephemeral=True)
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message(embed=create_embed("Error", "I lack ban permission.", 0xed4245, self.config), ephemeral=True)

        try:
            user = await self.bot.fetch_user(int(user_id))
        except:
            return await interaction.response.send_message(embed=create_embed("Error", "Invalid user ID.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_action_id()
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
                       (action_id, interaction.user.id, user.id, "Unban", reason))
        conn.commit()
        conn.close()

        await interaction.guild.unban(user, reason=reason)
        embed = create_embed("User Unbanned", f"**User:** {user.mention} (`{user.id}`)\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, user, "Unban", reason)
        await self.log_to_ban_log(interaction.guild, interaction.user, user, "Unban", reason)


async def setup(bot):
    await bot.add_cog(Moderation(bot))

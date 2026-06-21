import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging

from database import get_connection, get_next_action_id, ensure_user, ensure_staff_stats
from utils import load_config, create_embed, has_role_or_higher, get_channel_id, format_duration

logger = logging.getLogger("OrlandoBot.Moderation")


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

    async def log_action(self, guild, action_id, moderator, target, action, reason, result="success", duration=0):
        self.reload_config()
        log_channel_id = get_channel_id(self.config, "mod_log")
        if not log_channel_id:
            return
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        color_map = {
            "Warn": 0xfee75c,
            "Kick": 0xed4245,
            "Ban": 0xed4245,
            "Unban": 0x57f287,
            "Timeout": 0xfee75c,
            "Untimeout": 0x57f287,
            "Purge": 0x5865f2,
            "Nickname": 0x5865f2,
            "Note": 0x5865f2,
        }
        color = color_map.get(action, 0x5865f2)

        embed = create_embed(f"{action} | {action_id}", f"**Target:** {target.mention} (`{target.id}`)\n**Moderator:** {moderator.mention}\n**Reason:** {reason}", color, self.config)
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Result", value=result, inline=True)
        if duration:
            embed.add_field(name="Duration", value=format_duration(duration), inline=True)
        embed.set_footer(text=f"Action ID: {action_id}")

        await log_channel.send(embed=embed)

    async def log_to_ban_log(self, guild, moderator, target, action, reason):
        self.reload_config()
        ban_log_id = get_channel_id(self.config, "ban_log")
        if not ban_log_id:
            return
        log_channel = guild.get_channel(ban_log_id)
        if not log_channel:
            return
        embed = create_embed(f"{action} | {target}", f"**Target:** {target.mention} (`{target.id}`)\n**Moderator:** {moderator.mention}\n**Reason:** {reason}", 0xed4245, self.config)
        await log_channel.send(embed=embed)

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "moderator", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Moderator+ to warn members.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot warn yourself.", 0xed4245, self.config), ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot warn someone with a higher or equal role.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_action_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, member.id, "Warn", reason)
        )
        cursor.execute("UPDATE staff_stats SET warnings = warnings + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        cursor.execute("UPDATE users SET warnings = warnings + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = create_embed("Warning Issued", f"**Member:** {member.mention}\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0xfee75c, self.config)
        await interaction.response.send_message(embed=embed)

        try:
            await member.send(embed=create_embed("Warning Received", f"You have received a warning in **{interaction.guild.name}**.\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0xfee75c, self.config))
        except:
            pass

        await self.log_action(interaction.guild, action_id, interaction.user, member, "Warn", reason)

    @app_commands.command(name="kick", description="Kick a member")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "moderator", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Moderator+ to kick members.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot kick yourself.", 0xed4245, self.config), ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot kick someone with a higher or equal role.", 0xed4245, self.config), ephemeral=True)
        if not interaction.guild.me.guild_permissions.kick_members:
            return await interaction.response.send_message(embed=create_embed("Error", "I don't have permission to kick members.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_action_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        try:
            await member.send(embed=create_embed("Kicked", f"You have been kicked from **{interaction.guild.name}**.\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0xed4245, self.config))
        except:
            pass

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, member.id, "Kick", reason)
        )
        cursor.execute("UPDATE staff_stats SET kicks = kicks + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        cursor.execute("UPDATE users SET kicks = kicks + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = create_embed("Member Kicked", f"**Member:** {member.mention}\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0xed4245, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, member, "Kick", reason)
        await member.kick(reason=reason)

    @app_commands.command(name="ban", description="Ban a member")
    @app_commands.describe(member="Member to ban", reason="Reason for the ban", delete_days="Delete message history (0-7)")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str, delete_days: int = 0):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "administrator", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Administrator+ to ban members.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot ban yourself.", 0xed4245, self.config), ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot ban someone with a higher or equal role.", 0xed4245, self.config), ephemeral=True)
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message(embed=create_embed("Error", "I don't have permission to ban members.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_action_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, member.id, "Ban", reason)
        )
        cursor.execute("UPDATE staff_stats SET bans = bans + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        cursor.execute("UPDATE users SET bans = bans + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = create_embed("Member Banned", f"**Member:** {member.mention}\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0xed4245, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, member, "Ban", reason)
        await self.log_to_ban_log(interaction.guild, interaction.user, member, "Ban", reason)
        await member.ban(reason=reason, delete_message_days=delete_days)

    @app_commands.command(name="unban", description="Unban a user")
    @app_commands.describe(user_id="User ID to unban", reason="Reason for unban")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "administrator", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Administrator+ to unban users.", 0xed4245, self.config), ephemeral=True)
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message(embed=create_embed("Error", "I don't have permission to ban members.", 0xed4245, self.config), ephemeral=True)

        try:
            user = await self.bot.fetch_user(int(user_id))
        except:
            return await interaction.response.send_message(embed=create_embed("Error", "Invalid user ID or user not found.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_action_id()
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, user.id, "Unban", reason)
        )
        conn.commit()
        conn.close()

        await interaction.guild.unban(user, reason=reason)
        embed = create_embed("User Unbanned", f"**User:** {user.mention} (`{user.id}`)\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, user, "Unban", reason)
        await self.log_to_ban_log(interaction.guild, interaction.user, user, "Unban", reason)

    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.describe(member="Member to timeout", duration="Duration in minutes", reason="Reason for timeout")
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "moderator", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Moderator+ to timeout members.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot timeout yourself.", 0xed4245, self.config), ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot timeout someone with a higher or equal role.", 0xed4245, self.config), ephemeral=True)
        if not interaction.guild.me.guild_permissions.moderate_members:
            return await interaction.response.send_message(embed=create_embed("Error", "I don't have permission to timeout members.", 0xed4245, self.config), ephemeral=True)

        duration_seconds = min(duration * 60, 2419200)
        action_id = get_next_action_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason, duration) VALUES (?, ?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, member.id, "Timeout", reason, duration_seconds)
        )
        cursor.execute("UPDATE staff_stats SET moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        await member.timeout(discord.utils.utcnow() + datetime.timedelta(seconds=duration_seconds), reason=reason)
        embed = create_embed("Member Timed Out", f"**Member:** {member.mention}\n**Duration:** {format_duration(duration_seconds)}\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0xfee75c, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, member, "Timeout", reason, duration=duration_seconds)

    @app_commands.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.describe(member="Member to remove timeout from", reason="Reason")
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Timeout removed"):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "moderator", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Moderator+.", 0xed4245, self.config), ephemeral=True)
        if not interaction.guild.me.guild_permissions.moderate_members:
            return await interaction.response.send_message(embed=create_embed("Error", "I don't have permission.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_action_id()
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, member.id, "Untimeout", reason)
        )
        conn.commit()
        conn.close()

        await member.timeout(None, reason=reason)
        embed = create_embed("Timeout Removed", f"**Member:** {member.mention}\n**Action ID:** `{action_id}`", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, member, "Untimeout", reason)

    @app_commands.command(name="purge", description="Bulk delete messages")
    @app_commands.describe(amount="Number of messages to delete", reason="Reason for purge")
    async def purge(self, interaction: discord.Interaction, amount: int, reason: str = "Bulk delete"):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "moderator", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Moderator+ to purge messages.", 0xed4245, self.config), ephemeral=True)
        if not interaction.guild.me.guild_permissions.manage_messages:
            return await interaction.response.send_message(embed=create_embed("Error", "I don't have permission to manage messages.", 0xed4245, self.config), ephemeral=True)

        amount = min(max(amount, 1), 1000)
        action_id = get_next_action_id()
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        deleted = await interaction.channel.purge(limit=amount, reason=reason)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, interaction.user.id, "Purge", f"{reason} | {len(deleted)} messages")
        )
        cursor.execute("UPDATE staff_stats SET moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = create_embed("Messages Purged", f"**Amount:** {len(deleted)} messages\n**Channel:** {interaction.channel.mention}\n**Reason:** {reason}\n**Action ID:** `{action_id}`", 0x5865f2, self.config)
        msg = await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, interaction.user, "Purge", f"{reason} | {len(deleted)} messages")

    @app_commands.command(name="nickname", description="Change a member's nickname")
    @app_commands.describe(member="Member", nickname="New nickname (leave empty to reset)", reason="Reason")
    async def nickname(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None, reason: str = "Nickname change"):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "moderator", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Moderator+ to change nicknames.", 0xed4245, self.config), ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(embed=create_embed("Error", "Cannot change nickname.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_action_id()
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        old_nick = member.display_name
        await member.edit(nick=nickname, reason=reason)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, member.id, "Nickname", f"{reason} | {old_nick} -> {nickname}")
        )
        cursor.execute("UPDATE staff_stats SET moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = create_embed("Nickname Changed", f"**Member:** {member.mention}\n**Old:** {old_nick}\n**New:** {nickname or 'Reset'}\n**Action ID:** `{action_id}`", 0x5865f2, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, member, "Nickname", reason)

    @app_commands.command(name="note", description="Add a note to a member")
    @app_commands.describe(member="Member", note="Note content")
    async def note(self, interaction: discord.Interaction, member: discord.Member, note: str):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "moderator", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Moderator+ to add notes.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_action_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moderation_logs (action_id, moderator_id, target_id, action, reason) VALUES (?, ?, ?, ?, ?)",
            (action_id, interaction.user.id, member.id, "Note", note)
        )
        cursor.execute("UPDATE staff_stats SET moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = create_embed("Note Added", f"**Member:** {member.mention}\n**Note:** {note}\n**Action ID:** `{action_id}`", 0x5865f2, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, action_id, interaction.user, member, "Note", note)


async def setup(bot):
    await bot.add_cog(Moderation(bot))

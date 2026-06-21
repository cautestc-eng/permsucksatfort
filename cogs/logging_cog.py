import discord
from discord.ext import commands
import datetime
import logging

from utils import load_config, create_embed, get_channel_id

logger = logging.getLogger("OrlandoBot.Logging")


class LoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        self.reload_config()
        if message.author.bot:
            return
        log_id = get_channel_id(self.config, "mod_log")
        if not log_id:
            return
        channel = message.guild.get_channel(log_id)
        if not channel:
            return
        embed = create_embed("Message Deleted", f"**Channel:** {message.channel.mention}\n**Author:** {message.author.mention}\n**Content:** {message.content[:1000]}", 0xed4245, self.config)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        self.reload_config()
        if before.author.bot or before.content == after.content:
            return
        log_id = get_channel_id(self.config, "mod_log")
        if not log_id:
            return
        channel = before.guild.get_channel(log_id)
        if not channel:
            return
        embed = create_embed("Message Edited", f"**Channel:** {before.channel.mention}\n**Author:** {before.author.mention}\n**Before:** {before.content[:500]}\n**After:** {after.content[:500]}", 0x5865f2, self.config)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.reload_config()
        log_id = get_channel_id(self.config, "mod_log")
        if not log_id:
            return
        channel = member.guild.get_channel(log_id)
        if not channel:
            return
        embed = create_embed("Member Joined", f"**Member:** {member.mention} (`{member.id}`)\n**Account Created:** <t:{int(member.created_at.timestamp())}:R>", 0x57f287, self.config)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        self.reload_config()
        log_id = get_channel_id(self.config, "mod_log")
        if not log_id:
            return
        channel = member.guild.get_channel(log_id)
        if not channel:
            return
        embed = create_embed("Member Left", f"**Member:** {member.mention} (`{member.id}`)\n**Joined:** <t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "", 0xed4245, self.config)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        self.reload_config()
        log_id = get_channel_id(self.config, "ban_log")
        if not log_id:
            return
        channel = guild.get_channel(log_id)
        if not channel:
            return
        embed = create_embed("Member Banned", f"**User:** {user.mention} (`{user.id}`)", 0xed4245, self.config)
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                embed.add_field(name="Moderator", value=entry.user.mention, inline=True)
                embed.add_field(name="Reason", value=entry.reason or "No reason provided", inline=True)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        self.reload_config()
        log_id = get_channel_id(self.config, "ban_log")
        if not log_id:
            return
        channel = guild.get_channel(log_id)
        if not channel:
            return
        embed = create_embed("Member Unbanned", f"**User:** {user.mention} (`{user.id}`)", 0x57f287, self.config)
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
            if entry.target.id == user.id:
                embed.add_field(name="Moderator", value=entry.user.mention, inline=True)
        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LoggingCog(bot))

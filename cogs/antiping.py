import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging
import re

from database import get_connection, ensure_user
from utils import load_config, create_embed, has_permission, get_channel_id

logger = logging.getLogger("OrlandoBot.AntiPing")

OWNER_ID_PATTERN = re.compile(r"<@!?(\d+)>")


def get_antiping_role(guild_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config_cache WHERE key = ?", (f"antiping_role_{guild_id}",))
    row = cursor.fetchone()
    conn.close()
    return int(row["value"]) if row else 0


def set_antiping_role(guild_id, role_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config_cache (key, value) VALUES (?, ?)", (f"antiping_role_{guild_id}", str(role_id)))
    conn.commit()
    conn.close()


def send_antiping_log(guild, embed, config):
    log_id = get_channel_id(config, "mod_log")
    if not log_id:
        return
    channel = guild.get_channel(log_id)
    if not channel:
        return
    asyncio.ensure_future(channel.send(embed=embed))


import asyncio


class AntiPing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.ghost_ping_cache = {}

    def reload_config(self):
        self.config = load_config()

    def is_exempt(self, member):
        if not self.config:
            return False
        role_id = get_antiping_role(member.guild.id)
        if role_id and member.get_role(role_id):
            return True
        if member.guild_permissions.administrator:
            return True
        return False

    def get_mentions_from_content(self, content, guild):
        if not content:
            return [], [], False
        mentions = OWNER_ID_PATTERN.findall(content)
        mentioned_users = []
        for uid in mentions:
            user = guild.get_member(int(uid))
            if user:
                mentioned_users.append(user)
        pinged_everyone = "@everyone" in content or "@here" in content
        return mentioned_users, pinged_everyone

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        self.reload_config()

        owner = message.guild.owner
        if not owner:
            return

        if self.is_exempt(message.author):
            return

        mentioned_users, pinged_everyone = self.get_mentions_from_content(message.content, message.guild)

        if owner in mentioned_users:
            try:
                await message.delete()
            except:
                pass
            embed = create_embed(
                "Anti-Ping | Owner Ping",
                f"**User:** {message.author.mention}\n**Channel:** {message.channel.mention}\n**Action:** Message deleted (owner ping)",
                0xed4245, self.config
            )
            try:
                await message.author.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=5), reason="Anti-ping: pinged owner")
                embed.description += "\n**Timeout:** 5 minutes"
            except:
                pass
            log_id = get_channel_id(self.config, "mod_log")
            if log_id:
                channel = message.guild.get_channel(log_id)
                if channel:
                    await channel.send(embed=embed)
            try:
                await message.author.send(embed=create_embed("Anti-Ping", f"Do not ping the owner in {message.guild.name}.", 0xed4245, self.config))
            except:
                pass

        self.ghost_ping_cache[message.id] = {
            "content": message.content,
            "author": message.author,
            "mentions": mentioned_users,
            "pinged_everyone": pinged_everyone,
            "channel": message.channel,
        }

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        self.reload_config()

        cached = self.ghost_ping_cache.pop(message.id, None)
        if not cached:
            return

        if self.is_exempt(cached["author"]):
            return

        mentioned_users = cached["mentions"]
        pinged_everyone = cached["pinged_everyone"]

        if not mentioned_users and not pinged_everyone:
            return

        pinged_names = ", ".join(u.mention for u in mentioned_users)
        if pinged_everyone:
            if pinged_names:
                pinged_names += ", @everyone/@here"
            else:
                pinged_names = "@everyone/@here"

        embed = create_embed(
            "Anti-Ghost-Ping Detected",
            f"**User:** {cached['author'].mention}\n**Channel:** {cached['channel'].mention}\n**Content:** {cached['content'][:500] or '(empty)'}\n**Pinged:** {pinged_names}",
            0xfee75c, self.config
        )
        log_id = get_channel_id(self.config, "mod_log")
        if log_id:
            channel = message.guild.get_channel(log_id)
            if channel:
                await channel.send(embed=embed)

    @app_commands.command(name="setantiping", description="Set a role exempt from anti-ping measures")
    @app_commands.describe(role="Role to exempt (leave empty to check current)")
    async def setantiping(self, interaction: discord.Interaction, role: discord.Role = None):
        self.reload_config()
        if not has_permission(interaction.user, "manage_config", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Administrator+ to configure anti-ping.", 0xed4245, self.config),
                ephemeral=True
            )

        if role is None:
            current_id = get_antiping_role(interaction.guild.id)
            if current_id:
                current_role = interaction.guild.get_role(current_id)
                mention = current_role.mention if current_role else f"<@&{current_id}>"
                embed = create_embed("Anti-Ping Settings", f"**Exempt Role:** {mention}", 0x5865f2, self.config)
            else:
                embed = create_embed("Anti-Ping Settings", "**Exempt Role:** None set. All members are monitored.", 0xfee75c, self.config)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        set_antiping_role(interaction.guild.id, role.id)
        embed = create_embed("Anti-Ping Settings Updated", f"**Exempt Role:** {role.mention}\nMembers with this role will bypass anti-ping checks.", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(AntiPing(bot))

import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging

from database import get_connection, get_next_promotion_id, get_next_demotion_id, ensure_user, ensure_staff_stats
from utils import load_config, create_embed, has_permission, get_channel_id, build_promotion_embed, build_demotion_embed

logger = logging.getLogger("OrlandoBot.Promotions")


class Promotions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

    async def log_to_channel(self, guild, embed):
        log_id = get_channel_id(self.config, "staff_log")
        if not log_id:
            return
        channel = guild.get_channel(log_id)
        if not channel:
            return
        await channel.send(embed=embed)

    @app_commands.command(name="promote", description="Promote a staff member")
    @app_commands.describe(member="Staff member", previous_role="Previous role", new_role="New role", reason="Reason")
    async def promote(self, interaction: discord.Interaction, member: discord.Member, previous_role: str, new_role: str, reason: str):
        self.reload_config()
        if not has_permission(interaction.user, "manage_infractions", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Supervisor+ to promote.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot promote yourself.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_promotion_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO promotions (action_id, user_id, moderator_id, previous_role, new_role, reason) VALUES (?, ?, ?, ?, ?, ?)",
                       (action_id, member.id, interaction.user.id, previous_role, new_role, reason))
        cursor.execute("UPDATE staff_stats SET promotions_issued = promotions_issued + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?", (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = build_promotion_embed(action_id, interaction.user, member, previous_role, new_role, reason, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_to_channel(interaction.guild, embed)

    @app_commands.command(name="demote", description="Demote a staff member")
    @app_commands.describe(member="Staff member", previous_role="Previous role", new_role="New role", reason="Reason")
    async def demote(self, interaction: discord.Interaction, member: discord.Member, previous_role: str, new_role: str, reason: str):
        self.reload_config()
        if not has_permission(interaction.user, "manage_infractions", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Supervisor+ to demote.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot demote yourself.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_demotion_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO demotions (action_id, user_id, moderator_id, previous_role, new_role, reason) VALUES (?, ?, ?, ?, ?, ?)",
                       (action_id, member.id, interaction.user.id, previous_role, new_role, reason))
        cursor.execute("UPDATE staff_stats SET demotions_issued = demotions_issued + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?", (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = build_demotion_embed(action_id, interaction.user, member, previous_role, new_role, reason, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_to_channel(interaction.guild, embed)


async def setup(bot):
    await bot.add_cog(Promotions(bot))

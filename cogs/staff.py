import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging

from database import get_connection, ensure_user, ensure_staff_stats
from utils import load_config, create_embed, has_role_or_higher, get_channel_id, format_duration

logger = logging.getLogger("OrlandoBot.Staff")


class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

    @app_commands.command(name="staff_profile", description="View a staff member's profile")
    @app_commands.describe(member="Staff member to view")
    async def staff_profile(self, interaction: discord.Interaction, member: discord.Member = None):
        self.reload_config()
        member = member or interaction.user

        ensure_user(member.id, str(member))
        ensure_staff_stats(member.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (member.id,))
        user_data = cursor.fetchone()
        cursor.execute("SELECT * FROM staff_stats WHERE user_id = ?", (member.id,))
        stats = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM ssu_history WHERE host_id = ?", (member.id,))
        total_ssus = cursor.fetchone()[0]
        conn.close()

        embed = create_embed(f"Staff Profile — {member.display_name}", "", 0x2b2d31, self.config)
        embed.set_thumbnail(url=member.display_avatar.url)

        top_role = member.top_role.name if member.top_role else "No Role"
        embed.add_field(name="Rank", value=top_role, inline=True)
        embed.add_field(name="Joined Guild", value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown", inline=True)

        if user_data:
            embed.add_field(name="Total Points", value=str(user_data["total_points"] or 0), inline=True)
            embed.add_field(name="Active Infractions", value=str(user_data["active_infractions"] or 0), inline=True)
            embed.add_field(name="Warnings Given", value=str(user_data["warnings"] or 0), inline=True)

        if stats:
            embed.add_field(name="Infractions Issued", value=str(stats["infractions_issued"] or 0), inline=True)
            embed.add_field(name="Moderation Actions", value=str(stats["moderation_actions"] or 0), inline=True)
            embed.add_field(name="SSUs Hosted", value=str(stats["ssus_hosted"] or 0), inline=True)
            embed.add_field(name="SSU Duration", value=format_duration(stats["ssu_duration"] or 0), inline=True)
            embed.add_field(name="Locks Performed", value=str(stats["locks_performed"] or 0), inline=True)
            embed.add_field(name="Bans", value=str(stats["bans"] or 0), inline=True)
            embed.add_field(name="Kicks", value=str(stats["kicks"] or 0), inline=True)

        embed.add_field(name="Total SSU Sessions", value=str(total_ssus), inline=True)
        embed.set_footer(text=f"User ID: {member.id}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="staff_stats", description="View staff statistics")
    @app_commands.describe(member="Staff member")
    async def staff_stats(self, interaction: discord.Interaction, member: discord.Member = None):
        await self.staff_profile(interaction, member)

    @app_commands.command(name="staff_leaderboard", description="View staff leaderboard")
    async def staff_leaderboard(self, interaction: discord.Interaction):
        self.reload_config()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.user_id, s.infractions_issued, s.moderation_actions, s.ssus_hosted,
                   s.bans, s.kicks, s.warnings, s.locks_performed
            FROM staff_stats s
            ORDER BY s.moderation_actions DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return await interaction.response.send_message(
                embed=create_embed("Staff Leaderboard", "No staff data available yet.", 0xfee75c, self.config),
                ephemeral=True
            )

        embed = create_embed("Staff Leaderboard", "Top staff by moderation actions", 0x2b2d31, self.config)
        for i, row in enumerate(rows, 1):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"<@{row['user_id']}>"
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"`#{i}`"
            embed.add_field(
                name=f"{medal} {name}",
                value=f"**Actions:** {row['moderation_actions']} | **Infractions:** {row['infractions_issued']} | **SSUs:** {row['ssus_hosted']} | **Bans:** {row['bans']} | **Kicks:** {row['kicks']}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="staff_lookup", description="Look up a staff member's detailed statistics")
    @app_commands.describe(member="Staff member to look up")
    async def staff_lookup(self, interaction: discord.Interaction, member: discord.Member):
        await self.staff_profile(interaction, member)


async def setup(bot):
    await bot.add_cog(Staff(bot))

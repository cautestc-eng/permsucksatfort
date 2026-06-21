import discord
from discord.ext import commands
from discord import app_commands
import datetime
import json
import logging

from database import get_connection
from utils import load_config, create_embed, has_role_or_higher, format_duration

logger = logging.getLogger("OrlandoBot.Sessions")


class Sessions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

    @app_commands.command(name="session_history", description="View SSU session history")
    @app_commands.describe(page="Page number")
    async def session_history(self, interaction: discord.Interaction, page: int = 1):
        self.reload_config()
        per_page = 10
        offset = (page - 1) * per_page
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ssu_history")
        total = cursor.fetchone()[0]
        cursor.execute(
            "SELECT session_id, host_id, start_time, end_time, duration, status FROM ssu_history ORDER BY id DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return await interaction.response.send_message(
                embed=create_embed("No Sessions", "No SSU sessions found.", 0xfee75c, self.config),
                ephemeral=True
            )

        total_pages = max(1, (total + per_page - 1) // per_page)
        embed = create_embed("SSU Session History", f"Total Sessions: `{total}`", 0x2b2d31, self.config)
        for row in rows:
            host = interaction.guild.get_member(row["host_id"])
            host_name = host.display_name if host else f"<@{row['host_id']}>"
            duration = format_duration(row["duration"]) if row["duration"] else "In Progress"
            status_emoji = "🟢" if row["status"] == "active" else "🔴"
            embed.add_field(
                name=f"{status_emoji} {row['session_id']}",
                value=f"**Host:** {host_name}\n**Duration:** {duration}\n**Start:** <t:{int(datetime.datetime.fromisoformat(row['start_time']).timestamp())}:R>" if row["start_time"] else "N/A",
                inline=False
            )
        embed.set_footer(text=f"Page {page}/{total_pages}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="session_info", description="View details of a specific session")
    @app_commands.describe(session_id="Session ID (e.g., SSU-000001)")
    async def session_info(self, interaction: discord.Interaction, session_id: str):
        self.reload_config()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ssu_history WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return await interaction.response.send_message(
                embed=create_embed("Session Not Found", f"No session found with ID `{session_id}`.", 0xed4245, self.config),
                ephemeral=True
            )

        host = interaction.guild.get_member(row["host_id"])
        host_name = host.display_name if host else f"<@{row['host_id']}>"
        duration = format_duration(row["duration"]) if row["duration"] else "In Progress"

        embed = create_embed(f"Session {session_id}", f"**Status:** {row['status'].title()}", 0x2b2d31, self.config)
        embed.add_field(name="Host", value=host_name, inline=True)
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Server Code", value=row["server_code"] or "N/A", inline=True)
        if row["start_time"]:
            embed.add_field(name="Start Time", value=f"<t:{int(datetime.datetime.fromisoformat(row['start_time']).timestamp())}:F>", inline=True)
        if row["end_time"]:
            embed.add_field(name="End Time", value=f"<t:{int(datetime.datetime.fromisoformat(row['end_time']).timestamp())}:F>", inline=True)
        embed.add_field(name="Peak Players", value=str(row["peak_players"] or 0), inline=True)
        embed.add_field(name="Peak Staff", value=str(row["peak_staff"] or 0), inline=True)
        if row["notes"]:
            embed.add_field(name="Notes", value=row["notes"], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="session_delete", description="Delete a session record")
    @app_commands.describe(session_id="Session ID to delete")
    async def session_delete(self, interaction: discord.Interaction, session_id: str):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "administrator", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Administrator+ to delete sessions.", 0xed4245, self.config),
                ephemeral=True
            )
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT session_id FROM ssu_history WHERE session_id = ?", (session_id,))
        if not cursor.fetchone():
            conn.close()
            return await interaction.response.send_message(
                embed=create_embed("Session Not Found", f"No session found with ID `{session_id}`.", 0xed4245, self.config),
                ephemeral=True
            )
        cursor.execute("DELETE FROM ssu_history WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        embed = create_embed("Session Deleted", f"Session `{session_id}` has been deleted.", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="session_export", description="Export session data as JSON")
    async def session_export(self, interaction: discord.Interaction):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "administrator", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Administrator+ to export sessions.", 0xed4245, self.config),
                ephemeral=True
            )
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ssu_history ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        data = []
        for row in rows:
            data.append({
                "session_id": row["session_id"],
                "host_id": row["host_id"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "duration": row["duration"],
                "peak_players": row["peak_players"],
                "peak_staff": row["peak_staff"],
                "server_code": row["server_code"],
                "notes": row["notes"],
                "status": row["status"],
            })

        json_data = json.dumps(data, indent=2)
        with open("session_export.json", "w") as f:
            f.write(json_data)

        await interaction.response.send_message(
            embed=create_embed("Session Export", f"Exported `{len(data)}` sessions.", 0x57f287, self.config),
            file=discord.File("session_export.json"),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Sessions(bot))

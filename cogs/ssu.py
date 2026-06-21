import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import logging
import os

from database import (
    get_connection, get_next_session_id, ensure_user, ensure_staff_stats
)
from utils import (
    load_config, find_assets, create_embed, has_role_or_higher,
    get_role_id, get_channel_id, format_duration
)

logger = logging.getLogger("OrlandoBot.SSU")


class SSU(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_ssu = {}
        self.config = load_config()
        self.assets = find_assets()

    def reload_config(self):
        self.config = load_config()

    ssu_group = app_commands.Group(name="ssu", description="SSU management commands")

    @ssu_group.command(name="start", description="Start a Server Startup")
    @app_commands.describe(code="Server code (optional)")
    async def ssu_start(self, interaction: discord.Interaction, code: str = ""):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "supervisor", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Supervisor+ to start an SSU.", 0xed4245, self.config),
                ephemeral=True
            )
        if self.active_ssu.get(interaction.guild.id):
            return await interaction.response.send_message(
                embed=create_embed("SSU Already Active", "An SSU is already running. Use /ssu end to stop it.", 0xfee75c, self.config),
                ephemeral=True
            )

        await interaction.response.defer()

        session_id = get_next_session_id()
        server_code = code if code else self.config.get("server_code", "Orlando")
        start_time = datetime.datetime.utcnow()

        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ssu_history (session_id, host_id, start_time, server_code, status) VALUES (?, ?, ?, ?, 'active')",
            (session_id, interaction.user.id, start_time.isoformat(), server_code)
        )
        conn.commit()
        conn.close()

        ssu_banner_path = self.assets.get("ssu_banner")
        file = None
        if ssu_banner_path and os.path.exists(ssu_banner_path):
            file = discord.File(ssu_banner_path, filename="ssu_banner.png")

        embed = discord.Embed(
            title="",
            description=(
                f"Below you will find the detailed in-game server statistics for **{self.config.get('server_name', 'Orlando')}**.\n\n"
                "This section is dedicated to providing accurate and up-to-date information regarding server performance, "
                "activity, and statistics intended to keep the community informed and promote transparency regarding server status."
            ),
            color=self.config.get("embed_colors", {}).get("primary", 0x2b2d31),
            timestamp=datetime.datetime.utcnow()
        )
        if file:
            embed.set_image(url="attachment://ssu_banner.png")

        player_count = "12/40"
        staff_count = "5"
        embed.add_field(name="📋 Server Status", value="\u200b", inline=False)
        embed.add_field(name="Players", value=f"`{player_count}`", inline=True)
        embed.add_field(name="Staff", value=f"`{staff_count}`", inline=True)
        embed.add_field(name="Server Code", value=f"`{server_code}`", inline=True)
        embed.set_footer(text="🕒 Last Updated")

        ssu_role_id = get_role_id(self.config, "ssu_ping")
        ping_text = ""
        if ssu_role_id:
            ssu_role = interaction.guild.get_role(ssu_role_id)
            if ssu_role:
                ping_text = ssu_role.mention

        kwargs = {"embed": embed}
        if file:
            kwargs["file"] = file

        await interaction.followup.send(content=ping_text, **kwargs)

        self.active_ssu[interaction.guild.id] = {
            "session_id": session_id,
            "host_id": interaction.user.id,
            "start_time": start_time,
            "server_code": server_code,
            "message": None,
        }

        ssu_log_id = get_channel_id(self.config, "ssu_log")
        if ssu_log_id:
            log_channel = interaction.guild.get_channel(ssu_log_id)
            if log_channel:
                log_embed = create_embed(
                    "SSU Started",
                    f"**Session:** {session_id}\n**Host:** {interaction.user.mention}\n**Code:** {server_code}\n**Time:** <t:{int(start_time.timestamp())}:F>",
                    0x57f287,
                    self.config
                )
                await log_channel.send(embed=log_embed)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE staff_stats SET ssus_hosted = ssus_hosted + 1 WHERE user_id = ?", (interaction.user.id,))
        conn.commit()
        conn.close()

        logger.info(f"SSU started: {session_id} by {interaction.user}")

    @ssu_group.command(name="end", description="End the active SSU")
    async def ssu_end(self, interaction: discord.Interaction):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "supervisor", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Supervisor+ to end an SSU.", 0xed4245, self.config),
                ephemeral=True
            )
        active = self.active_ssu.get(interaction.guild.id)
        if not active:
            return await interaction.response.send_message(
                embed=create_embed("No Active SSU", "There is no active SSU to end.", 0xfee75c, self.config),
                ephemeral=True
            )

        await interaction.response.defer()

        end_time = datetime.datetime.utcnow()
        start_time = active["start_time"]
        duration_seconds = int((end_time - start_time).total_seconds())
        duration_str = format_duration(duration_seconds)
        session_id = active["session_id"]
        server_code = active["server_code"]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE ssu_history SET end_time = ?, duration = ?, status = 'ended' WHERE session_id = ?",
            (end_time.isoformat(), duration_seconds, session_id)
        )
        cursor.execute("UPDATE staff_stats SET ssu_duration = ssu_duration + ? WHERE user_id = ?",
                       (duration_seconds, active["host_id"]))
        conn.commit()
        conn.close()

        logo_path = self.assets.get("logo")
        ssd_banner_path = self.assets.get("ssd_banner")
        files = []
        embed = discord.Embed(
            title="",
            description="",
            color=self.config.get("embed_colors", {}).get("primary", 0x2b2d31),
            timestamp=datetime.datetime.utcnow()
        )

        if ssd_banner_path and os.path.exists(ssd_banner_path):
            files.append(discord.File(ssd_banner_path, filename="ssd_banner.png"))
            embed.set_image(url="attachment://ssd_banner.png")

        embed.description = (
            "We have decided to shut down the server for the day.\n\n"
            "Thank you all for attending and your continued support for the server.\n\n"
            "We will have the server back up soon."
        )

        host_user = interaction.guild.get_member(active["host_id"])
        host_mention = host_user.mention if host_user else f"<@{active['host_id']}>"

        field_data = [
            ("Host", host_mention, True),
            ("Duration", f"`{duration_str}`", True),
            ("Session ID", f"`{session_id}`", True),
            ("Server Code", f"`{server_code}`", True),
        ]
        for name, value, inline in field_data:
            embed.add_field(name=name, value=value, inline=inline)

        if logo_path and os.path.exists(logo_path):
            files.append(discord.File(logo_path, filename="logo.png"))
            embed.set_thumbnail(url="attachment://logo.png")

        embed.set_footer(text=f"Session {session_id} • Host: {host_user.display_name if host_user else 'Unknown'}" if host_user else f"Session {session_id}")

        kwargs = {"embed": embed}
        if files:
            kwargs["files"] = files

        await interaction.followup.send(**kwargs)

        ssu_log_id = get_channel_id(self.config, "ssu_log")
        if ssu_log_id:
            log_channel = interaction.guild.get_channel(ssu_log_id)
            if log_channel:
                log_embed = create_embed(
                    "SSU Ended",
                    f"**Session:** {session_id}\n**Host:** {host_mention}\n**Duration:** {duration_str}\n**End Time:** <t:{int(end_time.timestamp())}:F>",
                    0xed4245,
                    self.config
                )
                await log_channel.send(embed=log_embed)

        del self.active_ssu[interaction.guild.id]

    @ssu_group.command(name="pause", description="Pause the active SSU")
    async def ssu_pause(self, interaction: discord.Interaction):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "supervisor", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Supervisor+ to pause an SSU.", 0xed4245, self.config),
                ephemeral=True
            )
        active = self.active_ssu.get(interaction.guild.id)
        if not active:
            return await interaction.response.send_message(
                embed=create_embed("No Active SSU", "There is no active SSU to pause.", 0xfee75c, self.config),
                ephemeral=True
            )
        if active.get("paused"):
            return await interaction.response.send_message(
                embed=create_embed("Already Paused", "SSU is already paused. Use /ssu resume to continue.", 0xfee75c, self.config),
                ephemeral=True
            )
        active["paused"] = True
        active["pause_time"] = datetime.datetime.utcnow()
        embed = create_embed("SSU Paused", f"SSU `{active['session_id']}` has been paused by {interaction.user.mention}.", 0xfee75c, self.config)
        await interaction.response.send_message(embed=embed)

    @ssu_group.command(name="resume", description="Resume a paused SSU")
    async def ssu_resume(self, interaction: discord.Interaction):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "supervisor", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Supervisor+ to resume an SSU.", 0xed4245, self.config),
                ephemeral=True
            )
        active = self.active_ssu.get(interaction.guild.id)
        if not active or not active.get("paused"):
            return await interaction.response.send_message(
                embed=create_embed("Not Paused", "SSU is not currently paused.", 0xfee75c, self.config),
                ephemeral=True
            )
        active["paused"] = False
        embed = create_embed("SSU Resumed", f"SSU `{active['session_id']}` has been resumed by {interaction.user.mention}.", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)

    @ssu_group.command(name="lock", description="Lock the active SSU session")
    async def ssu_lock(self, interaction: discord.Interaction):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "supervisor", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Supervisor+ to lock SSU.", 0xed4245, self.config),
                ephemeral=True
            )
        active = self.active_ssu.get(interaction.guild.id)
        if not active:
            return await interaction.response.send_message(
                embed=create_embed("No Active SSU", "There is no active SSU.", 0xfee75c, self.config),
                ephemeral=True
            )
        active["locked"] = True
        embed = create_embed("SSU Locked", f"SSU `{active['session_id']}` has been locked. No new joins.", 0xed4245, self.config)
        await interaction.response.send_message(embed=embed)

    @ssu_group.command(name="unlock", description="Unlock the active SSU session")
    async def ssu_unlock(self, interaction: discord.Interaction):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "supervisor", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Supervisor+ to unlock SSU.", 0xed4245, self.config),
                ephemeral=True
            )
        active = self.active_ssu.get(interaction.guild.id)
        if not active or not active.get("locked"):
            return await interaction.response.send_message(
                embed=create_embed("Not Locked", "SSU is not currently locked.", 0xfee75c, self.config),
                ephemeral=True
            )
        active["locked"] = False
        embed = create_embed("SSU Unlocked", f"SSU `{active['session_id']}` has been unlocked.", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)

    @ssu_group.command(name="status", description="Check the current SSU status")
    async def ssu_status(self, interaction: discord.Interaction):
        self.reload_config()
        active = self.active_ssu.get(interaction.guild.id)
        if not active:
            return await interaction.response.send_message(
                embed=create_embed("No Active SSU", "There is no active SSU session.", 0xfee75c, self.config),
                ephemeral=True
            )
        now = datetime.datetime.utcnow()
        duration = int((now - active["start_time"]).total_seconds())
        status_parts = []
        if active.get("paused"):
            status_parts.append("⏸️ Paused")
        if active.get("locked"):
            status_parts.append("🔒 Locked")
        if not status_parts:
            status_parts.append("🟢 Active")

        embed = create_embed("SSU Status", f"**Session:** `{active['session_id']}`\n**Status:** {' • '.join(status_parts)}", 0x2b2d31, self.config)
        host = interaction.guild.get_member(active["host_id"])
        embed.add_field(name="Host", value=host.mention if host else f"<@{active['host_id']}>", inline=True)
        embed.add_field(name="Duration", value=f"`{format_duration(duration)}`", inline=True)
        embed.add_field(name="Server Code", value=f"`{active['server_code']}`", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SSU(bot))

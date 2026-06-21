import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging

from database import (
    get_connection,
    get_next_infraction_id, get_next_warning_id,
    get_next_promotion_id, get_next_demotion_id,
    get_next_suspension_id, get_next_termination_id,
    ensure_user, ensure_staff_stats, find_action_by_id
)
from utils import (
    load_config, create_embed, has_permission, get_channel_id,
    INFRACTION_CATEGORIES, build_infraction_embed, build_warning_embed,
    build_promotion_embed, build_demotion_embed, build_suspension_embed,
    build_termination_embed, get_threshold_message, get_member_role_label,
    ACTION_COLORS
)

logger = logging.getLogger("OrlandoBot.StaffActions")

ACTION_TYPES = {
    "promotion": {"color": 0x57f287, "title": "Staff Promotion"},
    "demotion": {"color": 0xe67e22, "title": "Staff Demotion"},
    "warning": {"color": 0xfee75c, "title": "Staff Warning"},
    "infraction": {"color": 0xe67e22, "title": "Staff Infraction"},
    "suspension": {"color": 0xed4245, "title": "Staff Suspension"},
    "termination": {"color": 0x8b0000, "title": "Staff Termination"},
}


class StaffActions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

    async def log_to_staff_log(self, guild, embed):
        log_id = get_channel_id(self.config, "staff_log")
        if not log_id:
            return
        channel = guild.get_channel(log_id)
        if not channel:
            return
        await channel.send(embed=embed)

    async def check_escalation(self, guild, user_id, total_points):
        threshold_msg = get_threshold_message(total_points, self.config)
        if not threshold_msg:
            return
        staff_log_id = get_channel_id(self.config, "staff_log")
        if not staff_log_id:
            return
        channel = guild.get_channel(staff_log_id)
        if not channel:
            return
        user = guild.get_member(user_id)
        user_mention = user.mention if user else f"<@{user_id}>"
        embed = create_embed("Automatic Escalation", f"**Member:** {user_mention}\n**Total Points:** {total_points}\n**Threshold:** {threshold_msg}", 0xed4245, self.config)
        await channel.send(embed=embed)

    @app_commands.command(name="infraction", description="Issue an infraction to a staff member")
    @app_commands.describe(
        member="Staff member",
        category="Infraction category",
        reason="Reason",
        evidence="Evidence link (optional)"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name=name, value=name) for name in INFRACTION_CATEGORIES.keys()
    ])
    async def infraction(self, interaction: discord.Interaction, member: discord.Member, category: str, reason: str, evidence: str = ""):
        self.reload_config()
        if not has_permission(interaction.user, "issue_infractions", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Moderator+ to issue infractions.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot infract yourself.", 0xed4245, self.config), ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(embed=create_embed("Error", "Cannot infract someone with a higher or equal role.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_infraction_id()
        point_value = INFRACTION_CATEGORIES.get(category, 0)
        if category == "Custom" and point_value == 0:
            point_value = 1

        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO infractions (action_id, user_id, moderator_id, category, reason, points, evidence_link) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (action_id, member.id, interaction.user.id, category, reason, point_value, evidence)
        )
        cursor.execute("UPDATE users SET total_points = total_points + ?, active_infractions = active_infractions + 1 WHERE user_id = ?",
                       (point_value, member.id))
        cursor.execute("UPDATE staff_stats SET infractions_issued = infractions_issued + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        cursor.execute("SELECT total_points FROM users WHERE user_id = ?", (member.id,))
        total_points = cursor.fetchone()["total_points"]
        conn.commit()
        conn.close()

        embed = build_infraction_embed(action_id, interaction.user, member, category, reason, point_value, evidence, total_points, self.config)
        await interaction.response.send_message(embed=embed)

        await self.log_to_staff_log(interaction.guild, embed)
        await self.check_escalation(interaction.guild, member.id, total_points)

        infraction_log_id = get_channel_id(self.config, "infraction_log")
        if infraction_log_id:
            channel = interaction.guild.get_channel(infraction_log_id)
            if channel:
                await channel.send(embed=embed)

    @app_commands.command(name="warn", description="Issue a warning to a staff member")
    @app_commands.describe(member="Staff member", reason="Reason", points="Warning points (1-5)")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str, points: int = 1):
        self.reload_config()
        if not has_permission(interaction.user, "warn", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Moderator+ to warn.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot warn yourself.", 0xed4245, self.config), ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(embed=create_embed("Error", "Cannot warn higher role.", 0xed4245, self.config), ephemeral=True)

        points = max(1, min(points, 5))
        action_id = get_next_warning_id()

        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO warnings (action_id, user_id, moderator_id, reason, points) VALUES (?, ?, ?, ?, ?)",
            (action_id, member.id, interaction.user.id, reason, points)
        )
        cursor.execute("UPDATE users SET total_points = total_points + ?, warnings = warnings + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (points, member.id))
        cursor.execute("UPDATE staff_stats SET warnings = warnings + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        cursor.execute("SELECT total_points FROM users WHERE user_id = ?", (member.id,))
        total_points = cursor.fetchone()["total_points"]
        conn.commit()
        conn.close()

        embed = build_warning_embed(action_id, interaction.user, member, reason, points, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_to_staff_log(interaction.guild, embed)
        await self.check_escalation(interaction.guild, member.id, total_points)

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
        cursor.execute(
            "INSERT INTO promotions (action_id, user_id, moderator_id, previous_role, new_role, reason) VALUES (?, ?, ?, ?, ?, ?)",
            (action_id, member.id, interaction.user.id, previous_role, new_role, reason)
        )
        cursor.execute("UPDATE staff_stats SET promotions_issued = promotions_issued + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = build_promotion_embed(action_id, interaction.user, member, previous_role, new_role, reason, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_to_staff_log(interaction.guild, embed)

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
        cursor.execute(
            "INSERT INTO demotions (action_id, user_id, moderator_id, previous_role, new_role, reason) VALUES (?, ?, ?, ?, ?, ?)",
            (action_id, member.id, interaction.user.id, previous_role, new_role, reason)
        )
        cursor.execute("UPDATE staff_stats SET demotions_issued = demotions_issued + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = build_demotion_embed(action_id, interaction.user, member, previous_role, new_role, reason, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_to_staff_log(interaction.guild, embed)

    @app_commands.command(name="suspend", description="Suspend a staff member")
    @app_commands.describe(member="Staff member", duration_days="Duration in days", reason="Reason", related_infraction="Related infraction ID (optional)")
    async def suspend(self, interaction: discord.Interaction, member: discord.Member, duration_days: int, reason: str, related_infraction: str = ""):
        self.reload_config()
        if not has_permission(interaction.user, "manage_infractions", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Supervisor+ to suspend.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot suspend yourself.", 0xed4245, self.config), ephemeral=True)

        action_id = get_next_suspension_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO suspensions (action_id, user_id, moderator_id, duration_days, reason, related_infraction) VALUES (?, ?, ?, ?, ?, ?)",
            (action_id, member.id, interaction.user.id, duration_days, reason, related_infraction)
        )
        cursor.execute("UPDATE staff_stats SET suspensions_issued = suspensions_issued + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = build_suspension_embed(action_id, interaction.user, member, duration_days, reason, related_infraction, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_to_staff_log(interaction.guild, embed)

    @app_commands.command(name="terminate", description="Terminate a staff member")
    @app_commands.describe(member="Staff member", reason="Reason")
    async def terminate(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        self.reload_config()
        if not has_permission(interaction.user, "manage_infractions", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Supervisor+ to terminate.", 0xed4245, self.config), ephemeral=True)
        if member == interaction.user:
            return await interaction.response.send_message(embed=create_embed("Error", "You cannot terminate yourself.", 0xed4245, self.config), ephemeral=True)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT total_points, active_infractions FROM users WHERE user_id = ?", (member.id,))
        stats = cursor.fetchone()
        total_points = stats["total_points"] if stats else 0
        active_inf = stats["active_infractions"] if stats else 0
        conn.close()

        action_id = get_next_termination_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO terminations (action_id, user_id, moderator_id, total_points, active_infractions, reason) VALUES (?, ?, ?, ?, ?, ?)",
            (action_id, member.id, interaction.user.id, total_points, active_inf, reason)
        )
        cursor.execute("UPDATE staff_stats SET terminations_issued = terminations_issued + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        conn.commit()
        conn.close()

        embed = build_termination_embed(action_id, interaction.user, member, total_points, active_inf, reason, self.config)
        await interaction.response.send_message(embed=embed)
        await self.log_to_staff_log(interaction.guild, embed)

    @app_commands.command(name="findid", description="Find and display an action by its ID")
    @app_commands.describe(action_id="Action ID (e.g., INF-XXXXXXXX, PROM-XXXXXXXX)")
    async def findid(self, interaction: discord.Interaction, action_id: str):
        self.reload_config()
        table, row = find_action_by_id(action_id)
        if not row:
            return await interaction.response.send_message(embed=create_embed("Not Found", f"No action found with ID `{action_id}`.", 0xed4245, self.config), ephemeral=True)

        moderator = interaction.guild.get_member(row["moderator_id"])
        if not moderator:
            return await interaction.response.send_message(embed=create_embed("Error", "Moderator not found in this server.", 0xed4245, self.config), ephemeral=True)

        target = interaction.guild.get_member(row["user_id"])
        if not target:
            return await interaction.response.send_message(embed=create_embed("Error", "Target user not found in this server.", 0xed4245, self.config), ephemeral=True)

        embed = None
        if table == "infractions":
            embed = build_infraction_embed(
                row["action_id"], moderator, target,
                row["category"], row["reason"], row["points"],
                row["evidence_link"] or "",
                None, self.config
            )
        elif table == "warnings":
            embed = build_warning_embed(row["action_id"], moderator, target, row["reason"], row["points"], self.config)
        elif table == "promotions":
            embed = build_promotion_embed(row["action_id"], moderator, target, row["previous_role"], row["new_role"], row["reason"], self.config)
        elif table == "demotions":
            embed = build_demotion_embed(row["action_id"], moderator, target, row["previous_role"], row["new_role"], row["reason"], self.config)
        elif table == "suspensions":
            embed = build_suspension_embed(row["action_id"], moderator, target, row["duration_days"], row["reason"], row["related_infraction"] or "", self.config)
        elif table == "terminations":
            embed = build_termination_embed(row["action_id"], moderator, target, row["total_points"], row["active_infractions"], row["reason"], self.config)

        if embed:
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=create_embed("Error", "Could not rebuild embed for this action type.", 0xed4245, self.config), ephemeral=True)

    @app_commands.command(name="history", description="View all staff actions for a user")
    @app_commands.describe(member="Staff member to look up")
    async def history(self, interaction: discord.Interaction, member: discord.Member):
        self.reload_config()
        if not has_permission(interaction.user, "view_history", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Trial Moderator+ to view history.", 0xed4245, self.config), ephemeral=True)

        conn = get_connection()
        cursor = conn.cursor()
        results = []

        for table, prefix in [("infractions", "INF"), ("warnings", "WARN"), ("promotions", "PROM"),
                               ("demotions", "DEMO"), ("suspensions", "SUS"), ("terminations", "TERM")]:
            cursor.execute(f"SELECT action_id, timestamp FROM {table} WHERE user_id = ? ORDER BY id DESC LIMIT 10", (member.id,))
            for row in cursor.fetchall():
                results.append((row["action_id"], row["timestamp"], prefix))

        results.sort(key=lambda x: x[1] or "", reverse=True)
        conn.close()

        if not results:
            return await interaction.response.send_message(embed=create_embed("No History", f"No actions found for {member.display_name}.", 0xfee75c, self.config), ephemeral=True)

        embed = discord.Embed(
            title="",
            description=f"**Action History — {member.display_name}**",
            color=0x2b2d31,
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        for action_id, ts, prefix in results[:20]:
            label = {"INF": "Infraction", "WARN": "Warning", "PROM": "Promotion",
                     "DEMO": "Demotion", "SUS": "Suspension", "TERM": "Termination"}.get(prefix, "Action")
            time_str = f"<t:{int(datetime.datetime.fromisoformat(ts).timestamp())}:R>" if ts else "Unknown"
            embed.add_field(name=f"{label} | {action_id}", value=time_str, inline=False)

        embed.set_footer(text=f"{self.config.get('server_name', 'Server')} • {member.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="staffprofile", description="View a staff member's full profile")
    @app_commands.describe(member="Staff member")
    async def staffprofile(self, interaction: discord.Interaction, member: discord.Member):
        self.reload_config()
        if not has_permission(interaction.user, "view_stats", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Trial Moderator+ to view profiles.", 0xed4245, self.config), ephemeral=True)

        ensure_user(member.id, str(member))
        ensure_staff_stats(member.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (member.id,))
        user_data = cursor.fetchone()
        cursor.execute("SELECT * FROM staff_stats WHERE user_id = ?", (member.id,))
        stats = cursor.fetchone()

        for table in ["infractions", "warnings", "promotions", "demotions", "suspensions", "terminations"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (member.id,))
            setattr(self, f"count_{table}", cursor.fetchone()[0])
        conn.close()

        rank_label = get_member_role_label(member, self.config)
        embed = discord.Embed(
            title="",
            description=f"**Staff Profile — {member.display_name}**",
            color=0x2b2d31,
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="Rank", value=rank_label, inline=True)
        embed.add_field(name="Total Actions", value=str(stats["moderation_actions"] if stats else 0), inline=True)
        embed.add_field(name="Total Points", value=str(user_data["total_points"] if user_data else 0), inline=True)
        embed.add_field(name="Active Infractions", value=str(user_data["active_infractions"] if user_data else 0), inline=True)
        embed.add_field(name="Warnings", value=str(self.count_warnings), inline=True)
        embed.add_field(name="Infractions", value=str(self.count_infractions), inline=True)
        embed.add_field(name="Promotions", value=str(self.count_promotions), inline=True)
        embed.add_field(name="Demotions", value=str(self.count_demotions), inline=True)
        embed.add_field(name="Suspensions", value=str(self.count_suspensions), inline=True)
        embed.add_field(name="Terminations", value=str(self.count_terminations), inline=True)
        embed.add_field(name="SSUs Hosted", value=str(stats["ssus_hosted"] if stats else 0), inline=True)
        embed.add_field(name="Bans / Kicks", value=f"{stats['bans'] if stats else 0} / {stats['kicks'] if stats else 0}", inline=True)

        embed.set_footer(text=f"{self.config.get('server_name', 'Server')} • {member.display_name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="activeinfractions", description="View active infractions for a user")
    @app_commands.describe(member="Staff member")
    async def activeinfractions(self, interaction: discord.Interaction, member: discord.Member):
        self.reload_config()
        if not has_permission(interaction.user, "view_infractions", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Trial Moderator+ to view infractions.", 0xed4245, self.config), ephemeral=True)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM infractions WHERE user_id = ? AND active = 1 ORDER BY id DESC LIMIT 25", (member.id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return await interaction.response.send_message(embed=create_embed("No Active Infractions", f"{member.display_name} has no active infractions.", 0x57f287, self.config), ephemeral=True)

        embed = discord.Embed(
            title="",
            description=f"**Active Infractions — {member.display_name}**",
            color=0xe67e22,
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        for row in rows[:10]:
            mod = interaction.guild.get_member(row["moderator_id"])
            mod_name = mod.display_name if mod else "Unknown"
            embed.add_field(
                name=f"`{row['action_id']}` — {row['category']} (+{row['points']})",
                value=f"**Reason:** {row['reason']}\n**Mod:** {mod_name}\n**Date:** <t:{int(datetime.datetime.fromisoformat(row['timestamp']).timestamp())}:R>" if row["timestamp"] else "",
                inline=False
            )

        embed.set_footer(text=f"{self.config.get('server_name', 'Server')} • {member.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="infraction_remove", description="Remove an infraction (deactivates it)")
    @app_commands.describe(action_id="Action ID to remove", reason="Reason for removal")
    async def infraction_remove(self, interaction: discord.Interaction, action_id: str, reason: str):
        self.reload_config()
        if not has_permission(interaction.user, "remove_infractions", self.config):
            return await interaction.response.send_message(embed=create_embed("Permission Denied", "You need Administrator+ to remove infractions.", 0xed4245, self.config), ephemeral=True)

        table, row = find_action_by_id(action_id)
        if not row or table not in ("infractions", "warnings"):
            return await interaction.response.send_message(embed=create_embed("Not Found", f"No infraction/warning found with ID `{action_id}`.", 0xed4245, self.config), ephemeral=True)

        conn = get_connection()
        cursor = conn.cursor()
        if table == "infractions":
            cursor.execute("UPDATE infractions SET active = 0 WHERE action_id = ?", (action_id,))
            cursor.execute("UPDATE users SET active_infractions = MAX(0, active_infractions - 1), total_points = MAX(0, total_points - ?) WHERE user_id = ?",
                           (row["points"], row["user_id"]))
        elif table == "warnings":
            cursor.execute("UPDATE warnings SET active = 0 WHERE action_id = ?", (action_id,))
            cursor.execute("UPDATE users SET total_points = MAX(0, total_points - ?), warnings = MAX(0, warnings - 1) WHERE user_id = ?",
                           (row["points"], row["user_id"]))
        conn.commit()
        conn.close()

        embed = create_embed("Infraction Removed", f"**Action:** `{action_id}`\n**Reason:** {reason}", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(StaffActions(bot))

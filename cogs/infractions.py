import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging

from database import get_connection, get_next_infraction_id, ensure_user, ensure_staff_stats
from utils import (
    load_config, create_embed, has_role_or_higher,
    get_channel_id, get_threshold_message, INFRACTION_CATEGORIES
)

logger = logging.getLogger("OrlandoBot.Infractions")


@app_commands.guild_only()
class Infractions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

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
        embed = create_embed(
            "Automatic Escalation Triggered",
            f"**Member:** {user_mention}\n**Total Points:** {total_points}\n**Threshold:** {threshold_msg}",
            0xed4245,
            self.config
        )
        await channel.send(embed=embed)

    @app_commands.command(name="infraction_issue", description="Issue an infraction to a member")
    @app_commands.describe(
        member="Member to issue infraction to",
        category="Infraction category",
        reason="Reason for the infraction",
        points="Custom points (only for Custom category)",
        evidence="Evidence link (optional)"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name=name, value=name) for name in INFRACTION_CATEGORIES.keys()
    ])
    async def infraction_issue(
        self, interaction: discord.Interaction,
        member: discord.Member,
        category: str,
        reason: str,
        points: int = 0,
        evidence: str = ""
    ):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "moderator", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Moderator+ to issue infractions.", 0xed4245, self.config),
                ephemeral=True
            )
        if member == interaction.user:
            return await interaction.response.send_message(
                embed=create_embed("Error", "You cannot issue an infraction to yourself.", 0xed4245, self.config),
                ephemeral=True
            )
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                embed=create_embed("Error", "You cannot infract someone with a higher or equal role.", 0xed4245, self.config),
                ephemeral=True
            )

        if category == "Custom":
            point_value = points if points > 0 else 0
        else:
            point_value = INFRACTION_CATEGORIES.get(category, 0)

        if point_value <= 0 and category != "Custom":
            return await interaction.response.send_message(
                embed=create_embed("Error", "Invalid infraction category.", 0xed4245, self.config),
                ephemeral=True
            )

        infraction_id = get_next_infraction_id()
        ensure_user(member.id, str(member))
        ensure_user(interaction.user.id, str(interaction.user))
        ensure_staff_stats(interaction.user.id)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO infractions (infraction_id, user_id, moderator_id, reason, points, category, infraction_type, evidence_link) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (infraction_id, member.id, interaction.user.id, reason, point_value, category, category, evidence)
        )
        cursor.execute("UPDATE users SET total_points = total_points + ?, active_infractions = active_infractions + 1 WHERE user_id = ?",
                       (point_value, member.id))
        cursor.execute("UPDATE staff_stats SET infractions_issued = infractions_issued + 1, moderation_actions = moderation_actions + 1 WHERE user_id = ?",
                       (interaction.user.id,))
        cursor.execute("SELECT total_points FROM users WHERE user_id = ?", (member.id,))
        total_points = cursor.fetchone()["total_points"]
        conn.commit()
        conn.close()

        embed = create_embed("Infraction Issued", f"**Member:** {member.mention}\n**Category:** {category}\n**Points:** {point_value}\n**Reason:** {reason}\n**ID:** `{infraction_id}`", 0xfee75c, self.config)
        if evidence:
            embed.add_field(name="Evidence", value=evidence, inline=False)
        await interaction.response.send_message(embed=embed)

        await self.check_escalation(interaction.guild, member.id, total_points)

        infraction_log_id = get_channel_id(self.config, "infraction_log")
        if infraction_log_id:
            log_channel = interaction.guild.get_channel(infraction_log_id)
            if log_channel:
                log_embed = create_embed(
                    f"Infraction | {infraction_id}",
                    f"**Member:** {member.mention} (`{member.id}`)\n**Moderator:** {interaction.user.mention}\n**Category:** {category}\n**Points:** {point_value}\n**Reason:** {reason}",
                    0xfee75c, self.config
                )
                await log_channel.send(embed=log_embed)

    @app_commands.command(name="infraction_remove", description="Remove an infraction")
    @app_commands.describe(infraction_id="Infraction ID to remove", reason="Reason for removal")
    async def infraction_remove(self, interaction: discord.Interaction, infraction_id: str, reason: str):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "administrator", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Administrator+ to remove infractions.", 0xed4245, self.config),
                ephemeral=True
            )

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM infractions WHERE infraction_id = ?", (infraction_id,))
        infraction = cursor.fetchone()
        if not infraction:
            conn.close()
            return await interaction.response.send_message(
                embed=create_embed("Not Found", f"Infraction `{infraction_id}` not found.", 0xed4245, self.config),
                ephemeral=True
            )

        cursor.execute("DELETE FROM infractions WHERE infraction_id = ?", (infraction_id,))
        cursor.execute("UPDATE users SET total_points = MAX(0, total_points - ?), active_infractions = MAX(0, active_infractions - 1) WHERE user_id = ?",
                       (infraction["points"], infraction["user_id"]))
        conn.commit()
        conn.close()

        embed = create_embed("Infraction Removed", f"**Infraction:** `{infraction_id}`\n**Reason:** {reason}", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="infraction_edit", description="Edit an infraction")
    @app_commands.describe(
        infraction_id="Infraction ID to edit",
        reason="New reason",
        points="New points (optional)",
        evidence="New evidence link (optional)"
    )
    async def infraction_edit(self, interaction: discord.Interaction, infraction_id: str, reason: str = None, points: int = None, evidence: str = None):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "administrator", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Administrator+ to edit infractions.", 0xed4245, self.config),
                ephemeral=True
            )

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM infractions WHERE infraction_id = ?", (infraction_id,))
        infraction = cursor.fetchone()
        if not infraction:
            conn.close()
            return await interaction.response.send_message(
                embed=create_embed("Not Found", f"Infraction `{infraction_id}` not found.", 0xed4245, self.config),
                ephemeral=True
            )

        update_fields = []
        update_values = []
        if reason:
            update_fields.append("reason = ?")
            update_values.append(reason)
        if evidence is not None:
            update_fields.append("evidence_link = ?")
            update_values.append(evidence)
        if points and points > 0:
            old_points = infraction["points"]
            diff = points - old_points
            update_fields.append("points = ?")
            update_values.append(points)
            cursor.execute("UPDATE users SET total_points = MAX(0, total_points + ?) WHERE user_id = ?",
                           (diff, infraction["user_id"]))

        if update_fields:
            update_fields.append("edited = 1")
            update_values.append(infraction_id)
            cursor.execute(f"UPDATE infractions SET {', '.join(update_fields)} WHERE infraction_id = ?", update_values)
            conn.commit()

        conn.close()
        embed = create_embed("Infraction Edited", f"**Infraction:** `{infraction_id}` has been updated.", 0x5865f2, self.config)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="infraction_view", description="View details of a specific infraction")
    @app_commands.describe(infraction_id="Infraction ID")
    async def infraction_view(self, interaction: discord.Interaction, infraction_id: str):
        self.reload_config()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM infractions WHERE infraction_id = ?", (infraction_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return await interaction.response.send_message(
                embed=create_embed("Not Found", f"Infraction `{infraction_id}` not found.", 0xed4245, self.config),
                ephemeral=True
            )

        user = interaction.guild.get_member(row["user_id"])
        mod = interaction.guild.get_member(row["moderator_id"])
        status = "🟢 Active" if row["active"] else "🔴 Removed"

        embed = create_embed(f"Infraction {infraction_id}", f"**Status:** {status}", 0x2b2d31, self.config)
        embed.add_field(name="Member", value=user.mention if user else f"<@{row['user_id']}>", inline=True)
        embed.add_field(name="Moderator", value=mod.mention if mod else f"<@{row['moderator_id']}>", inline=True)
        embed.add_field(name="Category", value=row["category"], inline=True)
        embed.add_field(name="Points", value=str(row["points"]), inline=True)
        embed.add_field(name="Reason", value=row["reason"], inline=False)
        if row["evidence_link"]:
            embed.add_field(name="Evidence", value=row["evidence_link"], inline=False)
        if row["timestamp"]:
            embed.add_field(name="Date", value=f"<t:{int(datetime.datetime.fromisoformat(row['timestamp']).timestamp())}:F>", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="infraction_history", description="View infraction history for a member")
    @app_commands.describe(member="Member to look up")
    async def infraction_history(self, interaction: discord.Interaction, member: discord.Member):
        self.reload_config()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM infractions WHERE user_id = ? ORDER BY id DESC LIMIT 25", (member.id,))
        rows = cursor.fetchall()
        cursor.execute("SELECT total_points, active_infractions FROM users WHERE user_id = ?", (member.id,))
        stats = cursor.fetchone()
        conn.close()

        embed = create_embed(f"Infraction History — {member.display_name}", f"**Total Points:** {stats['total_points'] if stats else 0} | **Active Infractions:** {stats['active_infractions'] if stats else 0}", 0x2b2d31, self.config)

        if not rows:
            embed.description = "No infractions found for this member."
        else:
            for row in rows[:10]:
                mod = interaction.guild.get_member(row["moderator_id"])
                mod_name = mod.display_name if mod else f"<@{row['moderator_id']}>"
                embed.add_field(
                    name=f"`{row['infraction_id']}` — {row['category']} ({'+' + str(row['points'])})",
                    value=f"**Reason:** {row['reason']}\n**Mod:** {mod_name}\n**Status:** {'🟢' if row['active'] else '🔴'}",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="infraction_search", description="Search infractions by criteria")
    @app_commands.describe(query="Search query (member ID, reason, or infraction ID)")
    async def infraction_search(self, interaction: discord.Interaction, query: str):
        self.reload_config()
        conn = get_connection()
        cursor = conn.cursor()
        pattern = f"%{query}%"
        cursor.execute(
            "SELECT * FROM infractions WHERE infraction_id LIKE ? OR reason LIKE ? OR CAST(user_id AS TEXT) LIKE ? ORDER BY id DESC LIMIT 25",
            (pattern, pattern, pattern)
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return await interaction.response.send_message(
                embed=create_embed("No Results", f"No infractions found matching `{query}`.", 0xfee75c, self.config),
                ephemeral=True
            )

        embed = create_embed("Infraction Search Results", f"Found `{len(rows)}` results for `{query}`", 0x2b2d31, self.config)
        for row in rows[:10]:
            user = interaction.guild.get_member(row["user_id"])
            user_name = user.display_name if user else f"<@{row['user_id']}>"
            embed.add_field(
                name=f"`{row['infraction_id']}` — {user_name}",
                value=f"**Category:** {row['category']} | **Points:** {row['points']}\n**Reason:** {row['reason'][:100]}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="infraction_leaderboard", description="View the infraction points leaderboard")
    async def infraction_leaderboard(self, interaction: discord.Interaction):
        self.reload_config()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, total_points, active_infractions FROM users WHERE total_points > 0 ORDER BY total_points DESC LIMIT 20")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return await interaction.response.send_message(
                embed=create_embed("Leaderboard", "No infractions recorded yet.", 0xfee75c, self.config),
                ephemeral=True
            )

        embed = create_embed("Infraction Points Leaderboard", "Top members by total infraction points", 0x2b2d31, self.config)
        for i, row in enumerate(rows, 1):
            user = interaction.guild.get_member(row["user_id"])
            user_name = user.display_name if user else f"<@{row['user_id']}>"
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"`#{i}`"
            embed.add_field(
                name=f"{medal} {user_name}",
                value=f"**Points:** {row['total_points']} | **Active Infractions:** {row['active_infractions']}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Infractions(bot))

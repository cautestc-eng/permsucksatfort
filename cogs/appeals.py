import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging

from database import get_connection, get_next_appeal_id, ensure_user
from utils import load_config, create_embed, has_role_or_higher

logger = logging.getLogger("OrlandoBot.Appeals")


class Appeals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

    @app_commands.command(name="appeal_create", description="Create an appeal for an infraction")
    @app_commands.describe(infraction_id="Infraction ID to appeal", reason="Reason for your appeal")
    async def appeal_create(self, interaction: discord.Interaction, infraction_id: str, reason: str):
        self.reload_config()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM infractions WHERE infraction_id = ? AND user_id = ?",
                       (infraction_id, interaction.user.id))
        infraction = cursor.fetchone()

        if not infraction:
            cursor.execute("SELECT * FROM infractions WHERE infraction_id = ?", (infraction_id,))
            infraction = cursor.fetchone()
            if not infraction:
                conn.close()
                return await interaction.response.send_message(
                    embed=create_embed("Not Found", f"Infraction `{infraction_id}` not found.", 0xed4245, self.config),
                    ephemeral=True
                )

        cursor.execute("SELECT appeal_id FROM appeals WHERE infraction_id = ? AND status = 'pending'", (infraction_id,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return await interaction.response.send_message(
                embed=create_embed("Already Pending", f"An appeal for `{infraction_id}` is already pending: `{existing['appeal_id']}`.", 0xfee75c, self.config),
                ephemeral=True
            )

        appeal_id = get_next_appeal_id()
        ensure_user(interaction.user.id, str(interaction.user))

        cursor.execute(
            "INSERT INTO appeals (appeal_id, infraction_id, user_id, reason) VALUES (?, ?, ?, ?)",
            (appeal_id, infraction_id, interaction.user.id, reason)
        )
        conn.commit()
        conn.close()

        embed = create_embed("Appeal Created", f"**Appeal ID:** `{appeal_id}`\n**Infraction:** `{infraction_id}`\n**Reason:** {reason}\n\nYour appeal will be reviewed by staff.", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="appeal_accept", description="Accept a pending appeal")
    @app_commands.describe(appeal_id="Appeal ID to accept", message="Resolution message")
    async def appeal_accept(self, interaction: discord.Interaction, appeal_id: str, message: str = "Appeal accepted."):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "administrator", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Administrator+ to accept appeals.", 0xed4245, self.config),
                ephemeral=True
            )

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM appeals WHERE appeal_id = ?", (appeal_id,))
        appeal = cursor.fetchone()
        if not appeal:
            conn.close()
            return await interaction.response.send_message(
                embed=create_embed("Not Found", f"Appeal `{appeal_id}` not found.", 0xed4245, self.config),
                ephemeral=True
            )
        if appeal["status"] != "pending":
            conn.close()
            return await interaction.response.send_message(
                embed=create_embed("Already Resolved", f"Appeal `{appeal_id}` is already {appeal['status']}.", 0xfee75c, self.config),
                ephemeral=True
            )

        cursor.execute(
            "UPDATE appeals SET status = 'accepted', resolved_by = ?, resolution_message = ? WHERE appeal_id = ?",
            (interaction.user.id, message, appeal_id)
        )
        cursor.execute("UPDATE infractions SET active = 0 WHERE infraction_id = ?", (appeal["infraction_id"],))
        cursor.execute("UPDATE users SET active_infractions = MAX(0, active_infractions - 1) WHERE user_id = ?",
                       (appeal["user_id"],))
        conn.commit()
        conn.close()

        embed = create_embed("Appeal Accepted", f"**Appeal:** `{appeal_id}`\n**Infraction:** `{appeal['infraction_id']}`\n**Resolution:** {message}", 0x57f287, self.config)
        await interaction.response.send_message(embed=embed)

        try:
            user = await self.bot.fetch_user(appeal["user_id"])
            await user.send(embed=create_embed("Appeal Accepted", f"Your appeal for `{appeal['infraction_id']}` has been accepted.\n**Message:** {message}", 0x57f287, self.config))
        except:
            pass

    @app_commands.command(name="appeal_deny", description="Deny a pending appeal")
    @app_commands.describe(appeal_id="Appeal ID to deny", message="Denial reason")
    async def appeal_deny(self, interaction: discord.Interaction, appeal_id: str, message: str = "Appeal denied."):
        self.reload_config()
        if not has_role_or_higher(interaction.user, "administrator", self.config):
            return await interaction.response.send_message(
                embed=create_embed("Permission Denied", "You need Administrator+ to deny appeals.", 0xed4245, self.config),
                ephemeral=True
            )

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM appeals WHERE appeal_id = ?", (appeal_id,))
        appeal = cursor.fetchone()
        if not appeal:
            conn.close()
            return await interaction.response.send_message(
                embed=create_embed("Not Found", f"Appeal `{appeal_id}` not found.", 0xed4245, self.config),
                ephemeral=True
            )
        if appeal["status"] != "pending":
            conn.close()
            return await interaction.response.send_message(
                embed=create_embed("Already Resolved", f"Appeal `{appeal_id}` is already {appeal['status']}.", 0xfee75c, self.config),
                ephemeral=True
            )

        cursor.execute(
            "UPDATE appeals SET status = 'denied', resolved_by = ?, resolution_message = ? WHERE appeal_id = ?",
            (interaction.user.id, message, appeal_id)
        )
        conn.commit()
        conn.close()

        embed = create_embed("Appeal Denied", f"**Appeal:** `{appeal_id}`\n**Infraction:** `{appeal['infraction_id']}`\n**Reason:** {message}", 0xed4245, self.config)
        await interaction.response.send_message(embed=embed)

        try:
            user = await self.bot.fetch_user(appeal["user_id"])
            await user.send(embed=create_embed("Appeal Denied", f"Your appeal for `{appeal['infraction_id']}` has been denied.\n**Reason:** {message}", 0xed4245, self.config))
        except:
            pass


async def setup(bot):
    await bot.add_cog(Appeals(bot))

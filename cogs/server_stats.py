import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import logging
import os
import aiohttp
import json

from database import get_connection
from utils import load_config, create_embed, get_channel_id

logger = logging.getLogger("OrlandoBot.ServerStats")


class ServerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.api_url = os.environ.get("MELONLY_API_URL", "")
        self.api_key = os.environ.get("MELONLY_API_KEY", "")
        self.players = 12
        self.staff = 5
        self.max_players = self.config.get("max_players", 40)
        self.server_code = self.config.get("server_code", "SanDIEGO")
        self.last_updated = datetime.datetime.utcnow()

    def reload_config(self):
        self.config = load_config()
        self.max_players = self.config.get("max_players", 40)
        self.server_code = self.config.get("server_code", "SanDIEGO")

    async def fetch_server_stats(self):
        if not self.api_url:
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.api_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.players = data.get("players", self.players)
                        self.staff = data.get("staff", self.staff)
                        self.max_players = data.get("max_players", self.max_players)
                        self.last_updated = datetime.datetime.utcnow()

                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM server_stats_cache")
                        cursor.execute(
                            "INSERT INTO server_stats_cache (players, staff, max_players) VALUES (?, ?, ?)",
                            (self.players, self.staff, self.max_players)
                        )
                        conn.commit()
                        conn.close()
                        return True
                    logger.warning(f"API returned status {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to fetch server stats: {e}")
            return False

    @app_commands.command(name="server_update", description="Manually update server statistics")
    async def server_update(self, interaction: discord.Interaction):
        self.reload_config()
        await interaction.response.defer(ephemeral=True)

        success = await self.fetch_server_stats()
        if success:
            embed = create_embed("Server Stats Updated", f"**Players:** {self.players}/{self.max_players}\n**Staff:** {self.staff}", 0x57f287, self.config)
        else:
            embed = create_embed("Server Stats", "External API unavailable. Using manual values.", 0xfee75c, self.config)
            embed.add_field(name="Players", value=f"{self.players}/{self.max_players}", inline=True)
            embed.add_field(name="Staff", value=str(self.staff), inline=True)
            embed.add_field(name="Server Code", value=f"`{self.server_code}`", inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="server_players", description="View current player count")
    async def server_players(self, interaction: discord.Interaction):
        self.reload_config()
        embed = create_embed("Server Players", f"**Players:** {self.players}/{self.max_players}\n**Staff:** {self.staff}\n**Last Updated:** <t:{int(self.last_updated.timestamp())}:R>", 0x2b2d31, self.config)
        embed.set_footer(text=f"Server Code: {self.server_code}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server_staff", description="View current staff count")
    async def server_staff(self, interaction: discord.Interaction):
        self.reload_config()
        embed = create_embed("Server Staff", f"**Online Staff:** {self.staff}\n**Last Updated:** <t:{int(self.last_updated.timestamp())}:R>", 0x2b2d31, self.config)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ServerStats(bot))

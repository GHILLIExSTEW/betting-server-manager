#   bot/services/leaderboard_handler.py

import logging
import discord
from discord import Interaction
from discord.ui import View, Select
import io
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from bot.data.db_manager import DatabaseManager

db_manager = DatabaseManager()

class ChannelSelectForLeaderboard(Select):
    def __init__(self, guild: discord.Guild):
        options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in guild.text_channels]
        super().__init__(placeholder="Select Channel", options=options or [discord.SelectOption(label="No channels", value="none")], min_values=1, max_values=1)
        self.guild = guild

    async def callback(self, interaction: Interaction):
        channel_id = self.values[0]
        if channel_id == "none":
            await interaction.response.send_message("No channel selected.", ephemeral=True)
            return
        try:
            query = """
                SELECT user_id, SUM(CASE WHEN bet_won = 1 THEN units ELSE 0 END) as total_units
                FROM bets
                WHERE bet_won = 1
                GROUP BY user_id
                ORDER BY total_units DESC
                LIMIT 5
            """
            results = await db_manager.fetch(query)
            if not results:
                await interaction.response.send_message("No leaderboard data available.", ephemeral=True)
                return

            fig = plt.figure(figsize=(12, 10))
            gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1])
            ax_text = fig.add_subplot(gs[0, 0])
            ax_bar = fig.add_subplot(gs[1, 0])

            # Text stats
            stats_text = "Leaderboard - Top 5 Bettors:\n\n"
            for i, (user_id, units) in enumerate(results, 1):
                user = self.guild.get_member(int(user_id))
                display_name = user.display_name if user else f"User {user_id}"
                stats_text += f"{i}. {display_name}: {units} units\n"
            ax_text.text(0, 0.5, stats_text, fontsize=18, ha='left', va='center')
            ax_text.axis('off')

            # Bar chart
            names = [self.guild.get_member(int(uid)).display_name if self.guild.get_member(int(uid)) else f"User {uid}" for uid, _ in results]
            units = [u for _, u in results]
            ax_bar.bar(names, units, color='gold')
            ax_bar.set_title("Units Won")
            ax_bar.set_ylabel("Units")
            plt.xticks(rotation=45, ha='right')

            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)

            channel = self.guild.get_channel(int(channel_id))
            await channel.send(file=discord.File(fp=buf, filename='leaderboard.png'))
            await interaction.response.send_message("Leaderboard sent successfully.", ephemeral=True)
        except Exception as e:
            logging.error("Error generating leaderboard: %s", e)
            await interaction.response.send_message("Failed to generate leaderboard.", ephemeral=True)

async def leaderboard_command_handler(interaction: Interaction):
    view = View(timeout=60)
    view.add_item(ChannelSelectForLeaderboard(interaction.guild))
    await interaction.response.send_message("Select a channel to send the leaderboard:", view=view, ephemeral=True)
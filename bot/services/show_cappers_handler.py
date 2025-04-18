#   bot/services/show_cappers_handler.py

import logging
import discord
from discord import Interaction
from bot.data.db_manager import DatabaseManager

db_manager = DatabaseManager()

async def show_cappers_command_handler(interaction: Interaction):
    try:
        query = "SELECT user_id, display_name FROM cappers"
        cappers = await db_manager.fetch(query)
        if not cappers:
            await interaction.response.send_message("No cappers found.", ephemeral=True)
            return
        embed = discord.Embed(title="📋 List of Cappers", color=discord.Color.purple())
        for user_id, display_name in cappers:
            embed.add_field(name=display_name, value=f"User ID: {user_id}", inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logging.error("Error fetching cappers: %s", e)
        await interaction.response.send_message("Failed to fetch cappers.", ephemeral=True)
#   bot/services/load_url_handler.py

import discord
from discord import Interaction

async def load_url_command_handler(interaction: Interaction, url: str):
    await interaction.response.send_message("This feature is not yet implemented.", ephemeral=True)
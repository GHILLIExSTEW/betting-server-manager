#   bot/commands/load_url.py

import discord
from discord import app_commands, Interaction, Object
from bot.services.load_url_handler import load_url_command_handler  # Import the handler

@app_commands.command(name="load_url", description="Load bet data from a URL (placeholder).")
@app_commands.describe(url="The URL containing bet data")
async def load_url_command(interaction: Interaction, url: str):
    await load_url_command_handler(interaction, url)  # Call the handler

def setup(tree: app_commands.CommandTree, guild: Object):
    tree.add_command(load_url_command, guild=guild)
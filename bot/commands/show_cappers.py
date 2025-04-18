#   bot/commands/show_cappers.py

import discord
from discord import app_commands, Interaction, Object
from bot.services.show_cappers_handler import show_cappers_command_handler  # Import the handler

@app_commands.command(name="show_cappers", description="List all cappers.")
async def show_cappers_command(interaction: Interaction):
    await show_cappers_command_handler(interaction)  # Call the handler

def setup(tree: app_commands.CommandTree, guild: Object):
    tree.add_command(show_cappers_command, guild=guild)
# bot/commands/help.py
# No changes needed for this file.

import discord
from discord import app_commands, Interaction
from bot.services.help_handler import help_command_handler  # Import the handler

@app_commands.command(name="help", description="Show available commands.")
async def help_command(interaction: Interaction):
    await help_command_handler(interaction)  # Call the handler

def setup(tree: app_commands.CommandTree):
    """Adds the help command to the command tree."""
    tree.add_command(help_command)
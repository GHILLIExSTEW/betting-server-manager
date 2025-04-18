#   bot/commands/stats.py

import discord
from discord import app_commands, Interaction, Object
from bot.services.stats_handler import stats_command_handler  # Import the handler
from typing import Optional

@app_commands.command(name="stats", description="Show a capper's betting stats.")
async def stats_command(interaction: Interaction):
    await stats_command_handler(interaction)  # Call the handler

def setup(tree: app_commands.CommandTree, guild: Object):
    tree.add_command(stats_command, guild=guild)
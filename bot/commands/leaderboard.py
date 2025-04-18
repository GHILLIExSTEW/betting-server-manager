#   bot/commands/leaderboard.py

import discord
from discord import app_commands, Interaction, Object
from bot.services.leaderboard_handler import leaderboard_command_handler  # Import the handler

@app_commands.command(name="leaderboard", description="Show top bettors by units won.")
async def leaderboard_command(interaction: Interaction):
    await leaderboard_command_handler(interaction)  # Call the handler

def setup(tree: app_commands.CommandTree, guild: Object):
    tree.add_command(leaderboard_command, guild=guild)
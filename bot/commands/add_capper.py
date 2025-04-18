import discord
from discord import app_commands, Interaction, Object
from bot.services.add_capper_handler import add_capper_command_handler  # Import the handler

@app_commands.command(name="add_capper", description="Add a user as a capper to the cappers table.")
async def add_capper_command(interaction: Interaction):
    await add_capper_command_handler(interaction)  # Call the handler

def setup(tree: app_commands.CommandTree, guild: Object):
    tree.add_command(add_capper_command, guild=guild)
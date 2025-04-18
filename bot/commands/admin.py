# bot/commands/admin.py
# Modified: Removed @app_commands.guild_only() to make it a global command.

import discord
from discord import app_commands, Interaction
# Import the handler function (ensure this matches the actual handler)
from bot.services.admin_handler import admin_settings_command_handler

# Removed @app_commands.guild_only() decorator
@app_commands.command(name="admin", description="Configure bot settings for the server where command is used.")
async def admin_command(interaction: Interaction):
    """
    Handles the /admin command globally.
    The handler will perform guild checks internally.
    """
    # The handler function needs to check interaction.guild internally
    # as the command can now technically be invoked outside a guild (e.g., DMs)
    # although the setup logic only makes sense within a guild.
    if not interaction.guild:
        await interaction.response.send_message("This command must be used inside a server to configure settings.", ephemeral=True)
        return

    # Call the handler function which initiates the interactive view/process
    await admin_settings_command_handler(interaction)

def setup(tree: app_commands.CommandTree):
    """Adds the admin command to the command tree."""
    tree.add_command(admin_command)
    # No need to specify guild here, as it's added globally by core.py
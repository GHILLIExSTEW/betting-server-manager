# bot/commands/profile.py

import discord
from discord import app_commands, Interaction, Object
# Import the handler (ensure path is correct)
from bot.services.profile_handler import profile_command_handler
from typing import Optional

@app_commands.command(name="profile", description="View or manage your profile.")
# Example parameters/choices - actual implementation might differ
@app_commands.describe(action="Choose an action (e.g., view, set_info)")
@app_commands.choices(action=[
    app_commands.Choice(name="View Profile", value="view"),
    # Add other relevant actions as choices
])
async def profile_command(interaction: Interaction, action: str, value: Optional[str] = None):
     # Pass necessary parameters to the handler
    await profile_command_handler(interaction, action, value)

def setup(tree: app_commands.CommandTree, guild: Object):
    """Adds the profile command to the command tree."""
    tree.add_command(profile_command, guild=guild)
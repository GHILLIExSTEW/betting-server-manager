# bot/commands/subscription.py
# No changes needed for this file.

import discord
from discord import app_commands, Interaction
# Import the handler (ensure path is correct)
from bot.services.subscription_handler import subscription_command_handler

@app_commands.command(name="subscription", description="View or manage guild subscription status.")
# Note: Depending on handler logic, describe might be better handled in help or dynamically
@app_commands.describe(status="Optional: Set status (e.g., 'paid', 'free'). Requires specific permissions.")
async def subscription_command(interaction: Interaction, status: str = None): # Made status optional
    # Handler should check permissions if status is provided
    await subscription_command_handler(interaction, status)

def setup(tree: app_commands.CommandTree):
    """Adds the subscription command to the command tree."""
    tree.add_command(subscription_command)
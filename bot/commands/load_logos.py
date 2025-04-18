# Correct content for bot/commands/load_logos.py
# Ensures setup function only accepts the command tree

import discord
from discord import app_commands, Interaction, Attachment
import logging

# Import the handler function (ensure path is correct)
# Adjust if your handler is located elsewhere
try:
    from bot.services.load_logos_handler import load_logos_command_handler
except ImportError:
    # Fallback or log critical error if handler is essential
    logger = logging.getLogger(__name__)
    logger.critical("Failed to import load_logos_command_handler. /load_logos command will not work.")
    # Define a placeholder handler if needed to prevent load failure
    async def load_logos_command_handler(interaction: Interaction, csv_file: Attachment):
        await interaction.response.send_message("Logo loading handler is unavailable.", ephemeral=True)


logger = logging.getLogger(__name__)

# Define the slash command (no changes here)
@app_commands.command(name="load_logos", description="Owner only: Upload a CSV to bulk load/update logos.")
@app_commands.describe(
    csv_file="The CSV file containing logo data (league, ..., logo_url)."
)
async def load_logos(interaction: Interaction, csv_file: Attachment):
    """Slash command entry point for loading logos."""
    # Make sure the imported handler is actually called
    await load_logos_command_handler(interaction, csv_file)

# --- CORRECTED SETUP FUNCTION ---
# Removed the 'guilds' parameter as the command is registered globally
def setup(tree: app_commands.CommandTree):
    """Adds the slash command to the command tree."""
    logger.info("Registering /load_logos command globally.")
    # Register command globally
    tree.add_command(load_logos)
# --- END CORRECTION ---
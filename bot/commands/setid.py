# bot/commands/setid.py
import logging
import discord
from discord import app_commands
from bot.services.setid_handler import handle_setid_command

logger = logging.getLogger(__name__)

def setup(tree: app_commands.CommandTree, guild: discord.Object = None):
    """Register the /setid command for a specific guild."""
    kwargs = {"guild": guild} if guild else {}
    @tree.command(name="setid", description="Set your capper profile", **kwargs)
    @app_commands.describe(
        attachment="Your profile picture (PNG or JPEG, required)"
    )
    async def setid_command(interaction: discord.Interaction, attachment: discord.Attachment):
        """
        Slash command to set a user's capper profile with a required image attachment.
        """
        try:
            logger.info(f"Processing /setid for user {interaction.user.id} in guild {interaction.guild_id}")
            await handle_setid_command(interaction, attachment)
        except Exception as e:
            logger.error(f"Failed to process /setid for user {interaction.user.id}: {e}", exc_info=True)
            await interaction.response.send_message("An error occurred while processing your request.", ephemeral=True)

    scope = f"guild {guild.id}" if guild else "globally"
    logger.info(f"Registered /setid command {scope}.")
# bot/services/subscription_handler.py

import logging
import discord
from discord import Interaction
# Ensure db_manager is correctly imported
from bot.data.db_manager import db_manager
from utils.errors import DatabaseError

logger = logging.getLogger(__name__)

async def check_admin_permissions(interaction: Interaction) -> bool:
    """Checks if the interacting user has administrator permissions."""
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return False
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        return False
    return True

async def subscription_command_handler(interaction: Interaction, status: str):
    """Handles the /subscription command logic by updating the subscribers table."""
    if not await check_admin_permissions(interaction):
        return

    # Normalize status and validate
    status_lower = status.lower()
    # Define valid statuses (adjust if needed, e.g., 'active', 'inactive')
    valid_statuses = ["free", "paid", "active", "inactive", "expired"]
    if status_lower not in valid_statuses:
        await interaction.response.send_message(f"Status must be one of: {', '.join(valid_statuses)}.", ephemeral=True)
        return

    guild_id = interaction.guild_id
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        # Update the subscribers table for this guild
        # Assumes guild_id is the primary key for subscriptions
        # Add other fields like expiry_date if needed
        query = """
            INSERT INTO subscribers (guild_id, subscription_status)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE subscription_status = VALUES(subscription_status)
        """
        # If you need to update expiry date when status changes, add logic here
        # e.g., if status_lower == 'active': expiry = calculate_expiry() else: expiry = None
        # query = """ INSERT INTO subscribers (guild_id, subscription_status, expirations_date) ... """
        # params = (guild_id, status_lower, expiry)

        params = (guild_id, status_lower)
        await db_manager.execute(query, params)

        await interaction.followup.send(f"Subscription status for this server set to '{status_lower}'.", ephemeral=True)
        logger.info(f"Set subscription status='{status_lower}' for guild_id={guild_id} by user {interaction.user.id}")

    except DatabaseError as db_err:
        logger.error(f"Database error setting subscription for guild_id={guild_id}: {db_err}", exc_info=True)
        await interaction.followup.send(f"Failed to set subscription status due to a database error: {db_err.message}", ephemeral=True)
    except Exception as e:
        logger.error(f"Unexpected error setting subscription for guild_id={guild_id}: {e}", exc_info=True)
        await interaction.followup.send("An unexpected error occurred while setting subscription status.", ephemeral=True)
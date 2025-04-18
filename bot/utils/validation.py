# Modified content for bot/utils/validation.py
"""
Validation utility functions for the Discord betting bot.
Ensures user inputs meet expected formats and constraints.
"""
import discord
import logging
import re
from typing import Optional

# --- MOVED IMPORT (See inside is_valid_entity) ---
# from bot.data.league.league_team_handler import validate_entity # Use the new generic function
# ---

# Assuming SUPPORTED_LEAGUES is correctly defined elsewhere (e.g., settings or loaded from league_dict)
# If needed, import it directly: from bot.data.league.league_dictionaries import SUPPORTED_LEAGUES
# Or get it passed into functions that need it. For is_valid_league, let's import standardize_league_code inside.

logger = logging.getLogger(__name__)

async def is_valid_entity(entity_input: str, league: str) -> bool:
    """
    Validate a team or player name for a given league using the league handler.

    Args:
        entity_input (str): The team or player name/alias to validate.
        league (str): The league context (used to load correct dictionaries).

    Returns:
        bool: True if valid (maps to a standard entity), False otherwise.
    """
    # --- MOVED IMPORT INSIDE FUNCTION ---
    try:
        from bot.data.league.league_team_handler import validate_entity
    except ImportError as e:
        logger.critical(f"Failed to import validate_entity inside is_valid_entity: {e}")
        return False # Cannot validate without the function
    # --- END MOVED IMPORT ---

    if not isinstance(entity_input, str) or not entity_input.strip():
        logger.debug(f"Invalid entity input: '{entity_input}' (empty or not a string)")
        return False

    if not league or not isinstance(league, str):
         logger.debug(f"Invalid league provided for entity validation: '{league}'")
         return False
    # We rely on the imported validate_entity to handle league standardization/checking

    is_valid = await validate_entity(entity_input, league)
    logger.debug(f"Entity '{entity_input}' validation for league '{league}': {is_valid}")
    return is_valid

def is_valid_league(league: str) -> bool:
    """
    Validate a league name against supported leagues by attempting standardization.

    Args:
        league (str): The league name to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    # Import standardize_league_code here to avoid top-level dependency issues
    try:
        from bot.data.league.league_team_handler import standardize_league_code
    except ImportError as e:
         logger.critical(f"Failed to import standardize_league_code inside is_valid_league: {e}")
         return False # Cannot validate

    if not isinstance(league, str) or not league.strip():
        logger.debug(f"Invalid league: '{league}' (empty or not a string)")
        return False

    # Use standardize_league_code which checks against the list in league_dictionaries/__init__
    is_valid = standardize_league_code(league) is not None
    logger.debug(f"League '{league}' validation: {is_valid}")
    return is_valid

def is_valid_units(units: int) -> bool:
    """
    Validate the units value for a bet (must be 1, 2, or 3).

    Args:
        units (int): The units value to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    if not isinstance(units, int):
        # Allow float conversion if needed, but prompt specified int
        try:
             units_int = int(units)
        except (ValueError, TypeError):
             logger.debug(f"Invalid units: '{units}' (not convertible to integer)")
             return False
    else:
         units_int = units

    is_valid = units_int in [1, 2, 3]
    logger.debug(f"Units '{units_int}' validation: {is_valid}")
    return is_valid

def is_valid_channel(channel: Optional[discord.abc.GuildChannel], bot: discord.Client) -> bool:
    """
    Validate if a channel is usable by the bot for sending messages and reactions.
    Accepts potential None values for channel.

    Args:
        channel (Optional[discord.abc.GuildChannel]): The channel to validate. Can be None.
        bot (discord.Client): The bot instance to check permissions.

    Returns:
        bool: True if channel is a valid TextChannel with perms, False otherwise.
    """
    # Check if channel is None or not a TextChannel
    if not channel or not isinstance(channel, discord.TextChannel):
        logger.debug(f"Invalid channel: '{channel}' (None or not a TextChannel object)")
        return False

    # Check permissions for the bot in that channel
    if not bot or not bot.user or not channel.guild: # Need guild context for permissions_for
         logger.error("Bot client/user or channel guild context not available for permission check.")
         return False

    # Use guild.me to get the bot's member object in that guild
    permissions = channel.permissions_for(channel.guild.me)
    required_perms = (
        permissions.send_messages and
        permissions.embed_links and
        permissions.add_reactions and
        permissions.read_message_history and
        permissions.manage_webhooks # Added based on bet_service logic
    )
    if not required_perms:
         # Log specific missing permissions
         missing = []
         if not permissions.send_messages: missing.append("Send Messages")
         if not permissions.embed_links: missing.append("Embed Links")
         if not permissions.add_reactions: missing.append("Add Reactions")
         if not permissions.read_message_history: missing.append("Read History")
         if not permissions.manage_webhooks: missing.append("Manage Webhooks")
         logger.warning(f"Bot missing required permissions in channel '{channel.name}' ({channel.id}): {', '.join(missing)}")
         return False

    logger.debug(f"Channel '{channel.name}' ({channel.id}) validation for bot permissions: True")
    return True

def is_valid_bet_serial(bet_serial: Optional[int]) -> bool:
    """
    Validate a bet serial number format (e.g., 15-digit integer). Accepts None.

    Args:
        bet_serial (Optional[int]): The bet serial to validate.

    Returns:
        bool: True if valid format, False otherwise.
    """
    if bet_serial is None:
        logger.debug("Bet serial is None, considered invalid for format check.")
        return False
    if not isinstance(bet_serial, int):
        logger.debug(f"Invalid bet serial: '{bet_serial}' (not an integer)")
        return False

    # Assuming serial is purely numeric and has a fixed length (e.g., 15)
    serial_str = str(bet_serial)
    # Adjust pattern if length or format differs
    # Example: Allowing 10 to 20 digits: r"^\d{10,20}$"
    pattern = r"^\d{15}$" # Matches exactly 15 digits
    is_valid = bool(re.match(pattern, serial_str))

    if not is_valid:
         logger.debug(f"Bet serial '{bet_serial}' format invalid (doesn't match {pattern})")
    else:
         logger.debug(f"Bet serial '{bet_serial}' validation: {is_valid}")
    return is_valid
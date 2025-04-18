"""
Utility functions for generating serial numbers in the Discord betting bot.
"""
import discord
import uuid
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

def generate_bet_serial() -> int:
    """
    Generate a unique bet serial number as an integer in the format YYYYMMDDHHMMXXX.

    Returns:
        int: A 15-digit bet serial (e.g., 202504061234123).
    """
    # Get current UTC timestamp in YYYYMMDDHHMM format
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")  # e.g., "202504061234"
    
    # Generate a 3-digit unique identifier from UUID
    unique_id = uuid.uuid4().int % 1000  # 0-999, padded to 3 digits
    
    # Combine into a 15-digit integer
    serial = int(f"{timestamp}{unique_id:03d}")  # e.g., 202504061234123
    
    logger.debug(f"Generated bet serial: {serial}")
    return serial
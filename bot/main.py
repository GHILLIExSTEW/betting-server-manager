# Modified content for bot/main.py
# Added one log message at start of main()

import asyncio
import logging
import sys
import os
import discord

# Ensure parent directory is added to sys.path
# This needs to be robust regardless of how the script is run
try:
    # Assumes main.py is in /home/container/bot/
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir) # Insert at beginning
    logger_check = logging.getLogger(__name__) # Temp logger for path check
    logger_check.info(f"Parent directory added to sys.path: {parent_dir}")
    logger_check.info(f"Current sys.path: {sys.path}")
except Exception as path_e:
     print(f"Error adding parent dir to sys.path: {path_e}") # Print as logger might not be configured

# Use absolute imports starting from 'bot.'
try:
    from bot.core import BettingBot
    # Assuming settings handles logging setup upon import
    from bot.config.settings import DISCORD_TOKEN
    from bot.data.db_manager import db_manager # Import the instance
    from bot.data.cache_manager import cache_manager # Import the instance
    # Removed logo_sync import as it's likely not needed directly here
    # from bot.utils.image_utils.logo_sync import sync_logos_from_db
except ImportError as imp_err:
     # Log critical import errors if possible
     critical_logger = logging.getLogger(__name__)
     critical_logger.critical(f"Failed to import core modules in main.py: {imp_err}. Check paths and circular dependencies.", exc_info=True)
     sys.exit(f"CRITICAL: Failed to import core modules - {imp_err}") # Exit if core parts fail

# Ensure logger is configured (might happen in settings.py)
# If not, basicConfig here as fallback
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

async def main():
    # --- ADDED LOGGING ---
    logger.info("--- Entered main() ---")
    # ---
    # Connections are handled in setup_hook now, remove from here
    # logger.info("Initializing database connection...")
    # await db_manager.connect()
    # logger.info("Initializing cache connection...")
    # await cache_manager.connect()

    logger.info("Initializing BettingBot class...")
    intents = discord.Intents.default()
    intents.members = True # Enable member intent if needed
    intents.message_content = True # Enable message content intent
    # Add any other required intents

    bot = BettingBot(intents=intents)
    logger.info("BettingBot instance created.")

    try:
        logger.info("Attempting to start bot...")
        if not DISCORD_TOKEN:
            logger.critical("DISCORD_TOKEN not found in settings. Cannot start bot.")
            return # Exit cleanly if token missing
        await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
         logger.critical("Failed to log in: Invalid Discord token provided.")
    except Exception as e:
        logger.critical(f"Bot failed during runtime: {e}", exc_info=True)
    finally:
        logger.info("Initiating bot close sequence...")
        # Ensure bot.close() is called to trigger cleanup
        if not bot.is_closed():
             await bot.close()
        # Connections are now closed within bot.close(), no need to repeat here
        # if hasattr(db_manager, 'close') and asyncio.iscoroutinefunction(db_manager.close): await db_manager.close()
        # if hasattr(cache_manager, 'close') and asyncio.iscoroutinefunction(cache_manager.close): await cache_manager.close()
        logger.info("Bot shutdown process complete.")

if __name__ == "__main__":
    logger.info(f"Starting main execution block (__name__ == '__main__')")
    try:
        # Use asyncio.run() which handles loop creation/closing
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt).")
    except Exception as main_e:
         # Catch unexpected errors during asyncio.run or main() execution
         logger.critical(f"Critical error in main execution: {main_e}", exc_info=True)
    finally:
         logger.info("Exiting main script.")
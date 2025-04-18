# bot/utils/logging.py
import logging
import os
from pathlib import Path
from config.settings import BASE_DIR
# Import datetime
import datetime # <<< ADDED IMPORT

def setup_logging() -> None:
    """
    Configure logging for the bot with file and console output.

    - File handler: Logs DEBUG and above to logs/bot_<timestamp>.log.
    - Console handler: Logs INFO and above to stdout.
    - Format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Ensure no duplicate handlers
    logger.handlers.clear()

    # File handler
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    # Use datetime.now().timestamp() for the log file name
    # log_file = log_dir / f"bot_{os.times().start:.0f}.log" # <<< OLD LINE
    log_file = log_dir / f"bot_{datetime.datetime.now().timestamp():.0f}.log" # <<< NEW LINE
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Adjust third-party loggers
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    logger.info("Logging configured successfully")

# Initialize logging on import (optional, can be called explicitly instead)
# setup_logging() # <<< Consider calling this explicitly in main.py instead of on import
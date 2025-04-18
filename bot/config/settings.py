# bot/config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path("/home/container/.env")
load_dotenv(dotenv_path=env_path)

BASE_DIR = Path(__file__).resolve().parent.parent

# Bot settings
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", "1328126227013439601"))

# Database settings
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "db": os.getenv("DB_NAME"),
}

# Redis settings
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST"),
    "port": int(os.getenv("REDIS_PORT", "14768")),
    "username": os.getenv("REDIS_USERNAME"),
    "password": os.getenv("REDIS_PASSWORD"),
    "db": int(os.getenv("REDIS_DB", "0")),
}

# API settings
API_KEY = os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_HOST")
WEBSOCKET_API_KEY = os.getenv("WEBSOCKET_API_KEY")

# Web settings
FERNET_KEY = os.getenv("FERNET_KEY")
FERNET_KEY_TIMESTAMP = os.getenv("FERNET_KEY_TIMESTAMP")

# Static file settings
STATIC_DIR = BASE_DIR / "static"
LOGO_BASE_URL = os.getenv("LOGO_BASE_URL")
DEFAULT_AVATAR_URL = "https://cdn.discordapp.com/embed/avatars/0.png"

SUPPORTED_LEAGUES = [
    'NFL', 'NBA', 'EPL', 'MLB', 'NHL', 'NCAA', 'UFC', 'La Liga', 'MLS',
    'ATP', 'WTA', 'PGA', 'NASCAR', 'CS:GO', 'LoL', 'LPGA', 'European Tour', 'Kentucky Derby'
]

import aiohttp
import asyncio
import logging
from typing import Optional 
from pathlib import Path
from bot.config.settings import BASE_DIR, LOGO_BASE_URL, DEFAULT_AVATAR_URL

logger = logging.getLogger(__name__)

# Define Paths
STATIC_DIR = BASE_DIR / "static"
LOGO_DIR = STATIC_DIR / "logos"
USER_IMAGES_DIR = STATIC_DIR / "user_images"
USER_CSV_PATH = STATIC_DIR / "user_urls.csv"

# Ensure Directories Exist
STATIC_DIR.mkdir(parents=True, exist_ok=True)
LOGO_DIR.mkdir(parents=True, exist_ok=True)
USER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Async Lock for CSV Writing
csv_lock = asyncio.Lock()

async def fetch_image(url: str) -> Optional[bytes]:
    """Fetches image bytes from a URL."""
    if not url or not url.lower().startswith(('http://', 'https://')):
        logger.warning(f"Invalid or missing URL provided for fetch_image: '{url}'")
        return None
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': 'DiscordBot/1.0 (ImageFetcher)'}
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(url, timeout=timeout, headers=headers) as response:
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '').lower()
                if 'image' in content_type:
                    return await response.read()
                else:
                    logger.error(f"Failed image fetch: URL {url} returned non-image Content-Type: {content_type}")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching image from {url}")
        return None
    except aiohttp.ClientError as e:
        logger.error(f"HTTP Error fetching image from {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching image from {url}: {e}", exc_info=True)
        return None
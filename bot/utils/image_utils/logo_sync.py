# Modified content for bot/utils/image_utils/logo_sync.py
# Fixes circular imports AND LOGO_DIR path calculation.

import logging
import asyncio
import csv
from pathlib import Path

# Assuming settings like DEFAULT_AVATAR_URL are needed and imported correctly
try:
    from bot.config.settings import DEFAULT_AVATAR_URL
except ImportError:
    DEFAULT_AVATAR_URL = None # Provide a fallback if settings might not exist
    logger = logging.getLogger(__name__)
    logger.warning("Could not import DEFAULT_AVATAR_URL from settings.")


logger = logging.getLogger(__name__)

# --- CORRECTED PATH CALCULATION ---
try:
    _current_file_path = Path(__file__).resolve()
    # Go up 3 levels from bot/utils/image_utils/ to get bot/ directory
    _bot_dir = _current_file_path.parent.parent.parent
    # Construct path as bot/static/logos
    LOGO_DIR = _bot_dir / "static" / "logos"
    # Also define USER_IMAGES_DIR if needed within this file, based on bot_dir
    USER_IMAGES_DIR = _bot_dir / "static" / "user_images"

    # Check if the calculated directories exist
    if not LOGO_DIR.is_dir():
        logger.warning(f"Calculated LOGO_DIR does not exist or is not a directory: {LOGO_DIR}")
        # Optionally try to create it: LOGO_DIR.mkdir(parents=True, exist_ok=True)
    else:
        logger.info(f"logo_sync.py: LOGO_DIR successfully set to: {LOGO_DIR}")

    if not USER_IMAGES_DIR.is_dir():
         logger.warning(f"Calculated USER_IMAGES_DIR does not exist or is not a directory: {USER_IMAGES_DIR}")
         # Optionally try to create it: USER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    else:
        logger.info(f"logo_sync.py: USER_IMAGES_DIR successfully set to: {USER_IMAGES_DIR}")

except Exception as e:
    logger.error(f"Error determining static directories in logo_sync.py: {e}", exc_info=True)
    LOGO_DIR = None
    USER_IMAGES_DIR = None
# --- END CORRECTED PATH CALCULATION ---


async def sync_logos_from_db():
    """
    Reads logo data from the database (assuming a table like 'league_teams_logos')
    and generates/updates the league-specific logo CSV files used by team_logos.py.
    Also primes the Redis cache for logo URLs.
    """
    # Imports moved inside function to break circular dependencies
    try:
         from bot.data.league.league_team_handler import standardize_league_code
         from bot.data.db_manager import db_manager
         from bot.data.cache_manager import cache_manager
         from bot.utils.errors import DatabaseError
    except ImportError as e:
         logger.critical(f"Failed to import dependencies inside sync_logos_from_db: {e}. Cannot proceed.")
         return

    logger.info("Starting logo sync: DB -> CSVs & Cache")

    # Check LOGO_DIR again inside the function in case initialization failed
    if not LOGO_DIR or not LOGO_DIR.is_dir():
        logger.error("Cannot sync logos: LOGO_DIR is not configured or invalid.")
        return

    # Ensure LOGO_DIR exists before writing
    try:
        LOGO_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create LOGO_DIR '{LOGO_DIR}' before writing CSVs: {e}")
        return

    league_data = {}
    processed_leagues = set()
    processed_count = 0
    cache_updates = {}
    CACHE_FOUND_NONE = "||NONE||"
    CACHE_FOUND_EMPTY = "||EMPTY||"

    try:
        # Assuming `logo_url` column exists and is populated.
        query = """
            SELECT league, team, first_name, last_name, logo_url
            FROM league_teams_logos
            WHERE logo_url IS NOT NULL AND logo_url != '' AND league IS NOT NULL
        """
        all_logos = await db_manager.fetch(query)
        logger.info(f"Fetched {len(all_logos)} logo entries from database.")

        for row in all_logos:
            raw_league = row.get('league')
            team_name = row.get('team')
            first_name = row.get('first_name')
            last_name = row.get('last_name')
            logo_url = row.get('logo_url')

            if not raw_league or not logo_url: continue

            standard_league = standardize_league_code(raw_league)
            if not standard_league: logger.warning(f"Could not standardize league '{raw_league}'. Skipping."); continue

            processed_leagues.add(standard_league)
            entity_key = None
            if team_name: entity_key = team_name.lower().strip()
            elif first_name and last_name: entity_key = f"{first_name} {last_name}".lower().strip()
            elif not team_name and not first_name and not last_name: entity_key = standard_league

            if entity_key:
                if standard_league not in league_data: league_data[standard_league] = {}
                if entity_key not in league_data[standard_league]:
                     league_data[standard_league][entity_key] = logo_url
                     processed_count += 1
                     cache_key = f"team_logo_url_v3:{standard_league}:{entity_key}"
                     cache_val = CACHE_FOUND_NONE
                     if isinstance(logo_url, str):
                          if logo_url.strip() == "": cache_val = CACHE_FOUND_EMPTY
                          elif logo_url.lower().startswith(('http://', 'https://')): cache_val = logo_url
                          else: logger.warning(f"Invalid format for logo_url '{logo_url}'. Caching as NONE.")
                     elif logo_url is None: cache_val = CACHE_FOUND_NONE
                     else: logger.warning(f"Unexpected type for logo_url '{logo_url}'. Caching as NONE."); cache_val = CACHE_FOUND_NONE
                     cache_updates[cache_key] = cache_val

        logger.info(f"Processed {processed_count} unique logo entries across {len(processed_leagues)} leagues.")
        for league_code, data in league_data.items():
            csv_path = LOGO_DIR / f"{league_code}_logos.csv"
            try:
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['team_key', 'logo_url']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for team_key, url in data.items():
                        if isinstance(url, str) and url.lower().startswith(('http://', 'https://')):
                             writer.writerow({'team_key': team_key, 'logo_url': url})
                        # else: logger.debug(f"Skipping write to CSV for key '{team_key}' due to invalid URL: '{url}'")
                logger.info(f"Successfully wrote/updated logo CSV: {csv_path}")
            except Exception as e: logger.error(f"Failed to write logo CSV for {league_code}: {e}", exc_info=True)

        cache_ttl = 86400; fail_cache_ttl = 3600
        logger.info(f"Updating Redis cache for {len(cache_updates)} logo entries...")
        cache_success = 0; cache_fail = 0
        for key, value in cache_updates.items():
            try:
                current_ttl = cache_ttl if value not in [CACHE_FOUND_EMPTY, CACHE_FOUND_NONE] else fail_cache_ttl
                await cache_manager.set(key, value, ttl=current_ttl)
                cache_success += 1
            except Exception as cache_err: logger.error(f"Failed to cache key '{key}': {cache_err}"); cache_fail += 1
        logger.info(f"Cache update complete. Success: {cache_success}, Failed: {cache_fail}")

    except DatabaseError as e: logger.error(f"Database error during logo sync: {e}", exc_info=True)
    except Exception as e: logger.error(f"Unexpected error during logo sync: {e}", exc_info=True)

    logger.info("Logo sync finished.")
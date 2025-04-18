# Modified content for bot/utils/image_utils/team_logos.py
# Fixes circular imports AND LOGO_DIR path calculation.

import csv
import logging
from typing import Optional, Tuple
from pathlib import Path
import asyncio

# --- MOVED cache_manager IMPORT (See inside function) ---
# from bot.data.cache_manager import cache_manager
# ---

# --- MOVED league_team_handler IMPORTS (See inside function) ---
# from bot.data.league.league_team_handler import standardize_league_code, get_standard_entity_name
# ---

# Assuming settings like DEFAULT_AVATAR_URL are needed and imported correctly
try:
    from bot.config.settings import DEFAULT_AVATAR_URL
except ImportError:
    DEFAULT_AVATAR_URL = None # Provide a fallback if settings might not exist
    logger = logging.getLogger(__name__)
    logger.warning("Could not import DEFAULT_AVATAR_URL from settings.")


logger = logging.getLogger(__name__)

# Log message updated slightly for clarity
logger.info("Running team_logos.py (modified for circular imports & path fix)")

# --- CORRECTED PATH CALCULATION ---
try:
    _current_file_path = Path(__file__).resolve()
    # Go up 3 levels from bot/utils/image_utils/ to get bot/ directory
    _bot_dir = _current_file_path.parent.parent.parent
    # Construct path as bot/static/logos
    LOGO_DIR = _bot_dir / "static" / "logos"

    # Check if the calculated directory exists
    if not LOGO_DIR.is_dir():
        logger.warning(f"Calculated LOGO_DIR does not exist or is not a directory: {LOGO_DIR}")
        # Optionally try to create it:
        # try:
        #     LOGO_DIR.mkdir(parents=True, exist_ok=True)
        #     logger.info(f"Created missing LOGO_DIR: {LOGO_DIR}")
        # except Exception as mkdir_err:
        #      logger.error(f"Failed to create LOGO_DIR {LOGO_DIR}: {mkdir_err}")
        #      LOGO_DIR = None # Set to None if creation fails
    else:
        logger.info(f"team_logos.py: LOGO_DIR successfully set to: {LOGO_DIR}")

except Exception as e:
    logger.error(f"Error determining LOGO_DIR in team_logos.py: {e}", exc_info=True)
    LOGO_DIR = None
# --- END CORRECTED PATH CALCULATION ---

async def get_team_logo_url_from_csv(league: Optional[str], team_name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetches team and league logo URLs from CSV: {league}_logos.csv.
    Checks cache first. Returns (team_url, league_url).
    Uses DEFAULT_AVATAR_URL as fallback if specific URLs aren't found/valid.
    """
    # Imports moved inside function to break circular dependencies
    try:
        from bot.data.cache_manager import cache_manager
        from bot.data.league.league_team_handler import standardize_league_code, get_standard_entity_name
    except ImportError as e:
         logger.critical(f"Failed to import dependencies inside get_team_logo_url_from_csv: {e}")
         # Return defaults if critical imports fail
         return DEFAULT_AVATAR_URL or None, DEFAULT_AVATAR_URL or None

    logger.debug(f"get_team_logo_url_from_csv called: league='{league}', team_name='{team_name}'")

    # Use default URL if defined, otherwise None
    default_url = DEFAULT_AVATAR_URL or None

    if not league:
        logger.warning("get_team_logo_url_from_csv: Missing league argument.")
        return default_url, default_url

    # Check if LOGO_DIR was successfully determined and exists
    if not LOGO_DIR or not LOGO_DIR.is_dir():
        logger.error(f"get_team_logo_url_from_csv: LOGO_DIR '{LOGO_DIR}' is invalid or inaccessible.")
        # Cannot read CSVs, rely on cache or return defaults
        # We'll still proceed to check cache below, but CSV reading will be skipped.
        pass # Continue to cache check

    # Standardize league code
    standard_league_code = standardize_league_code(league)
    if not standard_league_code:
        logger.warning(f"Cannot map input league '{league}' to standard code.")
        return default_url, default_url

    logger.debug(f"Standard league code for logo lookup: '{standard_league_code}'")

    # Normalize team name (handling potential awaitable)
    standard_team_name: Optional[str] = None
    if team_name:
        try:
            standard_team_name_result = await get_standard_entity_name(team_name, standard_league_code)
            standard_team_name = standard_team_name_result
            if standard_team_name: logger.debug(f"Normalized '{team_name}' to '{standard_team_name}'.")
            else: logger.debug(f"Could not normalize '{team_name}' for '{standard_league_code}'.")
        except Exception as norm_err: logger.error(f"Normalization error: {norm_err}", exc_info=True); standard_team_name = None
    else: logger.debug("No team_name provided.")

    # Define keys for lookup
    canonical_team_key_lower = standard_team_name.lower().strip() if standard_team_name else None
    canonical_league_key_lower = standard_league_code.lower().strip()

    # Define cache keys
    team_cache_key = f"team_logo_url_v3:{standard_league_code}:{canonical_team_key_lower}" if canonical_team_key_lower else None
    league_cache_key = f"team_logo_url_v3:{standard_league_code}:{canonical_league_key_lower}"

    team_logo_url: Optional[str] = None
    league_logo_url: Optional[str] = None
    needs_team_check = bool(canonical_team_key_lower)
    needs_league_check = True

    CACHE_FOUND_NONE = "||NONE||"
    CACHE_FOUND_EMPTY = "||EMPTY||"

    # --- Cache Check ---
    try:
        if team_cache_key and needs_team_check:
            cached_bytes = await cache_manager.get(team_cache_key)
            if cached_bytes is not None:
                cached_val = cached_bytes.decode('utf-8'); needs_team_check = False
                if cached_val == CACHE_FOUND_NONE: team_logo_url = None; logger.debug(f"Cache Hit (Team NONE): {team_cache_key}")
                elif cached_val == CACHE_FOUND_EMPTY: team_logo_url = ""; logger.debug(f"Cache Hit (Team EMPTY): {team_cache_key}")
                else: team_logo_url = cached_val; logger.debug(f"Cache Hit (Team URL): {team_cache_key}")
            else: logger.debug(f"Cache Miss (Team): {team_cache_key}")

        # Check league cache regardless of team check result initially
        cached_bytes_league = await cache_manager.get(league_cache_key)
        if cached_bytes_league is not None:
            cached_val_league = cached_bytes_league.decode('utf-8'); needs_league_check = False
            if cached_val_league == CACHE_FOUND_NONE: league_logo_url = None; logger.debug(f"Cache Hit (League NONE): {league_cache_key}")
            elif cached_val_league == CACHE_FOUND_EMPTY: league_logo_url = ""; logger.debug(f"Cache Hit (League EMPTY): {league_cache_key}")
            else: league_logo_url = cached_val_league; logger.debug(f"Cache Hit (League URL): {league_cache_key}")
        else: logger.debug(f"Cache Miss (League): {league_cache_key}")
    except Exception as cache_err:
        logger.error(f"Redis GET error during logo lookup: {cache_err}")
        # Assume cache miss if error occurs, proceed to CSV check if needed
        if team_logo_url is None: needs_team_check = bool(canonical_team_key_lower)
        if league_logo_url is None: needs_league_check = True
    # --- End Cache Check ---

    # --- CSV Check ---
    if (needs_team_check or needs_league_check) and LOGO_DIR and LOGO_DIR.is_dir(): # Only proceed if dir is valid
        logo_csv_path = LOGO_DIR / f"{standard_league_code}_logos.csv"
        logger.info(f"Checking CSV: '{logo_csv_path}' (Need Team: {needs_team_check}, Need League: {needs_league_check})")

        csv_team_url_found: Optional[str] = None
        csv_league_url_found: Optional[str] = None
        found_team_key_in_csv = False
        found_league_key_in_csv = False

        if not logo_csv_path.is_file():
            logger.warning(f"Logo CSV not found: '{logo_csv_path}'.")
            # Cache miss results if file not found and cache was also a miss
            fail_cache_ttl = 3600
            if needs_team_check and team_cache_key: await cache_manager.set(team_cache_key, CACHE_FOUND_NONE, ttl=fail_cache_ttl)
            if needs_league_check: await cache_manager.set(league_cache_key, CACHE_FOUND_NONE, ttl=fail_cache_ttl)
        else:
            try:
                with open(logo_csv_path, "r", newline="", encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    if not reader.fieldnames or 'team_key' not in reader.fieldnames or 'logo_url' not in reader.fieldnames:
                        logger.error(f"Invalid headers in {logo_csv_path}. Need 'team_key', 'logo_url'. Found: {reader.fieldnames}")
                        fail_cache_ttl = 3600 # Cache miss results if headers invalid
                        if needs_team_check and team_cache_key: await cache_manager.set(team_cache_key, CACHE_FOUND_NONE, ttl=fail_cache_ttl)
                        if needs_league_check: await cache_manager.set(league_cache_key, CACHE_FOUND_NONE, ttl=fail_cache_ttl)
                    else:
                        for row in reader:
                            try:
                                csv_key = row.get('team_key', '').strip().lower()
                                csv_url = row.get('logo_url', '').strip()
                                is_valid_url = bool(csv_url and csv_url.lower().startswith(('http://', 'https://')))

                                if needs_team_check and not found_team_key_in_csv and canonical_team_key_lower and csv_key == canonical_team_key_lower:
                                    found_team_key_in_csv = True
                                    csv_team_url_found = csv_url if is_valid_url else None
                                    logger.info(f"CSV Match (Team): Key '{csv_key}' -> URL '{csv_team_url_found}'")

                                if needs_league_check and not found_league_key_in_csv and csv_key == canonical_league_key_lower:
                                     found_league_key_in_csv = True
                                     csv_league_url_found = csv_url if is_valid_url else None
                                     logger.info(f"CSV Match (League): Key '{csv_key}' -> URL '{csv_league_url_found}'")

                                if (not needs_team_check or found_team_key_in_csv) and (not needs_league_check or found_league_key_in_csv):
                                     break # Found all needed from CSV
                            except Exception as row_err: logger.error(f"Error processing row in {logo_csv_path}: {row_err}", exc_info=True)

                # Update main variables and cache results based on CSV findings
                cache_ttl = 86400; fail_cache_ttl = 3600
                if needs_team_check:
                    team_logo_url = csv_team_url_found # Use the value found in CSV (could be None)
                    cache_val = team_logo_url if isinstance(team_logo_url, str) else (CACHE_FOUND_EMPTY if team_logo_url == "" else CACHE_FOUND_NONE)
                    ttl = cache_ttl if cache_val not in [CACHE_FOUND_EMPTY, CACHE_FOUND_NONE] else fail_cache_ttl
                    if team_cache_key: await cache_manager.set(team_cache_key, cache_val, ttl=ttl)
                    logger.debug(f"CSV Result (Team): '{team_logo_url}'. Caching '{cache_val}' for '{team_cache_key}' (TTL: {ttl})")

                if needs_league_check:
                    league_logo_url = csv_league_url_found
                    cache_val = league_logo_url if isinstance(league_logo_url, str) else (CACHE_FOUND_EMPTY if league_logo_url == "" else CACHE_FOUND_NONE)
                    ttl = cache_ttl if cache_val not in [CACHE_FOUND_EMPTY, CACHE_FOUND_NONE] else fail_cache_ttl
                    await cache_manager.set(league_cache_key, cache_val, ttl=ttl)
                    logger.debug(f"CSV Result (League): '{league_logo_url}'. Caching '{cache_val}' for '{league_cache_key}' (TTL: {ttl})")

            except Exception as e:
                logger.error(f"Error reading/processing CSV {logo_csv_path}: {e}", exc_info=True)
                fail_cache_ttl = 600
                if needs_team_check and team_cache_key: await cache_manager.set(team_cache_key, CACHE_FOUND_NONE, ttl=fail_cache_ttl)
                if needs_league_check: await cache_manager.set(league_cache_key, CACHE_FOUND_NONE, ttl=fail_cache_ttl)
    # --- End CSV Check ---

    # --- Final Return Logic ---
    # Return the URL found (from cache or CSV), or the default if still None
    final_team_url = team_logo_url if team_logo_url is not None else default_url
    final_league_url = league_logo_url if league_logo_url is not None else default_url

    # Handle case where cache/CSV explicitly stored "" (empty string)
    if team_logo_url == "": final_team_url = ""
    if league_logo_url == "": final_league_url = ""


    logger.info(f"get_team_logo_url_from_csv RETURN: Team URL='{final_team_url}', League URL='{final_league_url}'")
    return final_team_url, final_league_url
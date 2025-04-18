import logging
from typing import Optional
import importlib

from bot.data.cache_manager import cache_manager
from bot.data.league.league_dictionaries import get_league_data, SUPPORTED_LEAGUES as LEAGUE_LIST

logger = logging.getLogger(__name__)

# Attempt to import NCAAF dictionaries
try:
    from bot.data.league.league_dictionaries.ncaaf import NCAAF_ABBREVIATIONS, TEAM_FULL_NAMES
except ImportError as e:
    logger.error(f"Failed to import NCAAF_ABBREVIATIONS or TEAM_FULL_NAMES: {e}")
    NCAAF_ABBREVIATIONS = {}
    TEAM_FULL_NAMES = {}
except Exception as e:
    logger.error(f"Unexpected error importing NCAAF dictionaries: {e}")
    NCAAF_ABBREVIATIONS = {}
    TEAM_FULL_NAMES = {}

# Log dictionary contents at startup
logger.info(f"Initial TEAM_FULL_NAMES keys: {list(TEAM_FULL_NAMES.keys())}")
logger.info(f"Initial NCAAF_ABBREVIATIONS keys: {list(NCAAF_ABBREVIATIONS.keys())}")

# Reload ncaaf.py if dictionaries are empty
if not TEAM_FULL_NAMES:
    logger.warning("TEAM_FULL_NAMES is empty, attempting to reload ncaaf.py")
    try:
        ncaaf_module = importlib.import_module("bot.data.league.league_dictionaries.ncaaf")
        TEAM_FULL_NAMES = getattr(ncaaf_module, "TEAM_FULL_NAMES", {})
        NCAAF_ABBREVIATIONS = getattr(ncaaf_module, "NCAAF_ABBREVIATIONS", {})
        logger.info(f"Reloaded TEAM_FULL_NAMES keys: {list(TEAM_FULL_NAMES.keys())}")
        logger.info(f"Reloaded NCAAF_ABBREVIATIONS keys: {list(NCAAF_ABBREVIATIONS.keys())}")
    except Exception as e:
        logger.error(f"Failed to reload ncaaf.py: {e}")
        TEAM_FULL_NAMES = {}
        NCAAF_ABBREVIATIONS = {}

LEAGUE_NAME_MAP = {
    "la liga": "laliga",
    "ligue 1": "ligue1",
    "serie a": "seriea",
    "ncaa bb": "ncaam",
    "ncaa fb": "ncaaf",
    "ncaa": "ncaam",
    "tennis": "tennis",
}

def standardize_league_code(league_input: Optional[str]) -> Optional[str]:
    """Converts input league name/code to the standard internal code."""
    if not league_input:
        return None
    input_lower = league_input.lower()
    standard_code = LEAGUE_NAME_MAP.get(input_lower, input_lower)
    if standard_code in LEAGUE_LIST:
        return standard_code
    logger.warning(f"League input '{league_input}' ('{input_lower}') does not map to a supported standard code.")
    return None

async def normalize_entity_name(entity_name: str) -> str:
    """Normalizes a team or player name for comparison."""
    if not entity_name:
        return ""
    return entity_name.lower().strip()

async def get_standard_entity_name(entity_input: str, league: str) -> Optional[str]:
    """
    Find the standardized full name for a given team/player input alias using league data.
    Prioritizes TEAM_FULL_NAMES for NCAAF, falls back to league data for others.
    """
    if not entity_input:
        logger.debug("Empty entity_input provided.")
        return None

    standard_league_code = standardize_league_code(league)
    if not standard_league_code:
        logger.warning(f"Unsupported league for entity standardization: {league}")
        return None

    normalized_input = await normalize_entity_name(entity_input)
    if not normalized_input:
        logger.debug("Normalized input is empty.")
        return None

    cache_key = f"entity_std:{standard_league_code}:{normalized_input}"
    standard_name: Optional[str] = None

    # Check cache
    try:
        cached_value = await cache_manager.get(cache_key)
        if cached_value is not None:
            standard_name = cached_value.decode('utf-8') if isinstance(cached_value, bytes) else str(cached_value)
            if standard_name == "":
                logger.debug(f"Cache hit (no match stored) for entity std name: {entity_input} ({league})")
                return None
            logger.debug(f"Cache hit for entity std name: {entity_input} ({league}) -> {standard_name}")
            return standard_name
    except Exception as cache_err:
        logger.error(f"Redis GET error checking entity cache ({cache_key}): {cache_err}")

    # NCAAF handling
    if standard_league_code == "ncaaf":
        logger.debug(f"Checking NCAAF input '{normalized_input}' against TEAM_FULL_NAMES")
        # Log dictionary state
        logger.debug(f"Current TEAM_FULL_NAMES keys: {list(TEAM_FULL_NAMES.keys())}")
        for alias, team_key in TEAM_FULL_NAMES.items():
            normalized_alias = alias.lower().strip()
            if normalized_input == normalized_alias:
                standard_name = team_key.lower().strip()
                logger.debug(f"NCAAF alias match: '{alias}' -> '{standard_name}'")
                break
        if not standard_name:
            logger.debug(f"Current NCAAF_ABBREVIATIONS keys: {list(NCAAF_ABBREVIATIONS.keys())}")
            for abbr, team_key in NCAAF_ABBREVIATIONS.items():
                normalized_abbr = abbr.lower().strip()
                if normalized_input == normalized_abbr:
                    standard_name = team_key.lower().strip()
                    logger.debug(f"NCAAF abbreviation match: '{abbr}' -> '{standard_name}'")
                    break
        if not standard_name:
            logger.warning(f"No match for '{normalized_input}' in NCAAF TEAM_FULL_NAMES or NCAAF_ABBREVIATIONS")

    # Other leagues
    if not standard_name:
        try:
            league_data = get_league_data(standard_league_code)
            full_names_dict = league_data.get("full_names", {})
            logger.debug(f"Full names keys for {standard_league_code}: {list(full_names_dict.keys())}")
            for alias, mapped_full_name in full_names_dict.items():
                normalized_alias = await normalize_entity_name(alias)
                if normalized_alias == normalized_input:
                    standard_name = mapped_full_name
                    logger.debug(f"Matched alias '{alias}' to '{mapped_full_name}' for input '{entity_input}'")
                    break
        except ValueError as e:
            logger.warning(f"Failed to load league data for {standard_league_code}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during entity standardization for '{entity_input}' ({standard_league_code}): {e}", exc_info=True)

    # Cache result
    value_to_cache = standard_name if standard_name else ""
    try:
        await cache_manager.set(cache_key, value_to_cache, ttl=86400)
        logger.debug(f"Cached entity lookup for '{entity_input}' ({standard_league_code}): '{value_to_cache}'")
    except Exception as cache_set_err:
        logger.error(f"Redis SET error caching entity ({cache_key}): {cache_set_err}")

    if standard_name:
        logger.info(f"Normalized '{entity_input}' to '{standard_name}' for league '{standard_league_code}'")
    else:
        logger.warning(f"Could not normalize '{entity_input}' for '{standard_league_code}'")
    return standard_name

async def abbreviate_entity(entity_input: str, league: str) -> Optional[str]:
    """Abbreviate a team or player name based on league data."""
    standard_name = await get_standard_entity_name(entity_input, league)
    if not standard_name:
        logger.warning(f"Cannot abbreviate '{entity_input}': Standard name not found in league '{league}'.")
        return None

    standard_league_code = standardize_league_code(league)
    if not standard_league_code:
        return None

    normalized_standard_name = await normalize_entity_name(standard_name)
    abbr_cache_key = f"entity_abbr:{standard_league_code}:{normalized_standard_name}"
    final_abbr: Optional[str] = None

    try:
        cached_abbr = await cache_manager.get(abbr_cache_key)
        if cached_abbr is not None:
            final_abbr = cached_abbr.decode('utf-8') if isinstance(cached_abbr, bytes) else str(cached_abbr)
            if final_abbr == "":
                logger.debug(f"Cache hit (no abbr stored) for entity abbr: {standard_name} ({league})")
                return None
            else:
                logger.debug(f"Cache hit for entity abbr: {standard_name} ({league}) -> {final_abbr}")
                return final_abbr
    except Exception as cache_err:
        logger.error(f"Redis GET error checking entity abbr cache ({abbr_cache_key}): {cache_err}")

    try:
        league_data = get_league_data(standard_league_code)
        abbr_dict = league_data.get("abbreviations", {})
        for abbr_key, mapped_name in abbr_dict.items():
            normalized_mapped = await normalize_entity_name(mapped_name)
            if normalized_mapped == normalized_standard_name:
                final_abbr = abbr_key
                break

        # Fallback for NCAAF abbreviations
        if not final_abbr and standard_league_code == "ncaaf":
            for abbr_key, mapped_name in NCAAF_ABBREVIATIONS.items():
                normalized_mapped = await normalize_entity_name(mapped_name)
                if normalized_mapped == normalized_standard_name:
                    final_abbr = abbr_key
                    logger.debug(f"NCAAF abbreviation fallback: '{abbr_key}' for '{standard_name}'")
                    break

        if not final_abbr and standard_league_code in ["tennis", "pga", "masters", "esports_players"]:
            for abbr_key, mapped_name in abbr_dict.items():
                normalized_mapped = await normalize_entity_name(mapped_name)
                if normalized_mapped == normalized_standard_name:
                    final_abbr = abbr_key
                    break

        value_to_cache = final_abbr if final_abbr else ""
        try:
            await cache_manager.set(abbr_cache_key, value_to_cache, ttl=86400)
        except Exception as cache_set_err:
            logger.error(f"Redis SET error caching entity abbr ({abbr_cache_key}): {cache_set_err}")

    except ValueError as e:
        logger.warning(f"Failed to load league data for {standard_league_code}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during abbreviation for {standard_name} ({standard_league_code}): {e}", exc_info=True)

    if final_abbr:
        logger.debug(f"Abbreviated '{entity_input}' (Standard: '{standard_name}') to '{final_abbr}' for league {standard_league_code}")
    else:
        logger.warning(f"No abbreviation found for entity '{entity_input}' (Standard: '{standard_name}') in league {standard_league_code}")
    return final_abbr

async def validate_entity(entity_input: str, league: str) -> bool:
    """Validate if a team/player input maps to a known standard entity."""
    standard_name = await get_standard_entity_name(entity_input, league)
    is_valid = standard_name is not None
    logger.debug(f"Entity '{entity_input}' validation in league '{league}': {is_valid} (Standard Name: {standard_name})")
    return is_valid
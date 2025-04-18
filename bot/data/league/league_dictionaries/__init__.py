# Modified content for League Data/data/league/league_dictionaries/__init__.py
# Incorporates generic parent leagues and specific sub-leagues

from importlib import import_module
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# --- MODIFIED SUPPORTED_LEAGUES LIST ---
# Added generic parents (golf, tennis, esports, horseracing)
# Ensured specific sub-leagues are present
SUPPORTED_LEAGUES = [
    # Team Sports
    "nba", "nfl", "mlb", "nhl",
    "epl", "laliga", "seriea", "bundesliga", "ligue1",
    "mls", "wnba", "cfl",

    # NASCAR
    "nascar",

    # NCAA (Parent + Subs)
    "ncaa", # Generic parent for initial selection
    "ncaam", "ncaaw", "ncaaf", "ncaawvb",

    # Golf (Parent + Subs)
    "golf", # Generic parent
    "pga", "lpga", "europeantour", "masters",

    # Tennis (Parent + Subs)
    "tennis", # Generic parent
    "atp", "wta",

    # Esports (Parent + Subs)
    "esports", # Generic parent
    "csgo", "lol", "valorant",
    "esports_players", # Keep if used for a specific generic player handler

    # Horse Racing (Parent + Subs) - Define codes as needed
    "horseracing", # Generic parent
    "kentucky_derby",
    # Add other races like "preakness_stakes", "belmont_stakes" if needed

    # Combat Sports
    "ufc",
]
# --- END MODIFICATION ---


# Map standard API/internal sport keys to their display names or common variations
# This map seems more focused on mapping API IDs, keep it as is unless API IDs change
SPORT_MAP = {
    "BUNDESLIGA": "soccer_germany_bundesliga",
    "CFL": "football_cfl",
    "EPL": "soccer_england_premier_league",
    "LALIGA": "soccer_spain_la_liga",
    "LIGUE1": "soccer_france_ligue_one",
    "MLB": "baseball_mlb",
    "MLS": "soccer_usa_mls",
    "NBA": "basketball_nba",
    "NCAAF": "football_ncaaf",
    "NCAAM": "basketball_ncaam",
    "NCAAW": "basketball_ncaaw",
    "NCAAWVB": "volleyball_ncaawvb",
    "NFL": "football_nfl",
    "NHL": "icehockey_nhl",
    "SERIEA": "soccer_italy_serie_a",
    "WNBA": "basketball_wnba",
    "PGA": "golf_pga_tour",
    "LPGA": "golf_lpga_tour",           # Added
    "EUROPEANTOUR": "golf_european_tour", # Added (adjust key if needed)
    "MASTERS": "golf_masters",
    "ESPORTS_PLAYERS": "esports_multi", # Or map specific games if API supports it
    "CSGO": "esports_csgo",           # Added (if API has specific IDs)
    "LOL": "esports_lol",             # Added (if API has specific IDs)
    "VALORANT": "esports_valorant",     # Added (if API has specific IDs)
    "NASCAR": "motorsport_nascar",
    "TENNIS": "tennis_atp_wta",       # Keep generic? Or map ATP/WTA separately?
    "ATP": "tennis_atp",              # Added (if API has specific IDs)
    "WTA": "tennis_wta",              # Added (if API has specific IDs)
    "UFC": "fighting_ufc",            # Added
    "HORSERACING": "racing_horse",    # Added (adjust key based on API)
    "KENTUCKY_DERBY": "racing_horse_kentucky_derby" # Added (adjust key based on API)
}

def get_league_data(league: str) -> Dict[str, Any]:
    """
    Dynamically load league data from its respective module.
    Handles cases where a specific sub-league module might not exist
    but a generic parent module does (e.g., 'csgo' might load data from 'esports').
    """
    league_lower = league.lower().strip()

    # --- MODIFIED LOGIC TO HANDLE GENERIC FALLBACKS ---
    # Determine the module name to attempt loading.
    # If a specific sub-league is requested (e.g., 'csgo'), try loading it first.
    # If that fails, potentially fall back to a generic parent module (e.g., 'esports').
    # This requires a mapping or convention.
    module_load_attempts = [league_lower]
    if league_lower in ["csgo", "lol", "valorant"] and "esports" in SUPPORTED_LEAGUES:
        module_load_attempts.append("esports") # Fallback for specific esports games
    elif league_lower in ["atp", "wta"] and "tennis" in SUPPORTED_LEAGUES:
        module_load_attempts.append("tennis") # Fallback for specific tennis tours
    elif league_lower in ["pga", "lpga", "europeantour", "masters"] and "golf" in SUPPORTED_LEAGUES:
        module_load_attempts.append("golf") # Fallback for specific golf tours (if golf.py exists)
        if league_lower != "pga": module_load_attempts.append("pga") # Fallback to PGA data if needed
    elif league_lower in ["kentucky_derby"] and "horseracing" in SUPPORTED_LEAGUES:
         module_load_attempts.append("horseracing") # Fallback for specific races (if horseracing.py exists)
    # Add other fallback logic as needed

    # Also ensure the requested league is actually in the SUPPORTED_LEAGUES list *somewhere*
    if league_lower not in SUPPORTED_LEAGUES:
        logger.error(f"Unsupported league requested (not in SUPPORTED_LEAGUES): {league} (normalized: {league_lower})")
        raise ValueError(f"Unsupported league requested: {league_lower}")
    # --- END MODIFICATION ---

    module_found = None
    loaded_module_name = None
    for module_name_to_try in module_load_attempts:
        try:
            # Ensure the module we try to load is actually intended to be a module (exists in SUPPORTED_LEAGUES)
            # This prevents trying to load, e.g., 'golf' if only specific tours are in SUPPORTED_LEAGUES
            # However, the check above already ensures league_lower is in SUPPORTED_LEAGUES.
            # We need to be careful if the fallback itself isn't meant to be directly loaded.
            # Let's assume for now that fallbacks like 'esports', 'tennis', 'golf' might have modules.
            module = import_module(f".{module_name_to_try}", package="bot.data.league.league_dictionaries")
            module_found = module
            loaded_module_name = module_name_to_try
            logger.debug(f"Successfully loaded module '{loaded_module_name}' for requested league '{league_lower}'")
            break # Stop searching on success
        except ImportError:
            logger.debug(f"No data module found for '{module_name_to_try}' while looking for '{league_lower}'.")
            continue # Try next fallback if available
        except Exception as e:
            logger.error(f"Unexpected error importing module '{module_name_to_try}' for league '{league_lower}': {e}", exc_info=True)
            # Decide if we should stop or try the next fallback
            continue

    if not module_found or not loaded_module_name:
        logger.error(f"No data module found for league '{league_lower}' after trying fallbacks: {module_load_attempts}")
        raise ValueError(f"No data module found for league: {league_lower}")

    # Use the originally requested league (uppercase) for the SPORT_MAP lookup
    # Normalize key for SPORT_MAP lookup (remove special chars, make upper)
    league_upper_for_api = ''.join(filter(str.isalnum, league)).upper()


    try:
        # Attempt to get data from the *loaded* module
        # Use specific names if they exist, otherwise default to empty dicts
        team_names_dict = getattr(module_found, "TEAM_FULL_NAMES", {}) # Used by team sports
        # Cater for different naming conventions in individual sports
        player_map = getattr(module_found, "TENNIS_PLAYERS", getattr(module_found, "MASTERS_GOLFERS", getattr(module_found, "ESPORTS_PLAYERS", {})))
        abbr_map = getattr(module_found, f"{loaded_module_name.upper()}_ABBREVIATIONS", player_map) # Fallback to player map if specific ABBREVIATIONS not found

        # --- Refined abbr_map finding ---
        # Try standard convention first
        standard_abbr_name = f"{loaded_module_name.upper()}_ABBREVIATIONS"
        abbr_map = getattr(module_found, standard_abbr_name, {})

        # If standard not found, check for known individual sport conventions
        if not abbr_map:
             individual_sport_conventions = {
                 "TENNIS_PLAYERS": ["tennis", "atp", "wta"],
                 "PGA_ABBREVIATIONS": ["pga", "golf"], # PGA might contain golfer abbreviations
                 "GOLFER_FULL_NAMES": ["pga", "golf", "masters", "lpga", "europeantour"], # This holds aliases, treat as part of full_names
                 "MASTERS_GOLFERS": ["masters"],
                 "ESPORTS_PLAYERS": ["esports", "csgo", "lol", "valorant", "esports_players"],
                 # Add NASCAR_DRIVERS etc. if defined
             }
             for dict_name, relevant_leagues in individual_sport_conventions.items():
                 if loaded_module_name in relevant_leagues:
                     potential_map = getattr(module_found, dict_name, None)
                     if potential_map is not None and isinstance(potential_map, dict):
                         # Decide if this map is for abbreviations or full names
                         if "ABBREVIATIONS" in dict_name or "GOLFERS" in dict_name or "PLAYERS" in dict_name: # Treat these as potential abbreviation sources
                             abbr_map = potential_map
                             logger.debug(f"Found individual sport map '{dict_name}' for abbr_map in module '{loaded_module_name}'")
                             break
                         # Note: GOLFER_FULL_NAMES handled separately below

        # Build full_names using TEAM_FULL_NAMES, GOLFER_FULL_NAMES (if golf), and abbr_map
        full_names = {}

        # 1. Add from TEAM_FULL_NAMES (for team sports)
        if team_names_dict:
             for alias, full_name in team_names_dict.items():
                  normalized_alias = alias.lower().strip()
                  normalized_full_name = full_name.lower().strip()
                  full_names[normalized_alias] = normalized_full_name
                  full_names[normalized_full_name] = normalized_full_name # Map full name to itself

        # 2. Add from GOLFER_FULL_NAMES (specific to golf modules)
        golfer_full_names_map = getattr(module_found, "GOLFER_FULL_NAMES", {})
        if golfer_full_names_map:
             for alias, full_name in golfer_full_names_map.items():
                 normalized_alias = alias.lower().strip()
                 normalized_full_name = full_name.lower().strip()
                 full_names[normalized_alias] = normalized_full_name
                 # Ensure full name maps to itself if not already present
                 if normalized_full_name not in full_names:
                       full_names[normalized_full_name] = normalized_full_name

        # 3. Add from abbr_map (can be team abbreviations or player aliases/nicknames)
        for abbr_or_alias, full_name in abbr_map.items():
            normalized_abbr_alias = abbr_or_alias.lower().strip()
            normalized_full_name = full_name.lower().strip()
            # Add the alias/abbr mapping
            full_names[normalized_abbr_alias] = normalized_full_name
            # Ensure full name maps to itself if not already present from other sources
            if normalized_full_name not in full_names:
                 full_names[normalized_full_name] = normalized_full_name

        # --- End Refined Logic ---

        logger.debug(f"Loaded full_names for {league_lower} (from module {loaded_module_name}): {len(full_names)} entries")
        logger.debug(f"Using abbreviations/aliases map for {league_lower} (from module {loaded_module_name}): {len(abbr_map)} entries")

        return {
            "abbreviations": abbr_map, # The primary abbreviation/player map found
            "full_names": full_names, # Combined aliases/names map
            "api_id": SPORT_MAP.get(league_upper_for_api, "") # Use normalized original requested league for API ID map
        }
    except AttributeError as e:
        logger.error(f"Missing expected dictionary structure in module {loaded_module_name}: {e}")
        raise ValueError(f"Data structure error in module {loaded_module_name}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing data from module {loaded_module_name} for league {league_lower}: {e}", exc_info=True)
        raise ValueError(f"Failed to process league data for {league_lower}")


def get_all_league_data() -> Dict[str, Dict[str, Any]]:
    """
    Load data for all supported leagues defined in SUPPORTED_LEAGUES.
    """
    all_data = {}
    # Iterate through the definitive list
    for league in SUPPORTED_LEAGUES:
        # --- MODIFIED SKIP LOGIC ---
        # Decide if you want to load data for generic parents. If not, skip them.
        # If generic parents should load fallback data (e.g., 'esports' loads 'esports_players'), don't skip.
        # Example: Skip generic parents if they *only* exist for UI selection flow.
        # if league in ["ncaa", "golf", "tennis", "esports", "horseracing"]:
        #      logger.debug(f"Skipping data load for generic parent league '{league}' in get_all_league_data.")
        #      continue
        # If generic parents *should* load data (e.g., from a fallback module), remove the skip logic.
        # For now, let's attempt to load all listed leagues. The fallback in get_league_data should handle it.
        # --- END MODIFICATION ---

        try:
            all_data[league] = get_league_data(league)
        except ValueError as e:
            # Log as warning, as some entries in SUPPORTED_LEAGUES might be placeholders
            # or intentionally lack direct data modules (like generic parents)
            logger.warning(f"Could not load data for league '{league}' in get_all_league_data: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading data for league '{league}' in get_all_league_data: {e}", exc_info=True)

    logger.info(f"Loaded data for {len(all_data)} leagues in get_all_league_data.")
    return all_data
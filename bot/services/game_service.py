# Modified content for bot/services/game_service.py
# Corrects the import path for db_manager and cache_manager

"""
Game service for the Discord betting bot.
Manages live game data fetching and storage.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
# Assuming settings load correctly
from config.settings import SUPPORTED_LEAGUES # Ensure this path is correct
# --- CORRECTED IMPORTS ---
# Use absolute path from 'bot' root
from bot.data.cache_manager import cache_manager
from bot.data.db_manager import db_manager
# --- END CORRECTED IMPORTS ---
from api.sports_api import SportsAPI # Assuming this path is correct
# Import custom errors if needed for specific handling
from bot.utils.errors import DatabaseQueryError # Assuming this path is correct

logger = logging.getLogger(__name__)

class GameService:
    """Service for managing live game data."""
    def __init__(self, bot):
        self.bot = bot
        self.games: Dict[str, Dict[str, Any]] = {} # In-memory store for active game details
        # Ensure SportsAPI is correctly initialized
        try:
            self.api = SportsAPI()
        except Exception as e:
             logger.critical(f"Failed to initialize SportsAPI: {e}", exc_info=True)
             # Handle error appropriately - maybe raise or set self.api to None?
             raise RuntimeError("Could not initialize SportsAPI for GameService") from e
        self._poll_task: Optional[asyncio.Task] = None # To manage the polling task
        logger.info("GameService initialized.")


    async def start(self) -> None:
        """Initialize the service and start polling."""
        if not hasattr(self.api, 'start') or not asyncio.iscoroutinefunction(self.api.start):
             logger.error("SportsAPI does not have an awaitable start method.")
             return # Cannot proceed without API start
        await self.api.start()
        await self._fetch_initial_games()
        # Start the polling loop as a background task
        if self._poll_task is None or self._poll_task.done():
             self._poll_task = asyncio.create_task(self._poll_games())
             logger.info("Game service polling started.")


    async def _fetch_initial_games(self) -> None:
        """Fetch initial game data from active bets in the database."""
        logger.info("Fetching initial game data for pending bets...")
        try:
            # Query for pending bets (using IS NULL check)
            query = """
                SELECT DISTINCT event_id, league, team, opponent, game_start
                FROM bets
                WHERE event_id IS NOT NULL
                  AND bet_won IS NULL
                  AND bet_loss IS NULL
            """
            # Use the correctly imported db_manager instance
            pending_bets = await db_manager.fetch(query)
            logger.debug(f"Found {len(pending_bets)} unique pending bet events to initialize.")

            active_event_ids = set()
            for bet in pending_bets:
                event_id = bet.get("event_id")
                if not event_id: continue

                event_id_str = str(event_id)
                active_event_ids.add(event_id_str)

                if event_id_str not in self.games:
                    game_start_dt = bet.get("game_start")
                    # Initialize game data structure
                    self.games[event_id_str] = {
                        "home_team": bet.get("team", "N/A"),
                        "away_team": bet.get("opponent", "N/A"),
                        "home_score": "0",
                        "away_score": "0",
                        "game_status": "Scheduled",
                        "completion": "0%",
                        "display_clock": "",
                        "game_period": 1,
                        "league": bet.get("league", "N/A"),
                        "last_update": datetime.now(timezone.utc).isoformat(),
                        "game_start": game_start_dt.isoformat() if game_start_dt else None
                    }
                    # Caching game starts (optional)
                    # if game_start_dt:
                    #     try:
                    #         await cache_manager.zadd("game_starts", {event_id_str: game_start_dt.timestamp()})
                    #     except Exception as cache_err:
                    #          logger.error(f"Failed to cache game start time for {event_id_str}: {cache_err}")


            # Poll immediately for these specific games if any found
            if active_event_ids:
                 logger.info(f"Polling initial status for {len(active_event_ids)} active events.")
                 await self._poll_specific_games(list(active_event_ids))

            await self._update_cache() # Cache the initial or updated state
            logger.info("Initial game data fetching complete.")

        except DatabaseQueryError as e:
            logger.error(f"Database error fetching initial games: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error fetching initial games: {e}", exc_info=True)


    async def _poll_games(self) -> None:
        """Periodically fetch live game updates from the API for relevant leagues."""
        # Wait for bot to be ready before starting the loop
        await self.bot.wait_until_ready()
        logger.info("GameService poll loop starting after bot ready.")
        await asyncio.sleep(5) # Small initial delay

        while True:
            try:
                start_time = datetime.now(timezone.utc)
                logger.debug("Starting game polling cycle...")

                # Determine leagues with currently pending bets
                leagues_query = """
                    SELECT DISTINCT league
                    FROM bets
                    WHERE bet_won IS NULL AND bet_loss IS NULL AND league IS NOT NULL
                """
                leagues_result = await db_manager.fetch(leagues_query)
                # Convert to lowercase set for easier comparison if needed
                active_leagues = {row['league'].lower() for row in leagues_result if row.get('league')}

                if not active_leagues:
                     logger.info("Polling: No active leagues with pending bets found. Sleeping.")
                     await asyncio.sleep(300) # Wait 5 minutes
                     continue

                logger.debug(f"Polling active leagues: {active_leagues}")
                updated_count = 0
                live_game_count = 0
                all_live_fixtures = []

                # Fetch live fixtures for each active league
                # Consider using asyncio.gather for concurrent API calls if supported
                tasks = [self.api.get_live_fixtures(league) for league in active_leagues]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for league, result in zip(active_leagues, results):
                     if isinstance(result, Exception):
                          logger.error(f"Failed to fetch fixtures for league {league}: {result}")
                     elif result: # Check if result is not None or empty
                          all_live_fixtures.extend(result)
                          logger.debug(f"Fetched {len(result)} live fixtures for league {league}")
                     else:
                          logger.debug(f"No live fixtures returned for league {league}")


                # Process fetched fixtures
                processed_event_ids = set()
                for event in all_live_fixtures:
                    # Add robust checks for missing keys in API response
                    fixture_data = event.get("fixture") if isinstance(event.get("fixture"), dict) else {}
                    event_id = str(fixture_data.get("id")) if fixture_data.get("id") else None
                    if not event_id: continue

                    processed_event_ids.add(event_id)

                    status_info = fixture_data.get("status") if isinstance(fixture_data.get("status"), dict) else {}
                    status_long = status_info.get("long", "Unknown")
                    elapsed = status_info.get("elapsed") # Might be None

                    teams_data = event.get("teams") if isinstance(event.get("teams"), dict) else {}
                    home_team_data = teams_data.get("home") if isinstance(teams_data.get("home"), dict) else {}
                    away_team_data = teams_data.get("away") if isinstance(teams_data.get("away"), dict) else {}
                    home_team = home_team_data.get("name", "N/A")
                    away_team = away_team_data.get("name", "N/A")

                    score_data = event.get("score") if isinstance(event.get("score"), dict) else {}
                    # Prioritize fulltime, then halftime score
                    current_score = score_data.get("fulltime") or score_data.get("halftime") or {}
                    if not isinstance(current_score, dict): current_score = {} # Ensure it's a dict
                    home_score_val = current_score.get("home")
                    away_score_val = current_score.get("away")
                    home_score = str(home_score_val) if home_score_val is not None else "0"
                    away_score = str(away_score_val) if away_score_val is not None else "0"

                    league_data = event.get("league") if isinstance(event.get("league"), dict) else {}
                    # Use league code from DB record if API name differs? For now, use API name.
                    league_name = league_data.get("name", "N/A")

                    # Normalize status and calculate completion/period
                    display_clock = str(elapsed) if elapsed is not None else "" # Handle None for elapsed
                    game_period = 1 # Default
                    completion = "0%"
                    normalized_status = status_long # Default

                    if status_long == "In Progress" or "HT" in status_long or status_long.isdigit(): # Consider halftime or numeric statuses
                         normalized_status = "In Progress"
                         completion = f"{elapsed}%" if elapsed is not None else "50%" # Estimate if elapsed missing
                         live_game_count += 1
                         # Add logic here to parse period from status if available (e.g., "Q1", "P2")
                    elif status_long == "Finished" or status_long == "FT":
                         normalized_status = "Finished"
                         completion = "100%"
                    elif status_long == "Not Started":
                         normalized_status = "Scheduled"
                    # Add checks for Postponed, Cancelled, etc.
                    elif status_long in ["Postponed", "Cancelled", "Abandoned", "Interrupted"]:
                         normalized_status = status_long # Keep specific status
                         completion = "N/A"


                    new_data = {
                        "home_team": home_team, "away_team": away_team,
                        "home_score": home_score, "away_score": away_score,
                        "game_status": normalized_status, # Use normalized status
                        "completion": completion,
                        "display_clock": display_clock,
                        "game_period": game_period,
                        "league": league_name,
                        "last_update": datetime.now(timezone.utc).isoformat()
                        # Keep 'game_start' from initial fetch if needed
                        # "game_start": self.games.get(event_id, {}).get("game_start")
                    }

                    # Update in-memory store only if data has changed
                    existing_game = self.games.get(event_id)
                    # Compare relevant fields, excluding last_update
                    fields_to_compare = ["home_score", "away_score", "game_status", "display_clock", "game_period"]
                    has_changed = not existing_game or any(existing_game.get(f) != new_data.get(f) for f in fields_to_compare)

                    if has_changed:
                        if existing_game: logger.info(f"Updating game {event_id}: status '{existing_game.get('game_status')}' -> '{normalized_status}', score {existing_game.get('home_score')}:{existing_game.get('away_score')} -> {home_score}:{away_score}")
                        else: logger.info(f"Adding new game data for {event_id}: status '{normalized_status}', score {home_score}:{away_score}")
                        # Preserve game_start if it existed
                        if existing_game: new_data["game_start"] = existing_game.get("game_start")
                        self.games[event_id] = new_data
                        updated_count += 1

                # Update Cache if changes occurred
                if updated_count > 0:
                    await self._update_cache()

                elapsed_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(f"Game polling cycle finished in {elapsed_time:.2f}s. Processed {len(processed_event_ids)} events, {live_game_count} live, {updated_count} updates.")

                # Wait for next interval
                sleep_duration = max(10, 300 - elapsed_time) # Aim for 5min interval, min 10s sleep
                await asyncio.sleep(sleep_duration)

            except DatabaseQueryError as e:
                 logger.error(f"Database error during game polling loop: {e}")
                 await asyncio.sleep(60) # Wait longer on DB error
            except asyncio.CancelledError:
                 logger.info("Game polling task cancelled.")
                 break # Exit loop cleanly
            except Exception as e:
                 logger.error(f"Unexpected error in game polling loop: {e}", exc_info=True)
                 await asyncio.sleep(60) # Wait after unexpected error


    async def _poll_specific_games(self, event_ids: list[str]) -> None:
         """Fetch updates for a specific list of event IDs."""
         if not event_ids: return
         logger.debug(f"Polling specific event IDs: {event_ids}")
         updated_count = 0
         # Use asyncio.gather for concurrent fetches
         tasks = [self.api.get_fixture_by_id(eid) for eid in event_ids]
         results = await asyncio.gather(*tasks, return_exceptions=True)

         for event_id, result in zip(event_ids, results):
             try:
                  if isinstance(result, Exception):
                       logger.error(f"Error polling specific event {event_id}: {result}")
                       continue # Skip this one on error

                  if result: # API returned data
                       event_data = result # Result is the event data directly
                       # Process event_data similar to _poll_games loop
                       fixture_data = event_data.get("fixture", {})
                       status_info = fixture_data.get("status", {})
                       status_long = status_info.get("long", "Unknown")
                       elapsed = status_info.get("elapsed")
                       teams_data = event_data.get("teams", {})
                       home_team = teams_data.get("home", {}).get("name", "N/A")
                       away_team = teams_data.get("away", {}).get("name", "N/A")
                       score_data = event_data.get("score", {})
                       current_score = score_data.get("fulltime") or score_data.get("halftime") or {}
                       home_score = str(current_score.get("home", 0) if current_score.get("home") is not None else 0)
                       away_score = str(current_score.get("away", 0) if current_score.get("away") is not None else 0)
                       league_data = event_data.get("league", {})
                       league_name = league_data.get("name", "N/A")
                       display_clock = str(elapsed) if elapsed else ""
                       game_period = 1 # TODO: Improve period logic
                       # Normalize status
                       normalized_status = status_long
                       if status_long == "In Progress" or "HT" in status_long or status_long.isdigit(): normalized_status = "In Progress"
                       elif status_long == "Finished" or status_long == "FT": normalized_status = "Finished"
                       elif status_long == "Not Started": normalized_status = "Scheduled"
                       completion = "100%" if normalized_status == "Finished" else ("0%" if normalized_status == "Scheduled" else f"{elapsed}%" if elapsed else "50%")

                       new_data = {
                           "home_team": home_team, "away_team": away_team,
                           "home_score": home_score, "away_score": away_score,
                           "game_status": normalized_status, "completion": completion,
                           "display_clock": display_clock, "game_period": game_period,
                           "league": league_name, "last_update": datetime.now(timezone.utc).isoformat()
                       }
                       # Compare relevant fields before updating
                       existing_game = self.games.get(event_id)
                       fields_to_compare = ["home_score", "away_score", "game_status", "display_clock", "game_period"]
                       has_changed = not existing_game or any(existing_game.get(f) != new_data.get(f) for f in fields_to_compare)

                       if has_changed:
                            if existing_game: new_data["game_start"] = existing_game.get("game_start") # Preserve start time
                            self.games[event_id] = new_data
                            updated_count += 1
                            logger.info(f"Updated specific game {event_id} state via _poll_specific_games.")
                  else:
                       logger.debug(f"No data returned from API for specific event {event_id}")

             except Exception as e: # Catch errors processing a specific result
                  logger.error(f"Error processing specific event {event_id} result: {e}", exc_info=True)

         if updated_count > 0:
             await self._update_cache()


    async def _update_cache(self) -> None:
        """Cache the current game state in Redis."""
        try:
            # Serialize the dictionary to JSON string
            games_json = json.dumps(self.games)
            # Use cache_manager (ensure it's initialized and connected)
            await cache_manager.set("live_games", games_json, ttl=600) # Cache for 10 minutes
            logger.debug(f"Updated live games cache with {len(self.games)} games.")
        except Exception as e:
            logger.error(f"Failed to update game cache: {e}", exc_info=True)


    async def get_game(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve game data by event ID from the in-memory store."""
        # Ensure event_id is string
        event_id_str = str(event_id)
        game_data = self.games.get(event_id_str)
        if game_data:
             # logger.debug(f"In-memory hit for get_game: {event_id_str}") # Reduce log noise
             return game_data
        else:
             # Optionally check cache as fallback? Or trigger API fetch?
             # For now, just return None if not in memory.
             logger.warning(f"In-memory miss for get_game: {event_id_str}. Game data not loaded or expired.")
             # Consider fetching if crucial:
             # await self._poll_specific_games([event_id_str])
             # return self.games.get(event_id_str)
             return None


    async def stop(self) -> None:
        """Stop the service and clean up."""
        logger.info("Stopping Game Service...")
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                 await self._poll_task # Wait for cancellation
            except asyncio.CancelledError:
                 logger.info("Game service polling task successfully cancelled.")
            except Exception as e:
                 logger.error(f"Error during poll task cancellation: {e}")
        if self.api and hasattr(self.api, 'close') and asyncio.iscoroutinefunction(self.api.close):
            await self.api.close()
        self.games.clear()
        logger.info("Game service stopped.")
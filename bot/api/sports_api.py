"""
Sports API client for the Discord betting bot.
Handles interactions with the API-Football service.
"""

import aiohttp
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from config.settings import API_KEY, API_BASE_URL
from bot.data.cache_manager import cache_manager
from bot.data.league.league_dictionaries import SPORT_MAP, SUPPORTED_LEAGUES
from utils.rate_limiter import limit_api_call
# <<< CHANGE START >>>
# Import new custom error types
from utils.errors import APIConnectionError, APITimeoutError, APIResponseError
# <<< CHANGE END >>>


logger = logging.getLogger(__name__)

class SportsAPI:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {"x-apisports-key": API_KEY}
        # <<< CHANGE START >>>
        # Added a default timeout
        self.timeout = aiohttp.ClientTimeout(total=15) # 15 seconds total timeout
        # <<< CHANGE END >>>

    async def start(self) -> None:
        if not self.session or self.session.closed:
            # <<< CHANGE START >>>
            # Pass timeout to session
            self.session = aiohttp.ClientSession(headers=self.headers, timeout=self.timeout)
            # <<< CHANGE END >>>
            logger.info("Sports API client session started")

    @limit_api_call
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.session:
            await self.start()

        cache_key = f"api:{endpoint}:{json.dumps(params, sort_keys=True)}"
        try:
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for API request: {endpoint}")
                return json.loads(cached_data)
        except Exception as e: # Catch potential cache errors but don't stop the request
             logger.error(f"Cache retrieval failed for key {cache_key}: {e}")


        url = f"{API_BASE_URL}{endpoint}"
        try:
            logger.debug(f"Making API request to {url} with params {params}")
            async with self.session.get(url, params=params) as response:
                # <<< CHANGE START >>>
                # Check for non-200 status codes
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"API request failed: {endpoint} - Status: {response.status}, Response: {error_text}")
                    # Raise specific error based on status if needed, or a general one
                    raise APIResponseError(
                        message=f"API returned status {response.status}",
                        status_code=response.status,
                        url=url
                    )
                # Check content type before decoding JSON
                if 'application/json' not in response.headers.get('Content-Type', ''):
                    error_text = await response.text()
                    logger.error(f"API response is not JSON: {endpoint} - Content-Type: {response.headers.get('Content-Type')}, Response: {error_text}")
                    raise APIResponseError(
                        message="API response was not JSON",
                        url=url
                    )

                data = await response.json()
                # Basic check if response key exists (adjust based on actual API structure)
                if "response" not in data:
                    logger.warning(f"API response structure unexpected: Missing 'response' key. Data: {data}")
                    # Decide if this is an error or just empty data
                    # raise APIResponseError(message="API response missing 'response' key", url=url)

                # Cache the valid data
                try:
                    await cache_manager.set(cache_key, json.dumps(data), ttl=300) # 5 min TTL
                except Exception as e: # Catch potential cache errors
                    logger.error(f"Cache storage failed for key {cache_key}: {e}")

                logger.debug(f"API request successful: {endpoint}")
                return data
        # Catch specific exceptions
        except aiohttp.ClientConnectorError as e:
            logger.error(f"API connection error to {url}: {e}", exc_info=True)
            raise APIConnectionError(message=f"Could not connect to API endpoint: {e}", url=url, original_exception=e)
        except asyncio.TimeoutError as e:
            logger.error(f"API request timed out to {url}: {e}", exc_info=True)
            raise APITimeoutError(message="Request timed out", url=url, original_exception=e)
        except aiohttp.ClientResponseError as e: # Covers non-200 status errors if not caught above
            logger.error(f"API client response error {e.status} for {url}: {e.message}", exc_info=True)
            raise APIResponseError(message=e.message, status_code=e.status, url=url, original_exception=e)
        except aiohttp.ClientError as e: # Catch other general aiohttp client errors
            logger.error(f"API client error for {url}: {e}", exc_info=True)
            raise APIError(message=f"An API client error occurred: {e}", original_exception=e)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from {url}: {e}", exc_info=True)
            raise APIResponseError(message=f"Invalid JSON received from API: {e}", url=url, original_exception=e)
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error during API request to {url}: {e}", exc_info=True)
            # Re-raise as a generic BettingBotError or a specific new one if needed
            raise BettingBotError(message=f"An unexpected error occurred during the API request: {e}", original_exception=e)
        # <<< CHANGE END >>>


    async def get_live_fixtures(self, league: str) -> List[Dict[str, Any]]:
        league_upper = league.upper() # Use a different variable name
        if league_upper not in SUPPORTED_LEAGUES:
            logger.warning(f"Unsupported league for live fixtures: {league}")
            return []

        # <<< CHANGE START >>>
        # Simplified logic, rely on _make_request error handling
        # sport_key = SPORT_MAP.get(league_upper, league_upper.lower()) # sport_key seems unused
        params = {"live": "all"} # Consider adding league filter if API supports it?
        data = await self._make_request(endpoint="fixtures", params=params)

        # Defensive coding: Check if data and 'response' key exist
        if not data or "response" not in data:
             logger.warning(f"No valid response data received for live fixtures query: {params}")
             return []

        fixtures = data.get("response", [])

        # Ensure fixture and league data exist before accessing keys
        filtered_fixtures = [
            fixture for fixture in fixtures
            if fixture and isinstance(fixture.get("league"), dict) and fixture["league"].get("name", "").upper() == league_upper
        ]
        logger.info(f"Fetched {len(filtered_fixtures)} live fixtures matching league {league_upper} from API response of {len(fixtures)} total.")
        return filtered_fixtures
        # <<< CHANGE END >>>


    async def get_fixture_by_id(self, fixture_id: str) -> Optional[Dict[str, Any]]:
         # <<< CHANGE START >>>
         # Validate fixture_id type more robustly
        if not fixture_id or not isinstance(fixture_id, (str, int)):
             logger.warning(f"Invalid fixture ID type or value: {fixture_id}")
             return None

        fixture_id_str = str(fixture_id) # Ensure it's a string for API call/logging

        # Simplified logic, rely on _make_request error handling
        data = await self._make_request(endpoint="fixtures", params={"id": fixture_id_str})

        # Defensive coding
        if not data or "response" not in data:
             logger.warning(f"No valid response data received for fixture ID {fixture_id_str}")
             return None

        fixtures = data.get("response", [])
        if fixtures and isinstance(fixtures, list) and len(fixtures) > 0:
            # Check if the first element is a dictionary
            if isinstance(fixtures[0], dict):
                logger.debug(f"Fetched fixture data for ID {fixture_id_str}")
                return fixtures[0]
            else:
                logger.warning(f"Fixture data for ID {fixture_id_str} is not in expected format: {fixtures[0]}")
                return None
        # <<< CHANGE END >>>

        logger.warning(f"No fixture found for ID {fixture_id_str}")
        return None

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Sports API client session closed")
            self.session = None

# Instantiate the client (if you want a singleton instance readily available)
# sports_api_client = SportsAPI() # You might manage instantiation in core.py instead
import aiohttp
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from config.settings import API_KEY, API_BASE_URL
from bot.data.cache_manager import CacheManager
from bot.data.league.league_dictionaries import SPORT_MAP, SUPPORTED_LEAGUES
from utils.rate_limiter import limit_api_call

class PlayerStatsAPI:
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.session = None
        self.headers = {"x-apisports-key": API_KEY}

    async def start(self):
        """Initialize the aiohttp session."""
        self.session = aiohttp.ClientSession(headers=self.headers)
        logging.info("PlayerStatsAPI started.")

    @limit_api_call
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Make an API request and return the JSON response."""
        url = f"{API_BASE_URL}/{endpoint}"
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                logging.error("API request failed: %s, status=%s", url, response.status)
                return None
        except Exception as e:
            logging.error("Error in API request to %s: %s", url, e)
            return None

    async def get_player_stats(self, player_id: int, league: str) -> Dict[str, Any]:
        """Fetch player stats, including name, for a given player ID and league."""
        cache_key = f"player_stats:{player_id}:{league}"
        cached = await self.cache_manager.get(cache_key)
        if cached:
            return json.loads(cached)

        # Fetch player name first
        player_info = await self._get_player_info(player_id)
        if not player_info:
            return {"player_id": player_id, "name": f"Player {player_id}", "stats": {}}

        player_name = player_info.get("name", f"Player {player_id}")

        # Fetch stats
        league_id = self._get_league_id(league)
        if not league_id:
            return {"player_id": player_id, "name": player_name, "stats": {}}

        params = {"player": player_id, "league": league_id}
        data = await self._make_request("players/statistics", params)
        stats = data.get("response", {}) if data else {}

        result = {"player_id": player_id, "name": player_name, "stats": stats}
        await self.cache_manager.set(cache_key, json.dumps(result), ttl=3600)  # 1-hour TTL
        return result

    async def _get_player_info(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Fetch player info (including name) from the /players endpoint."""
        cache_key = f"player_info:{player_id}"
        cached = await self.cache_manager.get(cache_key)
        if cached:
            return json.loads(cached)

        params = {"id": player_id}
        data = await self._make_request("players", params)
        if data and "response" in data and data["response"]:
            player_info = data["response"][0].get("player", {})
            await self.cache_manager.set(cache_key, json.dumps(player_info), ttl=86400)  # 24-hour TTL
            return player_info
        return None

    def _get_league_id(self, league: str) -> Optional[str]:
        """Map league name to API identifier."""
        sport = SPORT_MAP.get(league.upper(), {}).get("sport")
        return sport if sport else None

    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            logging.info("PlayerStatsAPI session closed.")
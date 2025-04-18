# Modified content for League Data/sport_handler.py

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from discord import SelectOption, Interaction, TextStyle
from discord.ui import Modal, TextInput
import logging

# --- Use absolute imports ---
from bot.config.settings import DEFAULT_AVATAR_URL
# Assuming image utils path is correct relative to project root
# Use the updated league_team_handler path if needed
from bot.data.league.league_team_handler import standardize_league_code # For logo fetching context
from bot.utils.image_utils.team_logos import get_team_logo_url_from_csv # Import corrected path if necessary

# --- Use Forward reference for type hinting ---
if TYPE_CHECKING:
    # This avoids the circular import error at runtime
    # but allows type checkers (like mypy) to understand the type
    from bot.services.bet_service import (
        BetWorkflowView, PlayerBetModal, TeamBetModal, NASCARDriverBetModal,
        NASCRaceBetModal, GolfGolferBetModal, GolfTournamentBetModal,
        TennisPlayerBetModal, TennisMatchBetModal, UFCFighterBetModal,
        UFCFightBetModal, EsportsPlayerBetModal, EsportsMatchBetModal,
        HorseBetModal, HorseRaceBetModal
    )

logger = logging.getLogger(__name__)

# --- Base Sport Handler ---
class SportHandler(ABC):
    """Base class for sport-specific handlers."""
    league: str # Add type hint for league attribute expected in subclasses

    @abstractmethod
    def get_sub_league_options(self) -> List[SelectOption]:
        """Return sub-league options if applicable (e.g., NCAA sports).
           Most handlers will return [] unless they manage sub-league state themselves.
        """
        pass

    @abstractmethod
    def get_path_options(self) -> List[Dict[str, str]]:
        """Return sport-specific path options with labels and custom_ids."""
        pass

    @abstractmethod
    def get_modal(self, view: 'BetWorkflowView', path: str) -> Modal:
        """Return the appropriate modal for the selected path based on the specific league."""
        pass

    @abstractmethod
    async def build_preview_data(self, view: 'BetWorkflowView') -> Dict[str, Any]:
        """Build data needed for the bet preview embed. Includes logo URLs. Uses self.league context."""
        pass

    @abstractmethod
    async def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate the data submitted via the modal."""
        pass

# --- Team Sport Handler (NFL, NBA, MLB, NHL, EPL, MLS, WNBA, CFL, Soccer Leagues) ---
class TeamSportHandler(SportHandler):
    """Handler for generic team-based sports."""
    def __init__(self, league: str):
        # Ensure league is stored lowercase for consistency
        self.league = league.lower()
        logger.debug(f"TeamSportHandler initialized for league: '{self.league}'")

    def get_sub_league_options(self) -> List[SelectOption]:
        # Standard team sports don't have sub-leagues in this structure
        return []

    def get_path_options(self) -> List[Dict[str, str]]:
        # Default paths for most team sports
        return [
            {"label": "Bet on a Player", "custom_id": "path_player"},
            {"label": "Bet on a Team", "custom_id": "path_team"}
        ]

    def get_modal(self, view: 'BetWorkflowView', path: str) -> Modal:
        logger.debug(f"TeamSportHandler ({self.league}) getting modal for path: '{path}'")
        # Dynamically import Modal classes here if needed, or ensure they are imported at top level
        from bot.services.bet_service import PlayerBetModal, TeamBetModal # Ensure this import works

        title_league = self.league.upper() # Use the specific league code for the title
        if path == "Bet on a Player":
            return PlayerBetModal(view, title=f"Enter {title_league} Player Bet Details")
        elif path == "Bet on a Team":
            return TeamBetModal(view, title=f"Enter {title_league} Team Bet Details")
        else:
             # Handle invalid path robustly
            logger.error(f"Invalid path requested in TeamSportHandler ({self.league}): {path}")
            raise ValueError(f"Invalid bet path for {title_league}: {path}")

    async def build_preview_data(self, view: 'BetWorkflowView') -> Dict[str, Any]:
        data = view.current_leg_data
        path = view.path # Get path from view ('Bet on a Player' or 'Bet on a Team')
        logger.debug(f"TeamSportHandler ({self.league}) building preview data for path '{path}': {data}")

        team_input = data.get('team') # Team picked OR player's team
        opponent_input = data.get('opponent') # Opponent team

        # Initialize logo URLs
        team_logo_url: Optional[str] = DEFAULT_AVATAR_URL # Default for team/player's team
        league_logo_url: Optional[str] = DEFAULT_AVATAR_URL # Default for league
        opponent_logo_url: Optional[str] = DEFAULT_AVATAR_URL # Default for opponent

        # --- Fetch Logos using self.league (which is the specific league code) ---
        try:
            # Fetch league logo (pass None for team_name)
            _, league_logo_url_fetched = await get_team_logo_url_from_csv(self.league, None)
            if league_logo_url_fetched: league_logo_url = league_logo_url_fetched
            else: logger.warning(f"TeamSportHandler ({self.league}): Did not get league logo URL for '{self.league}'.")

            # Fetch primary team/entity logo
            if team_input:
                team_logo_url_fetched, _ = await get_team_logo_url_from_csv(self.league, team_input)
                if team_logo_url_fetched: team_logo_url = team_logo_url_fetched
                else: logger.warning(f"TeamSportHandler ({self.league}): Did not get primary logo URL for '{team_input}'.")
            else: logger.warning(f"TeamSportHandler ({self.league}): No primary team/entity input provided.")


            # Fetch opponent logo if opponent name is provided
            if opponent_input:
                opponent_logo_url_fetched, _ = await get_team_logo_url_from_csv(self.league, opponent_input)
                if opponent_logo_url_fetched: opponent_logo_url = opponent_logo_url_fetched
                else: logger.warning(f"TeamSportHandler ({self.league}): Did not get opponent logo URL for '{opponent_input}'.")

        except Exception as e:
            logger.error(f"Error fetching logos in TeamSportHandler ({self.league}): {e}", exc_info=True)
            # Defaults are already set, so just log the error

        logger.debug(f"TeamSportHandler ({self.league}) Logo URLs - Primary: '{team_logo_url}', League: '{league_logo_url}', Opponent: '{opponent_logo_url}'")

        # --- Build Description ---
        description = "Bet details missing." # Default message
        team_display = team_input or "N/A"
        opponent_display = opponent_input or "N/A"

        if path == "Bet on a Team":
            line = data.get('line', 'N/A')
            odds = data.get('odds', 'N/A')
            description = (
                f"{team_display} vs {opponent_display}\n\n"
                f"**Pick:** {team_display} {line}\n"
                f"**Odds:** {odds}"
            )
        elif path == "Bet on a Player":
            player = data.get('player_name', 'N/A')
            prop = data.get('prop', 'N/A')
            odds = data.get('odds', 'N/A')
            # Player's team is stored in 'team_input'
            player_team_display = team_display
            description = (
                f"**Matchup:** {player_team_display} vs {opponent_display}\n\n"
                f"**Player:** {player}\n"
                f"**Prop:** {prop}\n"
                f"**Odds:** {odds}"
            )

        # Structure the final preview data dictionary
        preview = {
            'team_logo_url': team_logo_url, # Primary logo (player's team or team picked)
            'league_logo_url': league_logo_url,
            # Optionally pass opponent logo if needed by view/embed structure
            # 'opponent_logo_url': opponent_logo_url,
            'description': description,
            'team_display': team_display, # Pass names for potential use in title/footer
            'opponent_display': opponent_display,
        }
        logger.debug(f"TeamSportHandler ({self.league}) returning preview data: {preview}")
        return preview

    async def validate_data(self, data: Dict[str, Any]) -> bool:
        # Assumes 'path' is added to data dict before calling validation
        path = data.get('path')
        logger.debug(f"TeamSportHandler ({self.league}) validating data for path '{path}': {data}")

        if path == "Bet on a Player":
            # Player bets need player name, their team, opponent, prop, odds
            req = ['team', 'opponent', 'player_name', 'prop', 'odds']
        elif path == "Bet on a Team":
            # Team bets need team picked, opponent, line, odds
            req = ['team', 'opponent', 'line', 'odds']
        else:
            logger.warning(f"Validation failed: Unknown path '{path}' in TeamSportHandler for league '{self.league}'")
            return False

        # Check if all required keys exist and have non-empty string values
        valid = all(data.get(k) and isinstance(data.get(k), str) and data.get(k).strip() for k in req)
        if not valid:
            missing = [k for k in req if not (data.get(k) and isinstance(data.get(k), str) and data.get(k).strip())]
            logger.warning(f"Validation failed for path '{path}' in league '{self.league}'. Missing/invalid fields: {missing}")
        else:
            logger.debug(f"Validation successful for path '{path}' in league '{self.league}'.")
        return valid

# --- NCAA Handler (No changes needed if factory passes specific sub-league) ---
class NCAASportHandler(TeamSportHandler):
    """Handler for NCAA sports. Inherits from TeamSportHandler.
       The factory should instantiate this with the specific sub-league code (e.g., 'ncaaf').
    """
    # SUB_LEAGUES list might not be needed here if selection happens in bet_service.py
    # SUB_LEAGUES = ['ncaaf', 'ncaam', 'ncaaw', 'ncaawvb']

    def __init__(self, league: str):
        # league will be the specific sub-league code (e.g., 'ncaaf')
        super().__init__(league) # Initialize TeamSportHandler with the specific sub-league
        logger.debug(f"NCAASportHandler initialized for sub-league: '{self.league}'")

    # No need to override get_sub_league_options if selection happens before handler creation
    # Inherits get_path_options, get_modal, build_preview_data, validate_data from TeamSportHandler
    # These methods will now operate with self.league set to the specific sub-league (e.g., 'ncaaf')

# --- NASCAR Handler (Unchanged) ---
class NASCARSportHandler(SportHandler):
    # ... (Keep existing definition) ...
    def __init__(self):
        self.league = "nascar" # Fixed league code for NASCAR
        logger.debug("NASCARSportHandler initialized.")

    def get_sub_league_options(self) -> List[SelectOption]: return []
    def get_path_options(self) -> List[Dict[str, str]]:
        return [
            {"label": "Bet on a Driver", "custom_id": "path_driver"},
            {"label": "Bet on a Race Prop", "custom_id": "path_race_prop"}
        ]
    def get_modal(self, view: 'BetWorkflowView', path: str) -> Modal:
        logger.debug(f"NASCARSportHandler getting modal for path: '{path}'")
        from bot.services.bet_service import NASCARDriverBetModal, NASCRaceBetModal
        if path == "Bet on a Driver": return NASCARDriverBetModal(view)
        elif path == "Bet on a Race Prop": return NASCRaceBetModal(view)
        logger.error(f"Invalid path requested in NASCARSportHandler: {path}")
        raise ValueError(f"Invalid path for NASCAR: {path}")

    async def build_preview_data(self, view: 'BetWorkflowView') -> Dict[str, Any]:
        data = view.current_leg_data
        path = view.path
        logger.debug(f"NASCARSportHandler building preview data for path '{path}': {data}")
        league_logo_url = DEFAULT_AVATAR_URL
        try:
            _, league_logo_url_fetched = await get_team_logo_url_from_csv(self.league, None)
            if league_logo_url_fetched: league_logo_url = league_logo_url_fetched
            else: logger.warning(f"NASCARSportHandler: Did not get league logo URL for '{self.league}'.")
        except Exception as e: logger.error(f"Error fetching {self.league} logo: {e}", exc_info=True)

        logger.debug(f"NASCARSportHandler Logo URLs - League: '{league_logo_url}'")
        description = "NASCAR Bet details missing."

        if path == "Bet on a Driver":
            driver = data.get('driver', 'N/A')
            car_number = data.get('car_number', '#?')
            line = data.get('line', 'N/A') # This is the 'Pick' in the modal
            odds = data.get('odds', 'N/A')
            description = (
                f"**Driver:** {driver} (#{car_number})\n"
                f"**Pick:** {line}\n"
                f"**Odds:** {odds}"
            )
        elif path == "Bet on a Race Prop":
            event = data.get('event', 'N/A')
            laps = data.get('laps', 'N/A') # Condition field
            outcome = data.get('outcome', 'N/A') # Pick field
            odds = data.get('odds', 'N/A')
            description = (
                f"**Event Prop:** {event}\n"
                f"**Condition:** {laps}\n"
                f"**Pick:** {outcome}\n"
                f"**Odds:** {odds}"
            )

        preview = {
            'team_logo_url': None, # No primary entity logo for NASCAR paths like this
            'league_logo_url': league_logo_url,
            'description': description,
        }
        logger.debug(f"NASCARSportHandler returning preview data: {preview}")
        return preview

    async def validate_data(self, data: Dict[str, Any]) -> bool:
        path = data.get('path')
        logger.debug(f"NASCARSportHandler validating data for path '{path}': {data}")
        if path == "Bet on a Driver": req = ['driver', 'car_number', 'line', 'odds']
        elif path == "Bet on a Race Prop": req = ['event', 'laps', 'outcome', 'odds']
        else: logger.warning(f"Validation failed: Unknown path '{path}'"); return False
        valid = all(data.get(k) and isinstance(data.get(k), str) and data.get(k).strip() for k in req)
        if not valid: logger.warning(f"Validation failed for path '{path}'. Missing/invalid fields: {[k for k in req if not (data.get(k) and isinstance(data.get(k), str) and data.get(k).strip())]}")
        else: logger.debug(f"Validation successful for path '{path}'.")
        return valid


# --- Golf Handler (Instantiated with specific tour/event code) ---
class GolfSportHandler(SportHandler):
    """Handler for Golf (PGA, Masters, LPGA, European Tour etc.)."""
    def __init__(self, league: str):
        # league is the specific code like 'pga', 'masters', 'lpga'
        self.league = league.lower()
        logger.debug(f"GolfSportHandler initialized for league: '{self.league}'")

    def get_sub_league_options(self) -> List[SelectOption]: return [] # Selection happens before handler creation

    def get_path_options(self) -> List[Dict[str, str]]:
        return [
            {"label": "Bet on a Golfer", "custom_id": "path_golfer"},
            {"label": "Bet on a Tournament Prop", "custom_id": "path_tournament_prop"}
        ]

    def get_modal(self, view: 'BetWorkflowView', path: str) -> Modal:
        logger.debug(f"GolfSportHandler ({self.league}) getting modal for path: '{path}'")
        from bot.services.bet_service import GolfGolferBetModal, GolfTournamentBetModal
        title_league = self.league.upper() # Use specific code (PGA, MASTERS, LPGA)
        if path == "Bet on a Golfer": return GolfGolferBetModal(view, title=f"Enter {title_league} Golfer Bet")
        elif path == "Bet on a Tournament Prop": return GolfTournamentBetModal(view, title=f"Enter {title_league} Tournament Prop")
        logger.error(f"Invalid path requested in GolfSportHandler ({self.league}): {path}")
        raise ValueError(f"Invalid path for Golf ({self.league}): {path}")

    async def build_preview_data(self, view: 'BetWorkflowView') -> Dict[str, Any]:
        data = view.current_leg_data
        path = view.path
        logger.debug(f"GolfSportHandler ({self.league}) building preview data for path '{path}': {data}")
        league_logo_url = DEFAULT_AVATAR_URL
        try:
             # Use specific league code (pga, masters, lpga) for logo fetch
            _, league_logo_url_fetched = await get_team_logo_url_from_csv(self.league, None)
            if league_logo_url_fetched: league_logo_url = league_logo_url_fetched
            else: logger.warning(f"GolfSportHandler ({self.league}): Did not get league logo URL.")
        except Exception as e: logger.error(f"Error fetching {self.league} logo: {e}", exc_info=True)

        logger.debug(f"GolfSportHandler ({self.league}) Logo URLs - League: '{league_logo_url}'")
        description = "Golf Bet details missing."

        if path == "Bet on a Golfer":
            golfer = data.get('golfer', 'N/A')
            line = data.get('line', 'N/A') # The pick
            odds = data.get('odds', 'N/A')
            description = f"**Golfer:** {golfer}\n**Pick:** {line}\n**Odds:** {odds}"
        elif path == "Bet on a Tournament Prop":
            event = data.get('event', 'N/A') # Prop description
            outcome = data.get('outcome', 'N/A') # The pick
            odds = data.get('odds', 'N/A')
            description = f"**Tournament Prop:** {event}\n**Pick:** {outcome}\n**Odds:** {odds}"

        preview = {
            'team_logo_url': None, # No primary 'team' logo for golf paths
            'league_logo_url': league_logo_url, # Logo for the specific tour/event
            'description': description,
        }
        logger.debug(f"GolfSportHandler ({self.league}) returning preview data: {preview}")
        return preview

    async def validate_data(self, data: Dict[str, Any]) -> bool:
        path = data.get('path')
        logger.debug(f"GolfSportHandler ({self.league}) validating data for path '{path}': {data}")
        if path == "Bet on a Golfer": req = ['golfer', 'line', 'odds']
        elif path == "Bet on a Tournament Prop": req = ['event', 'outcome', 'odds']
        else: logger.warning(f"Validation failed: Unknown path '{path}'"); return False
        valid = all(data.get(k) and isinstance(data.get(k), str) and data.get(k).strip() for k in req)
        if not valid: logger.warning(f"Validation failed for path '{path}' in league '{self.league}'. Missing/invalid fields: {[k for k in req if not (data.get(k) and isinstance(data.get(k), str) and data.get(k).strip())]}")
        else: logger.debug(f"Validation successful for path '{path}'.")
        return valid


# --- Tennis Handler (Instantiated with specific tour code) ---
class TennisSportHandler(SportHandler):
    """Handler for Tennis (ATP, WTA)."""
    def __init__(self, league: str):
        # league is the specific code 'atp' or 'wta'
        self.league = league.lower()
        logger.debug(f"TennisSportHandler initialized for league: '{self.league}'")

    def get_sub_league_options(self) -> List[SelectOption]: return [] # Selection happens before handler creation

    def get_path_options(self) -> List[Dict[str, str]]:
        return [
            {"label": "Bet on a Player Prop", "custom_id": "path_player_prop"},
            {"label": "Bet on a Match", "custom_id": "path_match"}
        ]

    def get_modal(self, view: 'BetWorkflowView', path: str) -> Modal:
        logger.debug(f"TennisSportHandler ({self.league}) getting modal for path: '{path}'")
        from bot.services.bet_service import TennisPlayerBetModal, TennisMatchBetModal
        title_league = self.league.upper() # ATP or WTA
        if path == "Bet on a Player Prop": return TennisPlayerBetModal(view, title=f"Enter {title_league} Player Prop")
        elif path == "Bet on a Match": return TennisMatchBetModal(view, title=f"Enter {title_league} Match Bet")
        logger.error(f"Invalid path requested in TennisSportHandler ({self.league}): {path}")
        raise ValueError(f"Invalid path for Tennis ({self.league}): {path}")

    async def build_preview_data(self, view: 'BetWorkflowView') -> Dict[str, Any]:
        data = view.current_leg_data
        path = view.path
        logger.debug(f"TennisSportHandler ({self.league}) building preview data for path '{path}': {data}")
        league_logo_url = DEFAULT_AVATAR_URL
        try:
            # Use specific league code (atp/wta) for logo fetch
            _, league_logo_url_fetched = await get_team_logo_url_from_csv(self.league, None)
            if league_logo_url_fetched: league_logo_url = league_logo_url_fetched
            else: logger.warning(f"TennisSportHandler ({self.league}): Did not get league logo URL.")
        except Exception as e: logger.error(f"Error fetching {self.league} logo: {e}", exc_info=True)

        logger.debug(f"TennisSportHandler ({self.league}) Logo URLs - League: '{league_logo_url}'")
        description = "Tennis Bet details missing."

        if path == "Bet on a Player Prop":
            player = data.get('player', 'N/A')
            opponent = data.get('opponent', 'N/A')
            prop = data.get('prop', 'N/A')
            odds = data.get('odds', 'N/A')
            description = f"**Match:** {player} vs {opponent}\n**Player Prop:** {prop}\n**Odds:** {odds}"
        elif path == "Bet on a Match":
            player1 = data.get('player1', 'N/A')
            player2 = data.get('player2', 'N/A')
            line = data.get('line', 'N/A') # The pick
            odds = data.get('odds', 'N/A')
            description = f"**Match:** {player1} vs {player2}\n**Pick:** {line}\n**Odds:** {odds}"

        preview = {
            'team_logo_url': None, # No primary 'team' logo for tennis paths
            'league_logo_url': league_logo_url, # ATP or WTA logo
            'description': description,
        }
        logger.debug(f"TennisSportHandler ({self.league}) returning preview data: {preview}")
        return preview

    async def validate_data(self, data: Dict[str, Any]) -> bool:
        path = data.get('path')
        logger.debug(f"TennisSportHandler ({self.league}) validating data for path '{path}': {data}")
        if path == "Bet on a Player Prop": req = ['player', 'opponent', 'prop', 'odds']
        elif path == "Bet on a Match": req = ['player1', 'player2', 'line', 'odds']
        else: logger.warning(f"Validation failed: Unknown path '{path}'"); return False
        valid = all(data.get(k) and isinstance(data.get(k), str) and data.get(k).strip() for k in req)
        if not valid: logger.warning(f"Validation failed for path '{path}' in league '{self.league}'. Missing/invalid fields: {[k for k in req if not (data.get(k) and isinstance(data.get(k), str) and data.get(k).strip())]}")
        else: logger.debug(f"Validation successful for path '{path}'.")
        return valid


# --- Esports Handler (Instantiated with specific game code) ---
class EsportsSportHandler(SportHandler):
    """Handler for Esports (CS:GO, LoL, Valorant, etc.)."""
    def __init__(self, league: str): # league is specific game code e.g., 'csgo'
        self.league = league.lower()
        logger.debug(f"EsportsSportHandler initialized for league: '{self.league}'")

    def get_sub_league_options(self) -> List[SelectOption]: return [] # Selection happens before handler creation

    def get_path_options(self) -> List[Dict[str, str]]:
        return [
            {"label": "Bet on a Player", "custom_id": "path_player"},
            {"label": "Bet on a Match", "custom_id": "path_match"}
        ]

    def get_modal(self, view: 'BetWorkflowView', path: str) -> Modal:
        logger.debug(f"EsportsSportHandler ({self.league}) getting modal for path: '{path}'")
        from bot.services.bet_service import EsportsPlayerBetModal, EsportsMatchBetModal
        title_league = self.league.upper() # Specific game (CSGO, LOL)
        if path == "Bet on a Player": return EsportsPlayerBetModal(view, title=f"Enter {title_league} Player Bet")
        elif path == "Bet on a Match": return EsportsMatchBetModal(view, title=f"Enter {title_league} Match Bet")
        logger.error(f"Invalid path requested in EsportsSportHandler ({self.league}): {path}")
        raise ValueError(f"Invalid path for Esports ({self.league}): {path}")

    async def build_preview_data(self, view: 'BetWorkflowView') -> Dict[str, Any]:
        data = view.current_leg_data
        path = view.path
        logger.debug(f"EsportsSportHandler ({self.league}) building preview data for path '{path}': {data}")
        # Use specific game code (self.league) for logos
        league_logo_url = DEFAULT_AVATAR_URL
        team1_logo_url = DEFAULT_AVATAR_URL # For primary entity
        team2_logo_url = DEFAULT_AVATAR_URL # For opponent if match bet
        try:
            # Fetch logo for the specific game (league)
            _, league_logo_url_fetched = await get_team_logo_url_from_csv(self.league, None)
            if league_logo_url_fetched: league_logo_url = league_logo_url_fetched
            else: logger.warning(f"Esports ({self.league}): Did not get league logo URL.")

            # Fetch team logos based on path
            team1_input = data.get('team') or data.get('team1') # Player's team or Team 1
            if team1_input:
                team1_logo_url_fetched, _ = await get_team_logo_url_from_csv(self.league, team1_input) # Use game code context
                if team1_logo_url_fetched: team1_logo_url = team1_logo_url_fetched
                else: logger.warning(f"Esports ({self.league}): Did not get logo for primary team '{team1_input}'.")

            if path == "Bet on a Match":
                team2_input = data.get('team2')
                if team2_input:
                     team2_logo_url_fetched, _ = await get_team_logo_url_from_csv(self.league, team2_input)
                     if team2_logo_url_fetched: team2_logo_url = team2_logo_url_fetched
                     else: logger.warning(f"Esports ({self.league}): Did not get logo for opponent team '{team2_input}'.")

        except Exception as e: logger.error(f"Error fetching {self.league} logos: {e}", exc_info=True)

        logger.debug(f"EsportsSportHandler ({self.league}) Logo URLs - League: '{league_logo_url}', Team1: '{team1_logo_url}', Team2: '{team2_logo_url}'")
        description = "Esports Bet details missing."

        primary_team_logo = team1_logo_url # Use team1/player's team logo

        if path == "Bet on a Player":
            player = data.get('player', 'N/A')
            team = data.get('team', 'N/A') # Player's team
            prop = data.get('prop', 'N/A')
            odds = data.get('odds', 'N/A')
            description = f"**Player:** {player} ({team})\n**Prop:** {prop}\n**Odds:** {odds}"
        elif path == "Bet on a Match":
            team1 = data.get('team1', 'N/A')
            team2 = data.get('team2', 'N/A')
            line = data.get('line', 'N/A') # The pick
            odds = data.get('odds', 'N/A')
            description = f"**Match:** {team1} vs {team2}\n**Pick:** {line}\n**Odds:** {odds}"

        preview = {
            'team_logo_url': primary_team_logo,
            'league_logo_url': league_logo_url,
            'description': description,
             # Pass team names if needed elsewhere
            'team_display': data.get('team') or data.get('team1'),
            'opponent_display': data.get('team2'),
        }
        logger.debug(f"EsportsSportHandler ({self.league}) returning preview data: {preview}")
        return preview

    async def validate_data(self, data: Dict[str, Any]) -> bool:
        path = data.get('path')
        logger.debug(f"EsportsSportHandler ({self.league}) validating data for path '{path}': {data}")
        if path == "Bet on a Player": req = ['player', 'team', 'prop', 'odds']
        elif path == "Bet on a Match": req = ['team1', 'team2', 'line', 'odds']
        else: logger.warning(f"Validation failed: Unknown path '{path}'"); return False
        valid = all(data.get(k) and isinstance(data.get(k), str) and data.get(k).strip() for k in req)
        if not valid: logger.warning(f"Validation failed for path '{path}' in league '{self.league}'. Missing/invalid fields: {[k for k in req if not (data.get(k) and isinstance(data.get(k), str) and data.get(k).strip())]}")
        else: logger.debug(f"Validation successful for path '{path}'.")
        return valid

# --- UFC Handler (Unchanged) ---
class UFCSportHandler(SportHandler):
    # ... (Keep existing definition) ...
    def __init__(self):
        self.league = "ufc" # Fixed league code
        logger.debug("UFCSportHandler initialized.")

    def get_sub_league_options(self) -> List[SelectOption]: return []
    def get_path_options(self) -> List[Dict[str, str]]:
        return [
            {"label": "Bet on a Fighter Prop", "custom_id": "path_fighter_prop"},
            {"label": "Bet on a Fight", "custom_id": "path_fight"}
        ]
    def get_modal(self, view: 'BetWorkflowView', path: str) -> Modal:
        logger.debug(f"UFCSportHandler getting modal for path: '{path}'")
        from bot.services.bet_service import UFCFighterBetModal, UFCFightBetModal
        if path == "Bet on a Fighter Prop": return UFCFighterBetModal(view)
        elif path == "Bet on a Fight": return UFCFightBetModal(view)
        logger.error(f"Invalid path requested in UFCSportHandler: {path}")
        raise ValueError(f"Invalid path for UFC: {path}")

    async def build_preview_data(self, view: 'BetWorkflowView') -> Dict[str, Any]:
        data = view.current_leg_data
        path = view.path
        logger.debug(f"UFCSportHandler building preview data for path '{path}': {data}")
        league_logo_url = DEFAULT_AVATAR_URL
        fighter1_logo_url = DEFAULT_AVATAR_URL # Default fighter pic
        try:
            _, league_logo_url_fetched = await get_team_logo_url_from_csv(self.league, None)
            if league_logo_url_fetched: league_logo_url = league_logo_url_fetched
            else: logger.warning(f"UFCSportHandler: Did not get league logo URL.")

            # Try fetching fighter logo if available
            fighter1_name = data.get('fighter') or data.get('fighter1')
            if fighter1_name:
                 fighter1_logo_url_fetched, _ = await get_team_logo_url_from_csv(self.league, fighter1_name) # Assume fighter name might be key
                 if fighter1_logo_url_fetched: fighter1_logo_url = fighter1_logo_url_fetched
                 else: logger.debug(f"No specific logo found for fighter '{fighter1_name}'.")

        except Exception as e: logger.error(f"Error fetching {self.league} logos: {e}", exc_info=True)

        logger.debug(f"UFCSportHandler Logo URLs - League: '{league_logo_url}', Fighter1: '{fighter1_logo_url}'")
        description = "UFC Bet details missing."

        primary_logo = fighter1_logo_url # Use fighter pic if found, else default

        if path == "Bet on a Fighter Prop":
            fighter = data.get('fighter', 'N/A')
            opponent = data.get('opponent', 'N/A')
            prop = data.get('prop', 'N/A')
            odds = data.get('odds', 'N/A')
            description = f"**Fight:** {fighter} vs {opponent}\n**Fighter Prop:** {prop}\n**Odds:** {odds}"
        elif path == "Bet on a Fight":
            fighter1 = data.get('fighter1', 'N/A')
            fighter2 = data.get('fighter2', 'N/A')
            line = data.get('line', 'N/A') # The pick
            odds = data.get('odds', 'N/A')
            description = f"**Fight:** {fighter1} vs {fighter2}\n**Pick:** {line}\n**Odds:** {odds}"

        preview = {
            'team_logo_url': primary_logo, # Use fighter pic here if available
            'league_logo_url': league_logo_url,
            'description': description,
        }
        logger.debug(f"UFCSportHandler returning preview data: {preview}")
        return preview

    async def validate_data(self, data: Dict[str, Any]) -> bool:
        path = data.get('path')
        logger.debug(f"UFCSportHandler validating data for path '{path}': {data}")
        if path == "Bet on a Fighter Prop": req = ['fighter', 'opponent', 'prop', 'odds']
        elif path == "Bet on a Fight": req = ['fighter1', 'fighter2', 'line', 'odds']
        else: logger.warning(f"Validation failed: Unknown path '{path}'"); return False
        valid = all(data.get(k) and isinstance(data.get(k), str) and data.get(k).strip() for k in req)
        if not valid: logger.warning(f"Validation failed for path '{path}'. Missing/invalid fields: {[k for k in req if not (data.get(k) and isinstance(data.get(k), str) and data.get(k).strip())]}")
        else: logger.debug(f"Validation successful for path '{path}'.")
        return valid

# --- Horse Racing Handler (Instantiated with specific race/event code) ---
class HorseRacingSportHandler(SportHandler):
    """Handler for Horse Racing (e.g., Kentucky Derby)."""
    def __init__(self, league: str): # league is specific race code e.g., 'kentucky_derby'
        self.league = league.lower()
        logger.debug(f"HorseRacingSportHandler initialized for league/race: '{self.league}'")

    def get_sub_league_options(self) -> List[SelectOption]: return [] # Selection happens before handler creation

    def get_path_options(self) -> List[Dict[str, str]]:
        return [
            {"label": "Bet on a Horse", "custom_id": "path_horse"},
            {"label": "Bet on a Race Prop", "custom_id": "path_race_prop"}
        ]

    def get_modal(self, view: 'BetWorkflowView', path: str) -> Modal:
        logger.debug(f"HorseRacingSportHandler ({self.league}) getting modal for path: '{path}'")
        from bot.services.bet_service import HorseBetModal, HorseRaceBetModal
        # Format title nicely (e.g., Kentucky_Derby -> Kentucky Derby)
        title_league = self.league.replace("_", " ").title()
        if path == "Bet on a Horse": return HorseBetModal(view, title=f"Enter {title_league} Horse Bet")
        elif path == "Bet on a Race Prop": return HorseRaceBetModal(view, title=f"Enter {title_league} Race Prop")
        logger.error(f"Invalid path requested in HorseRacingSportHandler ({self.league}): {path}")
        raise ValueError(f"Invalid path for Horse Racing ({self.league}): {path}")

    async def build_preview_data(self, view: 'BetWorkflowView') -> Dict[str, Any]:
        data = view.current_leg_data
        path = view.path
        logger.debug(f"HorseRacingSportHandler ({self.league}) building preview data for path '{path}': {data}")
        league_logo_url = DEFAULT_AVATAR_URL # Logo for the specific race/event
        horse_logo_url = DEFAULT_AVATAR_URL # Default for horse image/silks
        try:
            # Fetch logo for the specific race (using self.league as key)
            _, league_logo_url_fetched = await get_team_logo_url_from_csv(self.league, None)
            if league_logo_url_fetched: league_logo_url = league_logo_url_fetched
            else: logger.warning(f"HorseRacing ({self.league}): Did not get league/race logo URL.")

            # Fetch horse logo if applicable
            if path == "Bet on a Horse":
                 horse_name = data.get('horse')
                 if horse_name:
                      # Use self.league (race context) and horse name to find logo
                      horse_logo_url_fetched, _ = await get_team_logo_url_from_csv(self.league, horse_name)
                      if horse_logo_url_fetched: horse_logo_url = horse_logo_url_fetched
                      else: logger.debug(f"HorseRacing ({self.league}): No specific logo found for horse '{horse_name}'.")

        except Exception as e: logger.error(f"Error fetching {self.league} logos: {e}", exc_info=True)

        logger.debug(f"HorseRacing ({self.league}) Logo URLs - League: '{league_logo_url}', Horse: '{horse_logo_url}'")
        description = "Horse Racing Bet details missing."

        # Use horse logo if betting on a horse, else None for primary image
        primary_logo = horse_logo_url if path == "Bet on a Horse" else None

        if path == "Bet on a Horse":
            horse = data.get('horse', 'N/A')
            line = data.get('line', 'N/A') # Pick: Win/Place/Show etc.
            odds = data.get('odds', 'N/A')
            description = f"**Horse:** {horse}\n**Pick:** {line}\n**Odds:** {odds}"
        elif path == "Bet on a Race Prop":
            event = data.get('event', 'N/A') # Prop description from Modal
            outcome = data.get('outcome', 'N/A') # Condition/Description from Modal? Rename modal field maybe?
            pick = data.get('pick', 'N/A') # User's Pick from Modal
            odds = data.get('odds', 'N/A')
            # Clarify description based on modal fields
            description = f"**Race Prop:** {event} - {outcome}\n**Pick:** {pick}\n**Odds:** {odds}"


        preview = {
            'team_logo_url': primary_logo, # Use horse logo here if available and relevant
            'league_logo_url': league_logo_url, # Race/Event logo
            'description': description,
        }
        logger.debug(f"HorseRacingSportHandler ({self.league}) returning preview data: {preview}")
        return preview

    async def validate_data(self, data: Dict[str, Any]) -> bool:
        path = data.get('path')
        logger.debug(f"HorseRacingSportHandler ({self.league}) validating data for path '{path}': {data}")
        if path == "Bet on a Horse": req = ['horse', 'line', 'odds']
        elif path == "Bet on a Race Prop": req = ['event', 'outcome', 'pick', 'odds'] # Match modal fields
        else: logger.warning(f"Validation failed: Unknown path '{path}'"); return False
        valid = all(data.get(k) and isinstance(data.get(k), str) and data.get(k).strip() for k in req)
        if not valid: logger.warning(f"Validation failed for path '{path}' in league '{self.league}'. Missing/invalid fields: {[k for k in req if not (data.get(k) and isinstance(data.get(k), str) and data.get(k).strip())]}")
        else: logger.debug(f"Validation successful for path '{path}'.")
        return valid


# --- SportHandlerFactory ---
class SportHandlerFactory:
    """Factory to select the appropriate sport handler based on the specific league/sub-league code."""

    # Define mappings from specific league codes to their handler classes
    HANDLER_MAP = {
        # Team Sports -> TeamSportHandler
        'nfl': TeamSportHandler, 'nba': TeamSportHandler, 'mlb': TeamSportHandler, 'nhl': TeamSportHandler,
        'epl': TeamSportHandler, 'laliga': TeamSportHandler, 'seriea': TeamSportHandler,
        'bundesliga': TeamSportHandler, 'ligue1': TeamSportHandler, 'mls': TeamSportHandler,
        'wnba': TeamSportHandler, 'cfl': TeamSportHandler,

        # NCAA Sub-Leagues -> NCAASportHandler
        'ncaaf': NCAASportHandler, 'ncaam': NCAASportHandler, 'ncaaw': NCAASportHandler, 'ncaawvb': NCAASportHandler,

        # NASCAR -> NASCARSportHandler
        'nascar': NASCARSportHandler,

        # Golf Sub-Leagues -> GolfSportHandler
        'pga': GolfSportHandler, 'lpga': GolfSportHandler, 'europeantour': GolfSportHandler, 'masters': GolfSportHandler,

        # Tennis Sub-Leagues -> TennisSportHandler
        'atp': TennisSportHandler, 'wta': TennisSportHandler,

        # Esports Sub-Leagues -> EsportsSportHandler
        'csgo': EsportsSportHandler, 'lol': EsportsSportHandler, 'valorant': EsportsSportHandler,
        'esports_players': EsportsSportHandler, # Generic player handler if needed

        # Combat Sports -> UFCSportHandler
        'ufc': UFCSportHandler,

        # Horse Racing Sub-Leagues -> HorseRacingSportHandler
        'kentucky_derby': HorseRacingSportHandler,
        # Add other specific races mapped to HorseRacingSportHandler
        # 'preakness_stakes': HorseRacingSportHandler,
        # 'belmont_stakes': HorseRacingSportHandler,
        # 'horseracing': HorseRacingSportHandler, # Generic handler if needed?
    }

    @staticmethod
    def get_handler(league_code: str, supported_leagues: List[str]) -> SportHandler:
        """
        Gets the appropriate handler based on the specific league code.
        Expects league_code to be the final, specific code (e.g., 'ncaaf', 'atp', 'csgo').
        """
        # Normalize the input code (lowercase, strip)
        normalized_code = league_code.lower().strip()
        logger.info(f"SportHandlerFactory: Requested handler for specific code '{normalized_code}'")

        # Check if the code exists in the definitive SUPPORTED_LEAGUES list
        # This check might be redundant if bet_service already validates, but good safeguard
        if normalized_code not in supported_leagues:
             logger.error(f"Attempted to get handler for unsupported league code: '{normalized_code}' (Not in SUPPORTED_LEAGUES)")
             raise ValueError(f"League code '{normalized_code}' is not listed as supported.")

        # Lookup the handler class in the map
        handler_class = SportHandlerFactory.HANDLER_MAP.get(normalized_code)

        if handler_class:
            logger.debug(f"Handler found for '{normalized_code}': {handler_class.__name__}")
            # Instantiate the handler with the specific league code
            return handler_class(normalized_code)
        else:
            # Fallback or Error Handling
            # Should ideally not happen if HANDLER_MAP covers all SUPPORTED_LEAGUES
            logger.error(f"No specific handler defined in HANDLER_MAP for supported league code: '{normalized_code}'")
            # Option 1: Fallback to generic TeamSportHandler? (Might be incorrect)
            # logger.warning(f"Falling back to TeamSportHandler for unmapped code: '{normalized_code}'")
            # return TeamSportHandler(normalized_code)
            # Option 2: Raise error
            raise ValueError(f"Handler configuration error: No handler mapped for supported league code '{normalized_code}'")
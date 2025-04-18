# bot/services/bet_service.py
# ADDED member_role fetching and mention logic in ConfirmButton callback.
# ADDED member_role_id to bets table insert.

import asyncio
import logging
import discord
import aiomysql
from discord import app_commands, Interaction, SelectOption, TextStyle
from discord.ui import View, Select, Button, Modal, TextInput
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, TYPE_CHECKING

# Assuming db_manager and other necessary imports are available
from bot.data.db_manager import db_manager
from bot.data.cache_manager import cache_manager
from bot.data.league.league_team_handler import standardize_league_code
from bot.utils.serial_utils import generate_bet_serial
from bot.utils.validation import is_valid_league, is_valid_units
from bot.utils.errors import ValidationError, PermissionError, DatabaseError, BettingBotError
from bot.utils.rate_limiter import limit_discord_call
from bot.utils.image_utils.team_logos import get_team_logo_url_from_csv
from bot.data.league.league_dictionaries import SUPPORTED_LEAGUES
from bot.config.settings import TEST_GUILD_ID, DEFAULT_AVATAR_URL, LOGO_BASE_URL
from bot.services.sport_handler import SportHandlerFactory, SportHandler
# Make sure cancel_bet_handler exists and is importable
from bot.services.cancel_bet_handler import cancel_bet_command_handler
from bot.utils.buttons import CancelButton # Ensure this import is correct
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# --- LEAGUE EXAMPLES ---
LEAGUE_EXAMPLES = {
    "nba": {"team": "Lakers", "opponent": "Celtics", "player": "LeBron James"},
    "nfl": {"team": "Chiefs", "opponent": "Eagles", "player": "Patrick Mahomes"},
    "mlb": {"team": "Yankees", "opponent": "Dodgers", "player": "Aaron Judge"},
    "nhl": {"team": "Maple Leafs", "opponent": "Bruins", "player": "Auston Matthews"},
    "epl": {"team": "Manchester United", "opponent": "Liverpool", "player": "Erling Haaland"},
    "laliga": {"team": "Real Madrid", "opponent": "Barcelona", "player": "Vinicius Jr."},
    "seriea": {"team": "Juventus", "opponent": "Inter Milan", "player": "Lautaro Martinez"},
    "bundesliga": {"team": "Bayern Munich", "opponent": "Dortmund", "player": "Harry Kane"},
    "ligue1": {"team": "PSG", "opponent": "Monaco", "player": "Kylian Mbappe"},
    "mls": {"team": "Inter Miami", "opponent": "LA Galaxy", "player": "Lionel Messi"},
    "wnba": {"team": "Las Vegas Aces", "opponent": "New York Liberty", "player": "A’ja Wilson"},
    "cfl": {"team": "BC Lions", "opponent": "Winnipeg Blue Bombers", "player": "Zach Collaros"},
    "nascar": {"driver": "Kyle Larson", "car_number": "5", "event": "Daytona 500"},
    "ufc": {"fighter": "Jon Jones", "opponent": "Alex Pereira", "prop": "KO/TKO"},
    "ncaaf": {"team": "Alabama", "opponent": "Georgia", "player": "Jalen Milroe"},
    "ncaam": {"team": "Duke", "opponent": "Kansas", "player": "Cooper Flagg"},
    "ncaaw": {"team": "UConn", "opponent": "South Carolina", "player": "Paige Bueckers"},
    "ncaawvb": {"team": "Nebraska", "opponent": "Stanford", "player": "Lexi Rodriguez"},
    "pga": {"golfer": "Scottie Scheffler", "event": "The Masters"},
    "lpga": {"golfer": "Nelly Korda", "event": "U.S. Women’s Open"},
    "europeantour": {"golfer": "Rory McIlroy", "event": "DP World Tour"},
    "masters": {"golfer": "Jon Rahm", "event": "The Masters"},
    "atp": {"player": "Carlos Alcaraz", "opponent": "Novak Djokovic"},
    "wta": {"player": "Iga Swiatek", "opponent": "Coco Gauff"},
    "csgo": {"team": "Team Spirit", "opponent": "FaZe Clan", "player": "sh1ro"},
    "lol": {"team": "T1", "opponent": "G2 Esports", "player": "Faker"},
    "valorant": {"team": "Sentinels", "opponent": "Fnatic", "player": "TenZ"},
    "esports_players": {"player": "s1mple", "team": "Natus Vincere"},
    "kentucky_derby": {"horse": "Flightline", "event": "Kentucky Derby"},
    "horseracing": {"horse": "White Abarrio", "event": "Breeders’ Cup"}
    }

# --- Helper Functions ---

def create_league_select_options() -> List[SelectOption]:
    """Creates SelectOption list for league selection, including only top-level leagues."""
    options = []
    top_level_leagues = [
        "NBA", "NFL", "MLB", "NHL", "EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1",
        "MLS", "WNBA", "CFL", "NASCAR", "UFC",
        "NCAA", "Golf", "Tennis", "Esports", "HorseRacing"
    ]
    code_map = {
        "laliga": "laliga", "seriea": "seriea", "bundesliga": "bundesliga", "ligue1": "ligue1",
        "golf": "golf", "tennis": "tennis", "esports": "esports", "horseracing": "horseracing",
        "ncaa": "ncaa", "ufc": "ufc", "nascar": "nascar", "nba": "nba", "nfl": "nfl",
        "mlb": "mlb", "nhl": "nhl", "epl": "epl", "mls": "mls", "wnba": "wnba", "cfl": "cfl"
    }
    for league_display in top_level_leagues:
        league_code = code_map.get(league_display.lower(), league_display.lower())
        if league_code in SUPPORTED_LEAGUES:
            options.append(SelectOption(label=league_display.upper(), value=league_code))
        else:
            logger.warning(f"Skipping league '{league_display}' in options: Code '{league_code}' not found in SUPPORTED_LEAGUES.")
    if not options:
        logger.error("No valid top-level league options generated.")
        return []
    return options

def to_int_or_none(val):
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

async def fetch_guild_settings_and_sub(guild_id: int) -> dict:
    """Fetches key guild settings including channels and roles."""
    # ADDED member_role to the list of columns
    columns = ['command_channel_1', 'command_channel_2', 'embed_channel_1', 'embed_channel_2', 'authorized_role', 'admin_role', 'member_role']
    default_settings = {col: None for col in columns}
    try:
        query = f"SELECT {', '.join(columns)} FROM server_settings WHERE guild_id = %s"
        settings_record = await db_manager.fetch_one(query, (guild_id,))
        if settings_record:
            # Convert fetched IDs to int, keeping None if originally None or conversion fails
            converted_settings = {col: to_int_or_none(settings_record.get(col)) for col in columns}
            final_settings = {**default_settings, **converted_settings}
            logger.debug(f"Fetched settings for guild {guild_id}: {final_settings}")
            return final_settings
        else:
            logger.debug(f"No settings found for guild {guild_id}.")
            return default_settings
    except DatabaseError as e:
        logger.error(f"DB error fetching settings for guild {guild_id}: {e}")
        return default_settings
    except Exception as e:
        logger.error(f"Unexpected error fetching settings for guild {guild_id}: {e}", exc_info=True)
        return default_settings


# --- BetWorkflowView Class and other UI Components ---
# (Includes BetWorkflowView, SubLeague Selects, LeagueSelect, BetTypeSelect, PathButton, ChannelSelect, UnitsSelect, Modals, Confirm/Edit/Cancel Buttons)

class BetWorkflowView(View):
    selected_league: Optional[str] = None
    selected_sub_league: Optional[str] = None
    bet_type: Optional[str] = None
    path: Optional[str] = None
    legs: List[Dict[str, Any]] = []
    current_leg_data: Dict[str, Any] = {}
    preview_embed: Optional[discord.Embed] = None
    selected_channel_id: Optional[int] = None
    selected_units: Optional[int] = None
    original_interaction: Interaction
    bet_serial: int
    bet_service: 'BetService' # Forward reference for type hint
    embed_channel_id_1: Optional[int] = None
    embed_channel_id_2: Optional[int] = None
    sport_handler: Optional[SportHandler] = None

    def __init__(self, interaction: Interaction, bet_service: 'BetService', embed_ch_id_1: Optional[int], embed_ch_id_2: Optional[int], timeout=300):
        super().__init__(timeout=timeout)
        self.original_interaction = interaction
        self.bet_service = bet_service
        self.embed_channel_id_1 = embed_ch_id_1
        self.embed_channel_id_2 = embed_ch_id_2
        self.legs = []
        self.current_leg_data = {}
        self.bet_serial = generate_bet_serial()
        logger.debug(f"BetWorkflowView initialized (Serial: {self.bet_serial}) Embed Channels: {embed_ch_id_1}, {embed_ch_id_2}")
        self.update_view()

    async def on_timeout(self):
        logger.info(f"Bet setup timed out for bet serial {self.bet_serial} (User: {self.original_interaction.user.id})")
        if self.is_finished():
            return
        self.stop()
        try:
            await self.original_interaction.edit_original_response(content="*Bet setup timed out.*", view=None, embed=None)
        except discord.NotFound:
            logger.warning(f"Original interaction message not found on timeout for bet {self.bet_serial}.")
        except discord.HTTPException as e:
            logger.error(f"HTTPException editing message on timeout for bet {self.bet_serial}: {e}")
        except Exception as e:
            logger.error(f"Error editing message on timeout for bet {self.bet_serial}: {e}", exc_info=True)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message("This isn't your bet setup!", ephemeral=True)
            return False
        if self.is_finished():
            # Prevent further interactions if view is stopped (e.g., after confirmation/cancellation/timeout)
            if not interaction.response.is_done():
                 await interaction.response.send_message("This bet setup has finished.", ephemeral=True)
            return False
        return True

    def update_view(self):
        logger.debug(f"Updating view state for bet {self.bet_serial}: L={self.selected_league}, SL={self.selected_sub_league}, T={self.bet_type}, P={self.path}, Chan={self.selected_channel_id}, Units={self.selected_units}, Preview={self.preview_embed is not None}")
        self.clear_items()
        current_league_context = self.selected_sub_league or self.selected_league
        logger.debug(f"View Update: current_league_context = {current_league_context}")

        # State 1: No league selected
        if self.selected_league is None:
            opts = create_league_select_options()
            if opts:
                self.add_item(LeagueSelect(opts))
            else:
                # Handle error: No leagues available
                self.add_item(Button(label="Error: No Leagues Configured", style=discord.ButtonStyle.danger, disabled=True))

        # State 1b: League selected, requires sub-league
        elif self.selected_league in ["ncaa", "golf", "tennis", "esports", "horseracing"] and self.selected_sub_league is None:
            logger.debug(f"View Update: Adding sub-league select for {self.selected_league}")
            # Add appropriate sub-league selector
            if self.selected_league == "ncaa": self.add_item(SubLeagueSelect())
            elif self.selected_league == "esports": self.add_item(EsportsSubLeagueSelect())
            elif self.selected_league == "tennis": self.add_item(TennisSubLeagueSelect())
            elif self.selected_league == "golf": self.add_item(GolfSubLeagueSelect())
            elif self.selected_league == "horseracing": self.add_item(HorseRacingSubLeagueSelect())
            else: logger.error(f"No sub-league selector defined for generic league: {self.selected_league}")

        # State 2: League context decided, need bet type
        elif self.bet_type is None and current_league_context:
            logger.debug(f"View Update: Getting handler for {current_league_context}")
            try:
                # Ensure handler is obtained before adding BetTypeSelect
                self.sport_handler = SportHandlerFactory.get_handler(current_league_context, SUPPORTED_LEAGUES)
                logger.debug(f"View Update: Handler acquired: {type(self.sport_handler).__name__}")
                self.add_item(BetTypeSelect()) # Now add the select
            except ValueError as e:
                 logger.error(f"Could not find a SportHandler for league: {current_league_context}. Error: {e}")
                 self.add_item(Button(label=f"Error: Handler not found", style=discord.ButtonStyle.danger, disabled=True))
            except Exception as e:
                 logger.error(f"Error getting handler for '{current_league_context}' in State 2: {e}", exc_info=True)
                 self.add_item(Button(label="Error: Handler Issue", style=discord.ButtonStyle.danger, disabled=True))

        # State 3: Bet type selected, need path
        elif self.path is None and self.sport_handler:
            logger.debug(f"View Update: Adding path buttons from handler {type(self.sport_handler).__name__}")
            path_options = self.sport_handler.get_path_options()
            if not path_options:
                 logger.error(f"No path options returned by handler for league: {current_league_context}")
                 self.add_item(Button(label="Error: No bet paths available", style=discord.ButtonStyle.danger, disabled=True))
            else:
                 for option in path_options:
                     self.add_item(PathButton(option["label"], option["custom_id"]))

        # State 4: Path selected, Modal expected/submitted, waiting for preview
        elif self.path is not None and self.preview_embed is None:
             # Usually means modal interaction is pending or just happened
             logger.debug(f"View update skipped: Modal expected or just submitted for path '{self.path}'")
             pass # Don't add items here, wait for modal submission to call show_preview

        # State 5: Preview shown, need channel/units
        elif self.preview_embed is not None:
            logger.debug(f"View Update: Adding ChannelSelect, UnitsSelect, ConfirmButton, EditButton, CancelButton")
            # Row 0: ChannelSelect
            chan_select = ChannelSelect(self.original_interaction.guild, self.embed_channel_id_1, self.embed_channel_id_2)
            chan_select.row = 0
            # Pre-select if already chosen
            if self.selected_channel_id:
                for o in chan_select.options:
                    if o.value.isdigit() and int(o.value) == self.selected_channel_id:
                        o.default = True
                        break
            self.add_item(chan_select)

            # Row 1: UnitsSelect
            unit_select = UnitsSelect()
            unit_select.row = 1
            # Pre-select if already chosen
            if self.selected_units:
                for o in unit_select.options:
                    if o.value.isdigit() and int(o.value) == self.selected_units:
                        o.default = True
                        break
            self.add_item(unit_select)

            # Row 2: Buttons
            confirm_enabled = bool(self.selected_channel_id and self.selected_units)
            logger.debug(f"Confirm button enabled={confirm_enabled}: Chan={self.selected_channel_id}, Units={self.selected_units}")
            self.add_item(ConfirmButton(disabled=not confirm_enabled, row=2))
            self.add_item(EditButton(row=2))
            self.add_item(CancelButton(row=2)) # Use imported CancelButton

        # Fallback for unexpected state
        else:
            logger.warning(f"BetWorkflowView unexpected state for bet {self.bet_serial}.")
            self.add_item(Button(label="Error: Unexpected State", style=discord.ButtonStyle.danger, disabled=True))

        logger.debug(f"View updated with {len(self.children)} components for bet {self.bet_serial}.")


    async def show_preview(self):
        interaction = self.original_interaction # Use the initial interaction for editing
        logger.info(f"Generating preview for bet serial {self.bet_serial}. Current leg data: {self.current_leg_data}")

        # Ensure sport handler is available (might need re-acquisition if view state was lost/rebuilt)
        if not self.sport_handler:
            logger.error(f"Preview error for bet {self.bet_serial}: Sport handler is not set!")
            league_context = self.selected_sub_league or self.selected_league
            if league_context:
                try:
                    self.sport_handler = SportHandlerFactory.get_handler(league_context, SUPPORTED_LEAGUES)
                    logger.info(f"Re-acquired sport handler: {type(self.sport_handler).__name__} for {league_context}")
                except Exception as e:
                    logger.error(f"Failed to re-acquire handler for {league_context}: {e}")
            if not self.sport_handler: # If still no handler
                 await interaction.edit_original_response(content="Error: Critical state error (handler lost). Please restart.", view=None, embed=None)
                 self.stop()
                 return

        # Validate data using the handler
        try:
             self.current_leg_data['path'] = self.path # Ensure path is in data for validation context
             is_valid = await self.sport_handler.validate_data(self.current_leg_data)
             if not is_valid:
                 logger.error(f"Invalid bet data entered for bet {self.bet_serial}: {self.current_leg_data}")
                 self.preview_embed = None # Clear potential old preview
                 # Don't update view here, let the edit message handle components
                 edit_message = "Error: Invalid or missing bet details entered. Please use the 'Edit Bet' button to try again."
                 # Make sure Edit button is available
                 if not discord.utils.get(self.children, custom_id="edit_bet"):
                      self.add_item(EditButton(row=2)) # Add it if missing
                 await interaction.edit_original_response(content=edit_message, view=self, embed=None)
                 return # Stop processing, user needs to edit
        except Exception as val_err:
             logger.error(f"Error during data validation via handler for bet {self.bet_serial}: {val_err}", exc_info=True)
             await interaction.edit_original_response(content="Error validating bet details. Please restart.", view=None, embed=None)
             self.stop()
             return

        # Build preview data using the handler
        try:
            logger.debug(f"Calling sport_handler.build_preview_data for bet {self.bet_serial}...")
            preview_data = await self.sport_handler.build_preview_data(self) # Pass self (view)
            logger.info(f"Preview data received from handler for bet {self.bet_serial}: {preview_data}")
        except Exception as e:
            logger.error(f"Error building preview data via handler for bet {self.bet_serial}: {e}", exc_info=True)
            await interaction.edit_original_response(content="Error generating preview details. Please restart.", view=None, embed=None)
            self.stop()
            return

        # Create Embed
        league_display = self.selected_sub_league or self.selected_league or "Unknown League"
        title = f"{league_display.upper()} Bet Preview"
        if self.bet_type == "Straight": title = f"{league_display.upper()} - Straight Bet"
        embed = discord.Embed(title=title, description=preview_data.get('description', 'Bet details missing.'), color=discord.Color.blue())

        # Set Logos (using helper function)
        primary_entity_name = preview_data.get('team_display') # Handler should provide primary name
        try:
             team_logo_url, league_logo_url = await get_team_logo_url_from_csv(league_display.lower(), primary_entity_name)
             logger.info(f"Preview {self.bet_serial}: Fetched Logos - Team='{team_logo_url}', League='{league_logo_url}' for League='{league_display}', Entity='{primary_entity_name}'")

             # Prefer handler's specific URLs if provided, otherwise use fetched ones
             main_image_url = preview_data.get('team_logo_url', team_logo_url or DEFAULT_AVATAR_URL)
             thumb_url = preview_data.get('league_logo_url', league_logo_url or DEFAULT_AVATAR_URL)

             if main_image_url and isinstance(main_image_url, str) and main_image_url.lower().startswith(('http://', 'https://')):
                  logger.debug(f"Preview {self.bet_serial}: Setting image to '{main_image_url}'")
                  embed.set_image(url=main_image_url)
             elif main_image_url: logger.warning(f"Preview {self.bet_serial}: Invalid primary image URL received/fetched: '{main_image_url}'.")
             else: logger.debug(f"Preview {self.bet_serial}: No primary image URL provided or found.")

             if thumb_url and isinstance(thumb_url, str) and thumb_url.lower().startswith(('http://', 'https://')):
                 logger.debug(f"Preview {self.bet_serial}: Setting thumbnail to '{thumb_url}'")
                 embed.set_thumbnail(url=thumb_url)
             elif thumb_url: logger.warning(f"Preview {self.bet_serial}: Invalid league logo URL received/fetched: '{thumb_url}'.")
             else: logger.debug(f"Preview {self.bet_serial}: No league logo URL provided or found.")

        except Exception as logo_err:
            logger.error(f"Error fetching logos for preview {self.bet_serial}: {logo_err}", exc_info=True)
            # Use defaults if fetch fails
            if preview_data.get('team_logo_url', '').startswith('http'): embed.set_image(url=preview_data['team_logo_url'])
            else: embed.set_image(url=DEFAULT_AVATAR_URL)
            if preview_data.get('league_logo_url', '').startswith('http'): embed.set_thumbnail(url=preview_data['league_logo_url'])
            else: embed.set_thumbnail(url=DEFAULT_AVATAR_URL)


        embed.set_footer(text="Step 5/6: Select Channel and Units")

        # Store the generated embed and update the view to show confirmation options
        self.preview_embed = embed
        self.update_view() # This will add channel/unit selects and buttons

        # Edit the original interaction message
        try:
            await interaction.edit_original_response(content="**Bet Preview:**", embed=self.preview_embed, view=self)
            logger.info(f"Preview shown successfully for bet serial {self.bet_serial}")
        except discord.NotFound:
            logger.error(f"Error showing preview {self.bet_serial}: Original interaction msg not found.")
            self.stop()
        except discord.HTTPException as e:
            logger.error(f"HTTPException editing interaction for preview {self.bet_serial}: {e}")
        except Exception as e:
            logger.error(f"Error editing interaction for preview {self.bet_serial}: {e}", exc_info=True)

    async def update_preview_description_and_footer(self, interaction=None):
        """Updates the description and footer of the preview embed, typically after unit selection."""
        if not self.preview_embed or not self.sport_handler:
            logger.warning(f"Update preview failed {self.bet_serial}: embed/handler missing.")
            return

        logger.debug(f"Updating preview desc/footer {self.bet_serial}: Chan={self.selected_channel_id}, Units={self.selected_units}")

        # Rebuild base description from handler
        try:
            preview_data = await self.sport_handler.build_preview_data(self)
            base_description = preview_data.get('description', 'Bet details missing.')
        except Exception as e:
            logger.error(f"Error rebuilding preview description {self.bet_serial}: {e}", exc_info=True)
            base_description = self.preview_embed.description.split("\n\n**🔒")[0] if self.preview_embed.description else "Bet details missing."

        if self.selected_units is not None:
            odds_raw = self.current_leg_data.get('odds', 'N/A')
            stake_text = ""
            stake_amount = None
            try:
                # Parse odds
                odds = None
                if isinstance(odds_raw, (int, float)):
                    odds = float(odds_raw)
                elif isinstance(odds_raw, str):
                    if odds_raw.upper() == 'EVEN':
                        odds = 100.0
                    else:
                        try:
                            odds = float(odds_raw.replace('+',''))
                        except ValueError:
                            pass

                # Calculate stake based on odds
                if odds is not None:
                    if odds > 0:  # Positive odds: Stake = Risk amount
                        stake_amount = float(self.selected_units)
                        stake_text = f"🔒 TO RISK {stake_amount:.2f} UNITS 🔒"
                    else:  # Negative or even odds: Stake = Win amount
                        abs_odds = abs(odds) if odds != 100.0 else 100.0  # EVEN treated as 100
                        stake_amount = self.selected_units * (abs_odds / 100.0)
                        stake_text = f"🔒 TO WIN {stake_amount:.2f} UNITS 🔒"
                else:  # Invalid or 'N/A' odds
                    stake_amount = float(self.selected_units)  # Default to units risked
                    stake_text = f"🔒 TO RISK {stake_amount:.2f} UNITS 🔒"

                # Store calculated stake
                self.current_leg_data['stake'] = stake_amount
                logger.debug(f"Calculated Stake for bet {self.bet_serial}: {stake_amount} (Units: {self.selected_units}, Odds: {odds_raw})")

            except Exception as e:
                logger.warning(f"Error calculating stake for bet {self.bet_serial} (Odds: '{odds_raw}'): {e}")
                stake_amount = float(self.selected_units)
                stake_text = f"🔒 TO RISK {stake_amount:.2f} UNITS 🔒"
                self.current_leg_data['stake'] = stake_amount

            # Update embed description and footer
            self.preview_embed.description = f"{base_description}\n\n**{stake_text}**"
            self.preview_embed.set_footer(text="Ready to Confirm?")
            logger.debug(f"Preview {self.bet_serial}: Added stake line '{stake_text}', footer='Ready to Confirm?'")
        else:
            self.preview_embed.description = base_description
            self.preview_embed.set_footer(text="Step 5/6: Select Channel and Units")
            logger.debug(f"Preview {self.bet_serial}: Units not selected, footer='Select Channel and Units'")

        # Enable/Disable Confirm button
        confirm_enabled = bool(self.selected_channel_id and self.selected_units)
        logger.debug(f"Updating Confirm button: enabled={confirm_enabled}")
        confirm_button = discord.utils.get(self.children, custom_id="confirm_bet")
        if confirm_button and isinstance(confirm_button, Button):
            confirm_button.disabled = not confirm_enabled
        else:
            logger.warning(f"Could not find ConfirmButton to update for bet {self.bet_serial}")

        # Edit the original interaction message
        try:
            target_interaction = interaction or self.original_interaction
            await target_interaction.edit_original_response(embed=self.preview_embed, view=self)
            logger.debug(f"Updated preview embed {self.bet_serial} with new description/footer/button state.")
        except discord.NotFound:
            logger.error(f"Error updating preview {self.bet_serial}: Original interaction msg not found.")
            self.stop()
        except discord.HTTPException as e:
            logger.error(f"HTTPException updating preview {self.bet_serial}: {e}")
        except Exception as e:
            logger.error(f"Error updating preview {self.bet_serial}: {e}", exc_info=True)

# --- Sub-League Select Classes ---
class EsportsSubLeagueSelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="Counter-Strike (CS:GO)", value="csgo"),
            SelectOption(label="League of Legends (LoL)", value="lol"),
            SelectOption(label="Valorant", value="valorant"),
            SelectOption(label="Generic Esports Players", value="esports_players"), # Keep if needed
        ]
        super().__init__(placeholder="1b. Select Esports Game...", options=options, custom_id="esports_sub_league_select")

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return
        view.selected_sub_league = self.values[0]
        logger.info(f"Esports Sub-League selected: {view.selected_sub_league} by {interaction.user.id} (Serial: {view.bet_serial})")
        view.update_view() # This will now trigger State 2 (BetTypeSelect)
        await interaction.response.edit_message(content="Step 2: Select Bet Type", view=view, embed=None)

class TennisSubLeagueSelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="Men's Tennis (ATP)", value="atp"),
            SelectOption(label="Women's Tennis (WTA)", value="wta"),
        ]
        super().__init__(placeholder="1b. Select Tennis Tour...", options=options, custom_id="tennis_sub_league_select")

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return
        view.selected_sub_league = self.values[0]
        logger.info(f"Tennis Sub-League selected: {view.selected_sub_league} by {interaction.user.id} (Serial: {view.bet_serial})")
        view.update_view()
        await interaction.response.edit_message(content="Step 2: Select Bet Type", view=view, embed=None)

class GolfSubLeagueSelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="PGA Tour", value="pga"),
            SelectOption(label="LPGA Tour", value="lpga"),
            SelectOption(label="European Tour", value="europeantour"),
            SelectOption(label="The Masters", value="masters"), # Example major
        ]
        super().__init__(placeholder="1b. Select Golf Tour/Event...", options=options, custom_id="golf_sub_league_select")

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return
        view.selected_sub_league = self.values[0]
        logger.info(f"Golf Sub-League selected: {view.selected_sub_league} by {interaction.user.id} (Serial: {view.bet_serial})")
        view.update_view()
        await interaction.response.edit_message(content="Step 2: Select Bet Type", view=view, embed=None)

class HorseRacingSubLeagueSelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="Kentucky Derby", value="kentucky_derby"), # Example specific race
            # Add other major races as needed (Preakness, Belmont, Breeders' Cup?)
            SelectOption(label="Other Horse Racing", value="horseracing"), # Generic fallback
        ]
        super().__init__(placeholder="1b. Select Horse Race/Event...", options=options, custom_id="horseracing_sub_league_select")

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return
        view.selected_sub_league = self.values[0]
        logger.info(f"Horse Racing Sub-League selected: {view.selected_sub_league} by {interaction.user.id} (Serial: {view.bet_serial})")
        view.update_view()
        await interaction.response.edit_message(content="Step 2: Select Bet Type", view=view, embed=None)


# --- Standard Component Classes ---
class LeagueSelect(Select):
    def __init__(self, league_options: List[SelectOption]):
        placeholder = "1. Select League/Category..."
        disabled = False
        if not league_options:
            options = [SelectOption(label="No leagues configured", value="error", default=True)]
            placeholder = "Error: No leagues found"
            disabled = True
        else: options = league_options
        super().__init__(placeholder=placeholder, options=options, custom_id="league_select", disabled=disabled)

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return
        selected_value = self.values[0]
        if selected_value == "error":
             await interaction.response.send_message("League selection is currently unavailable.", ephemeral=True)
             return
        # Reset subsequent state
        view.selected_league = selected_value
        view.selected_sub_league = None
        view.bet_type = None
        view.path = None
        view.preview_embed = None
        view.current_leg_data = {}
        view.sport_handler = None # Reset handler
        logger.info(f"League selected: {view.selected_league} by {interaction.user.id} (Serial: {view.bet_serial})")
        generic_parents = ["ncaa", "golf", "tennis", "esports", "horseracing"]
        next_step_message = f"Step 1b: Select {view.selected_league.capitalize()} Sub-Category" if view.selected_league in generic_parents else "Step 2: Select Bet Type"
        view.update_view() # Update view based on selection
        await interaction.response.edit_message(content=next_step_message, view=view, embed=None)

class SubLeagueSelect(Select): # Specifically for NCAA
    def __init__(self):
        placeholder = "1b. Select NCAA Sport..."
        options = [
            SelectOption(label="NCAA Football (NCAAF)", value="ncaaf"),
            SelectOption(label="NCAA Men's Basketball (NCAAM)", value="ncaam"),
            SelectOption(label="NCAA Women's Basketball (NCAAW)", value="ncaaw"),
            SelectOption(label="NCAA Women's Volleyball (NCAAWVB)", value="ncaawvb"),
        ]
        super().__init__(placeholder=placeholder, options=options, custom_id="sub_league_select")

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return
        view.selected_sub_league = self.values[0]
        # Reset subsequent state
        view.bet_type = None
        view.path = None
        view.preview_embed = None
        view.current_leg_data = {}
        view.sport_handler = None # Reset handler
        logger.info(f"NCAA Sub-League selected: {view.selected_sub_league} by {interaction.user.id} (Serial: {view.bet_serial})")
        view.update_view() # Update view based on selection
        await interaction.response.edit_message(content="Step 2: Select Bet Type", view=view, embed=None)


class BetTypeSelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="Straight Bet", value="Straight"),
            SelectOption(label="Parlay", value="Parlay", description="Coming Soon!") # Keep disabled if needed
        ]
        super().__init__(placeholder="2. Select Bet Type...", options=options, custom_id="bet_type_select")

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return
        selected_type = self.values[0]
        if selected_type == "Parlay": # Handle unavailable option
            await interaction.response.send_message("Parlay functionality is not yet available!", ephemeral=True)
            # Do not update view state if option is unavailable
            # Re-edit message to keep current state? Or just let the ephemeral message show.
            # await interaction.edit_original_response(view=view) # Optional: Keep the BetTypeSelect visible
            return
        view.bet_type = selected_type
        # Reset subsequent state
        view.path = None
        view.preview_embed = None
        view.current_leg_data = {}
        logger.info(f"Bet Type selected: {view.bet_type} by {interaction.user.id} (Serial: {view.bet_serial})")
        view.update_view() # Update view to show path options
        await interaction.response.edit_message(content="Step 3: Choose Bet Specifics", view=view, embed=None)


class PathButton(Button):
    def __init__(self, label: str, custom_id: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=custom_id)

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return

        # Ensure sport handler is still set
        if not view.sport_handler:
             logger.error(f"Sport handler not set when path button '{self.label}' clicked for bet {view.bet_serial}")
             # Try to re-acquire handler
             league_context = view.selected_sub_league or view.selected_league
             if league_context:
                 try: view.sport_handler = SportHandlerFactory.get_handler(league_context, SUPPORTED_LEAGUES)
                 except Exception as e: logger.error(f"Failed to re-acquire handler on path click for {league_context}: {e}")
             if not view.sport_handler: # If still no handler
                 await interaction.response.send_message("Error: Sport context lost. Please restart.", ephemeral=True)
                 view.stop()
                 return

        view.path = self.label # Store the path selected
        logger.info(f"Path chosen: '{view.path}' by {interaction.user.id} (Serial: {view.bet_serial})")

        # Get and send the appropriate modal
        try:
            modal = view.sport_handler.get_modal(view, view.path) # Pass view and path
            await interaction.response.send_modal(modal)
            logger.debug(f"Modal for path '{view.path}' sent successfully.")
            # View state doesn't change until modal submission, so no view.update_view() here
        except ValueError as e: # Specific error from get_modal if path is invalid
            logger.error(f"Error getting modal for path '{view.path}', league '{view.sport_handler.league}': {e}")
            await interaction.response.send_message(f"Error: Could not load input form for '{view.path}'.", ephemeral=True)
            view.path = None # Reset path if modal failed
            view.update_view() # Go back to showing path buttons
            await interaction.edit_original_response(view=view)
        except Exception as e: # Catch other errors
            logger.error(f"Unexpected error generating modal for bet {view.bet_serial}, path '{view.path}': {e}", exc_info=True)
            if not interaction.response.is_done(): # Check if modal response already happened (unlikely but possible)
                 await interaction.response.send_message("An unexpected error occurred setting up the bet form.", ephemeral=True)
            # Optionally reset state or stop view if modal fails critically
            # view.path = None
            # view.update_view()
            # await interaction.edit_original_response(view=view)


class ChannelSelect(Select):
    def __init__(self, guild: Optional[discord.Guild], embed_channel_id_1: Optional[int], embed_channel_id_2: Optional[int]):
        options = []
        placeholder = "5. Select Channel..."
        disabled = True

        if guild:
            channel_ids = [ch_id for ch_id in [embed_channel_id_1, embed_channel_id_2] if ch_id is not None]
            if not channel_ids:
                options = [SelectOption(label="No embed channels set", value="none")]
                placeholder = "Error: Configure embed channels"
            else:
                valid_channels_found = False
                for ch_id in channel_ids:
                    channel = guild.get_channel(ch_id)
                    # Check if channel exists, is text, and bot has permissions
                    if channel and isinstance(channel, discord.TextChannel):
                        perms = channel.permissions_for(guild.me)
                        # Ensure webhook perm needed for posting
                        if perms.send_messages and perms.embed_links and perms.manage_webhooks:
                            options.append(SelectOption(label=f"#{channel.name}", value=str(channel.id)))
                            valid_channels_found = True
                        else: logger.warning(f"Bot lacks Send/Embed/Webhook perms in configured channel {channel.id} ({channel.name})")
                    else: logger.warning(f"Configured embed channel {ch_id} not found or not text channel in guild {guild.id}")

                if not valid_channels_found:
                    options = [SelectOption(label="Invalid configured channels", value="none")]
                    placeholder = "Error: Check channel config/perms"
                else:
                    disabled = False # Enable select only if valid options exist
        else: # Should not happen if command is guild_only
            options = [SelectOption(label="Error: Use in server", value="error")]
            placeholder = "Error: Command must be used in a server"

        super().__init__(placeholder=placeholder, options=options, custom_id="channel_select", min_values=1, max_values=1, disabled=disabled)

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return
        selected_value = self.values[0]
        if selected_value in ["none", "error"]:
            view.selected_channel_id = None
            await interaction.response.send_message("Please select a valid channel.", ephemeral=True)
        else:
            try:
                view.selected_channel_id = int(selected_value)
                logger.info(f"Channel selected: {view.selected_channel_id} by {interaction.user.id} (Serial: {view.bet_serial})")
                await interaction.response.defer() # Acknowledge interaction
                # Update preview with selection (will also enable/disable confirm button)
                await view.update_preview_description_and_footer(interaction)
            except ValueError:
                 logger.error(f"Invalid channel value selected: {selected_value} for bet {view.bet_serial}")
                 view.selected_channel_id = None
                 await interaction.response.send_message("Invalid channel value selected.", ephemeral=True)
            except Exception as e:
                 logger.error(f"Error in ChannelSelect callback: {e}", exc_info=True)
                 if not interaction.response.is_done():
                      await interaction.response.send_message("An error occurred processing your channel selection.", ephemeral=True)


class UnitsSelect(Select):
    def __init__(self):
        # Consider fetching unit options from config or DB if variable
        options = [SelectOption(label=f"{i} Unit{'s' if i > 1 else ''}", value=str(i)) for i in range(1, 4)] # Example: 1-3 units
        super().__init__(placeholder="6. Select Units...", options=options, custom_id="units_select", min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return
        try:
            view.selected_units = int(self.values[0])
            logger.info(f"Units selected: {view.selected_units} by {interaction.user.id} (Serial: {view.bet_serial})")
            await interaction.response.defer() # Acknowledge interaction
            # Update preview with selection (will add stake line and enable/disable confirm button)
            await view.update_preview_description_and_footer(interaction)
        except ValueError:
             logger.error(f"Invalid units value selected: {self.values[0]} for bet {view.bet_serial}")
             view.selected_units = None
             await interaction.response.send_message("Invalid units value selected.", ephemeral=True)
        except Exception as e:
             logger.error(f"Error in UnitsSelect callback: {e}", exc_info=True)
             if not interaction.response.is_done():
                  await interaction.response.send_message("An error occurred processing your unit selection.", ephemeral=True)


class ConfirmButton(Button):
    def __init__(self, disabled: bool = True, row: Optional[int] = None):
        super().__init__(label="Confirm Bet", style=discord.ButtonStyle.success, custom_id="confirm_bet", disabled=disabled, row=row)

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return

        if not view.selected_channel_id or not view.selected_units or not view.preview_embed or not view.current_leg_data:
            logger.warning(f"Confirm bet {view.bet_serial} attempt failed: Missing Chan={view.selected_channel_id}, Units={view.selected_units}, Embed={view.preview_embed is not None}, Data={view.current_leg_data is not None}")
            await interaction.response.send_message("Error: Missing channel, units, or bet details. Please select them.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        logger.info(f"ConfirmButton processing bet {view.bet_serial} for user {interaction.user.id}")

        try:
            guild = interaction.guild
            if not guild: raise ValueError("Interaction missing guild context for confirmation.")

            target_channel = guild.get_channel(view.selected_channel_id)
            if not target_channel or not isinstance(target_channel, discord.TextChannel):
                raise ValueError(f"Selected channel {view.selected_channel_id} is invalid or not found.")
            target_perms = target_channel.permissions_for(guild.me)
            if not target_perms.send_messages or not target_perms.embed_links:
                raise PermissionError(f"Missing Send/Embed permissions in target channel {target_channel.mention}")

            webhook = None
            webhook_name = f"{guild.me.display_name} Bets"
            try:
                webhooks = await target_channel.webhooks()
                webhook = next((wh for wh in webhooks if wh.user and wh.user.id == guild.me.id), None)
                if not webhook and target_perms.manage_webhooks:
                    webhook = await target_channel.create_webhook(name=webhook_name)
                    logger.info(f"Created new webhook {webhook.id} named '{webhook_name}' in channel {target_channel.id}")
                elif not webhook and webhooks:
                    webhook = webhooks[0]
                    logger.warning(f"Using existing webhook {webhook.id} (owned by {webhook.user}) in channel {target_channel.id}")
                elif not webhook:
                    raise BettingBotError("Webhook required but none available/creatable. Check permissions.")
            except discord.Forbidden:
                logger.error(f"Forbidden error managing/using webhooks in channel {target_channel.id}.")
                raise PermissionError("Bot lacks permissions for webhooks.") from None
            except Exception as e:
                logger.error(f"Error getting/creating webhook for channel {target_channel.id}: {e}", exc_info=True)
                raise BettingBotError("Error setting up webhook for posting.") from e

            if not webhook: raise BettingBotError("Could not obtain a webhook instance.")

            # --- MEMBER ROLE MENTION LOGIC ---
            settings = await fetch_guild_settings_and_sub(guild.id)
            member_role_id = settings.get('member_role') # Fetch the role ID
            mention_content = "" # Default to no mention
            if member_role_id:
                role = guild.get_role(member_role_id)
                # Check if role exists AND if the bot can mention it (role setting)
                if role and role.mentionable:
                    mention_content = f"{role.mention} " # Add the mention + space
                    logger.debug(f"Adding mention for member_role ID {member_role_id} ('{role.name}') in bet {view.bet_serial}")
                elif role:
                    logger.warning(f"Member role ID {member_role_id} ('{role.name}') found but is not mentionable in guild {guild.id}. Cannot ping.")
                    member_role_id = None # Don't save non-mentionable role ID to bet
                else:
                    logger.warning(f"Configured member role ID {member_role_id} not found in guild {guild.id}. Cannot ping.")
                    member_role_id = None # Don't save invalid role ID to bet
            else:
                logger.debug(f"No member_role configured for guild {guild.id}.")
            # --- END MEMBER ROLE MENTION LOGIC ---


            capper_display_name = interaction.user.display_name
            capper_avatar_url = interaction.user.display_avatar.url
            try:
                capper_query = "SELECT display_name, image_path FROM cappers WHERE user_id = %s AND guild_id = %s"
                capper_record = await db_manager.fetch_one(capper_query, (interaction.user.id, guild.id))
                if capper_record:
                    db_display_name = capper_record.get("display_name")
                    db_image_path = capper_record.get("image_path")
                    if db_display_name: capper_display_name = db_display_name
                    if db_image_path: capper_avatar_url = db_image_path
                    logger.debug(f"Using capper profile: Name='{capper_display_name}', Avatar='{capper_avatar_url}'")
                else: logger.debug(f"No capper record for user {interaction.user.id}, using Discord profile.")
            except DatabaseError as db_e: logger.error(f"DB Error fetching capper info: {db_e}. Using Discord defaults.")
            except Exception as e: logger.error(f"Unexpected error fetching capper info: {e}. Using Discord defaults.", exc_info=True)

            final_embed = view.preview_embed
            final_embed.timestamp = discord.utils.utcnow()
            final_embed.color = discord.Color.gold()
            final_embed.set_footer(text=f"Bet #{view.bet_serial}")

            # Use mention_content in webhook send
            bet_message = await webhook.send(
                content=mention_content, # Pass the mention string here
                embed=final_embed,
                username=capper_display_name,
                avatar_url=capper_avatar_url,
                wait=True
            )
            logger.info(f"Bet {view.bet_serial} message {bet_message.id} posted via webhook {webhook.id} in channel {target_channel.id} with content '{mention_content}'.")

            async with db_manager._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("START TRANSACTION")
                    try:
                        fb_data = view.current_leg_data
                        db_bet_type = 'standard'
                        player_prop_value = None
                        line_value = None
                        path = view.path

                        if path == "Bet on a Player":
                            db_bet_type = 'prop'
                            player_prop_value = fb_data.get('prop')
                        elif path == "Bet on a Team":
                            line_value = fb_data.get('line')
                        elif path == "Bet on a Driver":
                            db_bet_type = 'prop'
                            player_prop_value = fb_data.get('line')
                        elif path == "Bet on a Race Prop":
                            db_bet_type = 'prop'
                            player_prop_value = f"{fb_data.get('event','?')}: {fb_data.get('laps','?')} {fb_data.get('outcome','?')}"
                        elif path == "Bet on a Golfer":
                            db_bet_type = 'prop'
                            player_prop_value = fb_data.get('line')
                        elif path == "Bet on a Tournament Prop":
                            db_bet_type = 'prop'
                            player_prop_value = f"{fb_data.get('event','?')}: {fb_data.get('outcome','?')}"
                        elif path == "Bet on a Player Prop":
                            db_bet_type = 'prop'
                            player_prop_value = fb_data.get('prop')
                        elif path == "Bet on a Match":
                            line_value = fb_data.get('line')
                        elif path == "Bet on a Fight":
                            line_value = fb_data.get('line')
                        elif path == "Bet on a Horse":
                            line_value = fb_data.get('line')
                        elif path == "Bet on a Race Prop": # Duplicate path name - check logic
                            db_bet_type = 'prop'
                            player_prop_value = f"{fb_data.get('event','?')}: {fb_data.get('outcome','?')} {fb_data.get('pick','?')}"

                        team_db = fb_data.get('team') or fb_data.get('player1') or fb_data.get('team1') or fb_data.get('fighter1') or fb_data.get('horse') or fb_data.get('driver') or fb_data.get('golfer') or fb_data.get('player') or 'N/A'
                        opponent_db = fb_data.get('opponent') or fb_data.get('player2') or fb_data.get('team2') or fb_data.get('fighter2') or 'N/A'
                        if path == "Bet on a Driver":
                            opponent_db = fb_data.get('car_number', 'N/A')
                        elif path == "Bet on a Golfer":
                            opponent_db = "Tournament"
                        elif path == "Bet on a Tournament Prop":
                            team_db = fb_data.get('event', 'N/A')
                            opponent_db = "Tournament"
                        elif path == "Bet on a Horse":
                            opponent_db = "Race Field"
                        elif path == "Bet on a Race Prop": # Duplicate path name - check logic
                            team_db = fb_data.get('event', 'N/A')
                            opponent_db = fb_data.get('pick', fb_data.get('outcome', 'N/A'))

                        player_name_db = fb_data.get('player_name') or fb_data.get('player') or fb_data.get('fighter') or fb_data.get('driver') or fb_data.get('golfer')
                        league_db = (view.selected_sub_league or view.selected_league or 'UNK').upper()

                        odds_raw = fb_data.get('odds', 'N/A')
                        odds_db = None
                        try:
                            if isinstance(odds_raw, (int, float)):
                                odds_db = float(odds_raw)
                            elif isinstance(odds_raw, str):
                                if odds_raw.upper() == 'EVEN':
                                    odds_db = 100.0
                                else:
                                    try:
                                        odds_db = float(odds_raw.replace('+',''))
                                    except ValueError:
                                        pass
                        except Exception:
                            pass

                        line_db_value = line_value
                        line_db = None
                        try:
                            if isinstance(line_db_value, (int, float)):
                                line_db = float(line_db_value)
                            elif isinstance(line_db_value, str) and line_db_value.upper() not in ['N/A', '']:
                                line_db = line_db_value
                        except Exception:
                            pass

                        player_id_db = fb_data.get('player_id')
                        event_id_db = fb_data.get('event_id')
                        stake_db = fb_data.get('stake', float(view.selected_units))

                        # ADDED member_role_id to the query and params
                        bets_query = """
                            INSERT INTO bets
                            (bet_serial, user_id, guild_id, league, team, opponent, units, bet_type, message_id,
                             player_id, player_prop, odds, event_id, line, legs, stake, created_at, bet_won, bet_loss, member_role_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
                        """
                        bets_params = (
                            view.bet_serial, interaction.user.id, guild.id, league_db, team_db, opponent_db,
                            view.selected_units, db_bet_type, bet_message.id, player_id_db, player_prop_value,
                            odds_db, event_id_db, line_db, 1, stake_db, 0, 0, member_role_id # Pass the ID here
                        )
                        await cur.execute(bets_query, bets_params)
                        logger.info(f"Bet {view.bet_serial} saved to 'bets' table with units={view.selected_units}, stake={stake_db:.2f}, bet_won=0, bet_loss=0, member_role_id={member_role_id}")

                        unit_records_query = """
                            INSERT INTO unit_records (guild_id, bet_serial, user_id, units, timestamp, total)
                            VALUES (%s, %s, %s, %s, NOW(), %s)
                        """
                        unit_records_params = (guild.id, view.bet_serial, interaction.user.id, 0.0, 0.0)
                        await cur.execute(unit_records_query, unit_records_params)
                        logger.info(f"Inserted into unit_records for bet {view.bet_serial}: units=0.0, total=0.0")

                        await conn.commit()
                        logger.info(f"Transaction committed for bet {view.bet_serial}.")

                    except Exception as db_trans_err:
                        logger.error(f"Error during DB transaction for bet {view.bet_serial}: {db_trans_err}", exc_info=True)
                        await conn.rollback()
                        try:
                            await bet_message.delete()
                        except:
                            logger.warning(f"Failed to delete message {bet_message.id} after DB rollback for bet {view.bet_serial}")
                        raise DatabaseError("Failed to save bet details to database.") from db_trans_err

            view.bet_service.pending_bets[bet_message.id] = view.bet_serial

            await interaction.followup.send(f"Bet #{view.bet_serial} placed successfully in {target_channel.mention}! Please add ✅ or ❌ to resolve.", ephemeral=True)
            await view.original_interaction.edit_original_response(content=f"✅ Bet #{view.bet_serial} Placed!", view=None, embed=None)
            view.stop()

        except (ValidationError, PermissionError, DatabaseError, BettingBotError) as e:
            logger.warning(f"Error confirming bet {view.bet_serial}: {e}")
            await interaction.followup.send(f"Error placing bet: {e}", ephemeral=True)
            if isinstance(e, (DatabaseError, BettingBotError)):
                 view.stop()
        except Exception as e:
            logger.error(f"Unexpected error confirming bet {view.bet_serial}: {e}", exc_info=True)
            await interaction.followup.send(f"An unexpected error occurred while placing the bet.", ephemeral=True)
            if not view.is_finished(): view.stop()


class EditButton(Button):
    def __init__(self, row: Optional[int] = None):
        super().__init__(label="Edit Bet", style=discord.ButtonStyle.secondary, custom_id="edit_bet", row=row)

    async def callback(self, interaction: Interaction):
        view: BetWorkflowView = self.view
        if not await view.interaction_check(interaction): return

        # Check if we have the necessary info to re-open the modal
        if not view.path or not view.current_leg_data or not view.sport_handler:
            logger.warning(f"Cannot edit bet {view.bet_serial}: Missing path, data, or handler. Resetting to path selection.")
            # Reset state to allow user to re-select path
            view.path = None
            view.preview_embed = None
            view.current_leg_data = {}
            view.selected_channel_id = None
            view.selected_units = None

            # Ensure handler exists before updating view
            if not view.sport_handler:
                league_context = view.selected_sub_league or view.selected_league
                if league_context:
                     try: view.sport_handler = SportHandlerFactory.get_handler(league_context, SUPPORTED_LEAGUES)
                     except Exception as e: logger.error(f"Failed to re-acquire handler for edit fallback: {e}")
                if not view.sport_handler: # Still no handler
                     await interaction.response.send_message("Error: Cannot edit bet, context lost. Please restart.", ephemeral=True)
                     view.stop(); return

            view.update_view() # Go back to path selection state
            try:
                await interaction.response.edit_message(content="Step 3: Choose Bet Specifics (Editing)", view=view, embed=None)
            except discord.HTTPException as e:
                 logger.error(f"HTTPException editing message for edit fallback {view.bet_serial}: {e}")
                 # If original edit fails, try ephemeral response
                 if not interaction.response.is_done():
                      await interaction.response.send_message("Error updating bet setup. Please try again.", ephemeral=True)
            return

        # Re-open the modal, pre-filling with current_leg_data
        try:
            modal = view.sport_handler.get_modal(view, view.path)
            # Populate modal fields from stored data
            for child in modal.children:
                if isinstance(child, TextInput) and child.custom_id in view.current_leg_data:
                     # Ensure value is string for default
                     child.default = str(view.current_leg_data.get(child.custom_id, ''))

            logger.info(f"Re-opening modal for edit by {interaction.user.id} for bet serial {view.bet_serial}: Path='{view.path}'")
            await interaction.response.send_modal(modal)
            # Clear preview embed AFTER sending modal to signify editing state
            view.preview_embed = None
            # Don't update view here, wait for modal submission

        except ValueError as e: # Handle errors from get_modal
             logger.error(f"Error getting modal for edit in bet {view.bet_serial}: {e}")
             await interaction.response.send_message(f"Error generating edit form: {e}", ephemeral=True)
        except discord.HTTPException as e:
             logger.error(f"HTTPException sending modal for edit {view.bet_serial}: {e}")
             # If modal send fails, maybe interaction already responded to?
             if not interaction.response.is_done():
                  await interaction.response.send_message("Error opening edit form. Please try again.", ephemeral=True)
        except Exception as e:
             logger.error(f"Unexpected error generating modal for edit {view.bet_serial}: {e}", exc_info=True)
             if not interaction.response.is_done():
                  await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)


# --- Modal Classes ---
# (Keep all modal classes as they were in the provided file)
class PlayerBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Player Bet Details"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or parent_view.selected_league or "nba"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["nba"])
        league_display = league.upper()
        self.add_item(TextInput(
            label="Team Name (Player's Team)", required=True, custom_id="team",
            placeholder=f"e.g., {examples['team']} ({league_display})"
        ))
        self.add_item(TextInput(
            label="Opponent Name", required=True, custom_id="opponent",
            placeholder=f"e.g., {examples['opponent']} ({league_display})"
        ))
        self.add_item(TextInput(
            label="Player Name", required=True, custom_id="player_name",
            placeholder=f"e.g., {examples['player']}"
        ))
        self.add_item(TextInput(
            label="Prop (e.g., Points Over 25.5)", required=True, custom_id="prop",
            placeholder="Points Over 25.5"
        ))
        self.add_item(TextInput(
            label="Odds (e.g., -110 or +150)", required=True, custom_id="odds",
            placeholder="-110 or +150"
        ))

    async def on_submit(self, interaction: Interaction):
        # Extract data, ensuring keys match TextInput custom_ids
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Player" # Add path context
        if not all(data.values()): # Basic check for empty fields
            await interaction.response.send_message("All fields are required.", ephemeral=True)
            return
        self.parent_view.current_leg_data = data
        logger.info(f"Player Bet Modal submitted by {interaction.user.id} (Serial: {self.parent_view.bet_serial}): {data}")
        await interaction.response.defer() # Acknowledge modal submission
        await self.parent_view.show_preview() # Trigger preview generation

class TeamBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Team Bet Details"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or parent_view.selected_league or "nba"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["nba"])
        league_display = league.upper()
        self.add_item(TextInput(label="Team Pick", required=True, custom_id="team", placeholder=f"e.g., {examples['team']} ({league_display})"))
        self.add_item(TextInput(label="Opponent", required=True, custom_id="opponent", placeholder=f"e.g., {examples['opponent']} ({league_display})"))
        self.add_item(TextInput(label="Line (e.g., -7.5 or ML)", required=True, custom_id="line", placeholder="-7.5 or ML"))
        self.add_item(TextInput(label="Odds (e.g., -110)", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Team"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"Team Bet Modal submitted by {interaction.user.id} (Serial: {self.parent_view.bet_serial}): {data}")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class NASCARDriverBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter NASCAR Driver Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        examples = LEAGUE_EXAMPLES["nascar"]
        self.add_item(TextInput(label="Driver", required=True, custom_id="driver", placeholder=f"e.g., {examples['driver']}"))
        self.add_item(TextInput(label="Car #", required=True, custom_id="car_number", placeholder=f"e.g., {examples['car_number']}"))
        self.add_item(TextInput(label="Pick (e.g., Top 5 Finish)", required=True, custom_id="line", placeholder="Top 5 Finish"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Driver"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"NASCAR Driver Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class NASCRaceBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter NASCAR Race Prop"):
        super().__init__(title=title)
        self.parent_view = parent_view
        examples = LEAGUE_EXAMPLES["nascar"]
        self.add_item(TextInput(label="Event Name/Prop", required=True, custom_id="event", placeholder=f"e.g., {examples['event']}"))
        self.add_item(TextInput(label="Prop Condition (e.g., Laps)", required=True, custom_id="laps", placeholder="e.g., Total Laps"))
        self.add_item(TextInput(label="Your Pick (e.g., Over 10.5)", required=True, custom_id="outcome", placeholder="e.g., Over 10.5"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Race Prop"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"NASCAR Race Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class GolfGolferBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Golfer Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or "pga"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["pga"])
        self.add_item(TextInput(label="Golfer", required=True, custom_id="golfer", placeholder=f"e.g., {examples['golfer']}"))
        self.add_item(TextInput(label="Pick (e.g., Top 10 Finish)", required=True, custom_id="line", placeholder="e.g., Top 10 Finish"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Golfer"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"Golf Golfer Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class GolfTournamentBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Tournament Prop"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or "pga"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["pga"])
        self.add_item(TextInput(label="Tournament Prop", required=True, custom_id="event", placeholder=f"e.g., {examples['event']}"))
        self.add_item(TextInput(label="Pick (e.g., Over 5.5 Birdies)", required=True, custom_id="outcome", placeholder="e.g., Over 5.5 Birdies"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Tournament Prop"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"Golf Tournament Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class TennisPlayerBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Player Prop Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or "atp"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["atp"])
        self.add_item(TextInput(label="Player", required=True, custom_id="player", placeholder=f"e.g., {examples['player']}"))
        self.add_item(TextInput(label="Opponent", required=True, custom_id="opponent", placeholder=f"e.g., {examples['opponent']}"))
        self.add_item(TextInput(label="Prop", required=True, custom_id="prop", placeholder="e.g., Over 22.5 Games"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Player Prop"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"Tennis Player Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class TennisMatchBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Match Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or "atp"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["atp"])
        self.add_item(TextInput(label="Player 1", required=True, custom_id="player1", placeholder=f"e.g., {examples['player']}"))
        self.add_item(TextInput(label="Player 2", required=True, custom_id="player2", placeholder=f"e.g., {examples['opponent']}"))
        self.add_item(TextInput(label="Pick (e.g., -1.5 Sets)", required=True, custom_id="line", placeholder="e.g., -1.5 Sets"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Match"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"Tennis Match Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class UFCFighterBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Fighter Prop Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        examples = LEAGUE_EXAMPLES["ufc"]
        self.add_item(TextInput(label="Fighter", required=True, custom_id="fighter", placeholder=f"e.g., {examples['fighter']}"))
        self.add_item(TextInput(label="Opponent", required=True, custom_id="opponent", placeholder=f"e.g., {examples['opponent']}"))
        self.add_item(TextInput(label="Prop (e.g., KO/TKO)", required=True, custom_id="prop", placeholder=f"e.g., {examples['prop']}"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Fighter Prop"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"UFC Fighter Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class UFCFightBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Fight Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        examples = LEAGUE_EXAMPLES["ufc"]
        self.add_item(TextInput(label="Fighter 1", required=True, custom_id="fighter1", placeholder=f"e.g., {examples['fighter']}"))
        self.add_item(TextInput(label="Fighter 2", required=True, custom_id="fighter2", placeholder=f"e.g., {examples['opponent']}"))
        self.add_item(TextInput(label="Pick (e.g., Over 2.5 Rds)", required=True, custom_id="line", placeholder="e.g., Over 2.5 Rounds"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Fight"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"UFC Fight Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class EsportsPlayerBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Esports Player Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or "csgo"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["csgo"])
        self.add_item(TextInput(label="Player", required=True, custom_id="player", placeholder=f"e.g., {examples['player']}"))
        self.add_item(TextInput(label="Team", required=True, custom_id="team", placeholder=f"e.g., {examples['team']}"))
        self.add_item(TextInput(label="Prop (e.g., Kills Over 20.5)", required=True, custom_id="prop", placeholder="e.g., Kills Over 20.5"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Player"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"Esports Player Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class EsportsMatchBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Esports Match Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or "csgo"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["csgo"])
        self.add_item(TextInput(label="Team 1", required=True, custom_id="team1", placeholder=f"e.g., {examples['team']}"))
        self.add_item(TextInput(label="Team 2", required=True, custom_id="team2", placeholder=f"e.g., {examples['opponent']}"))
        self.add_item(TextInput(label="Pick (e.g., Map 1 Winner)", required=True, custom_id="line", placeholder="e.g., Map 1 Winner"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Match"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"Esports Match Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class HorseBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Horse Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or "kentucky_derby"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["kentucky_derby"])
        self.add_item(TextInput(label="Horse", required=True, custom_id="horse", placeholder=f"e.g., {examples['horse']}"))
        self.add_item(TextInput(label="Pick (e.g., Win/Place/Show)", required=True, custom_id="line", placeholder="e.g., Win/Place/Show"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Horse"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"Horse Bet Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

class HorseRaceBetModal(Modal):
    def __init__(self, parent_view: 'BetWorkflowView', title="Enter Race Prop Bet"):
        super().__init__(title=title)
        self.parent_view = parent_view
        league = parent_view.selected_sub_league or "kentucky_derby"
        examples = LEAGUE_EXAMPLES.get(league.lower(), LEAGUE_EXAMPLES["kentucky_derby"])
        self.add_item(TextInput(label="Race Name/Event", required=True, custom_id="event", placeholder=f"e.g., {examples['event']}"))
        self.add_item(TextInput(label="Prop Description", required=True, custom_id="outcome", placeholder="e.g., Total Finishers"))
        self.add_item(TextInput(label="Your Pick (e.g., Over/Under Value)", required=True, custom_id="pick", placeholder="e.g., Over 8.5"))
        self.add_item(TextInput(label="Odds", required=True, custom_id="odds", placeholder="-110 or +150"))

    async def on_submit(self, interaction: Interaction):
        data = {child.custom_id: child.value.strip() for child in self.children if isinstance(child, TextInput)}
        data['path'] = "Bet on a Race Prop"
        if not all(data.values()): await interaction.response.send_message("All fields are required.", ephemeral=True); return
        self.parent_view.current_leg_data = data
        logger.info(f"Horse Race Modal submitted: {data} (Serial: {self.parent_view.bet_serial})")
        await interaction.response.defer()
        await self.parent_view.show_preview()

# --- Command Logic/Interaction Handlers ---
# These functions MUST be defined before setup_bet_service_commands

async def bet_command_interaction(interaction: Interaction, bet_service_instance: 'BetService'):
    """Handles the logic for the /bet command."""
    if not interaction.guild or not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("Use in server text channel.", ephemeral=True)
        return
    guild_id = interaction.guild_id
    current_channel_id = interaction.channel.id
    user_id = interaction.user.id
    logger.debug(f"/bet invoked: User={user_id}, Chan={current_channel_id}, Guild={guild_id}")
    try:
        settings = await fetch_guild_settings_and_sub(guild_id)
        cmd_ch_1_id = settings.get('command_channel_1')
        cmd_ch_2_id = settings.get('command_channel_2')
        embed_ch_1_id = settings.get('embed_channel_1')
        embed_ch_2_id = settings.get('embed_channel_2')
        auth_role_id = settings.get('authorized_role')
        admin_role_id = settings.get('admin_role')

        allowed_command_channels = [ch for ch in [cmd_ch_1_id, cmd_ch_2_id] if ch]
        if not allowed_command_channels:
            await interaction.response.send_message("Cmd channels not configured.", ephemeral=True)
            return
        if current_channel_id not in allowed_command_channels:
            channel_mentions = [f"<#{ch_id}>" for ch_id in allowed_command_channels if interaction.guild.get_channel(ch_id)]
            await interaction.response.send_message(f"Please use `/bet` in: {', '.join(channel_mentions) or 'configured channels'}", ephemeral=True)
            return

        valid_embed_channels = bool(embed_ch_1_id and interaction.guild.get_channel(embed_ch_1_id)) or bool(embed_ch_2_id and interaction.guild.get_channel(embed_ch_2_id))
        if not valid_embed_channels:
            await interaction.response.send_message("Embed channels not configured.", ephemeral=True)
            return

        if auth_role_id:
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message("Error checking roles.", ephemeral=True)
                return
            member = interaction.user # Already checked it's a Member
            is_authorized = any(role.id == auth_role_id for role in member.roles)
            is_admin_role = (admin_role_id and any(role.id == admin_role_id for role in member.roles))
            has_admin_perm = member.guild_permissions.administrator
            if not (is_authorized or is_admin_role or has_admin_perm):
                auth_role = interaction.guild.get_role(auth_role_id)
                role_name = auth_role.name if auth_role else f"ID {auth_role_id}"
                await interaction.response.send_message(f"Need '{role_name}' role or admin perms.", ephemeral=True)
                return

        logger.info(f"/bet initiated by authorized user {user_id}.")
        # Pass the bet_service_instance (self equivalent) to the view
        view = BetWorkflowView(interaction, bet_service_instance, embed_ch_1_id, embed_ch_2_id)
        await interaction.response.send_message("Starting bet setup...\nStep 1: Select League/Category", view=view, ephemeral=True)

    except DatabaseError as e:
        logger.error(f"DB error during /bet setup: {e}", exc_info=True)
        await interaction.response.send_message("Error accessing config.", ephemeral=True)
    except Exception as e:
        logger.error(f"Unexpected error during /bet setup: {e}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message("Unexpected error.", ephemeral=True)

async def edit_units_command_interaction(interaction: Interaction, bet_serial: int, units: float, total: float):
    """Handles the logic for the /edit_units command."""
    if not interaction.guild:
        await interaction.response.send_message("Use in server.", ephemeral=True)
        return
    guild_id = interaction.guild_id
    user_id = interaction.user.id
    logger.debug(f"/edit_units: User={user_id}, Guild={guild_id}, BetSerial={bet_serial}, Units={units}, Total={total}")
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        settings = await fetch_guild_settings_and_sub(guild_id)
        admin_role_id = settings.get('admin_role')
        is_admin = False
        if isinstance(interaction.user, discord.Member):
            is_admin = interaction.user.guild_permissions.administrator or (admin_role_id and any(role.id == admin_role_id for role in interaction.user.roles))

        bet_query = "SELECT user_id FROM bets WHERE bet_serial = %s AND guild_id = %s" # Removed message_id fetch unless needed
        bet_record = await db_manager.fetch_one(bet_query, (bet_serial, guild_id))
        if not bet_record:
            await interaction.followup.send(f"Bet #{bet_serial} not found.", ephemeral=True)
            return

        bettor_id = bet_record.get('user_id')

        if user_id != bettor_id and not is_admin:
            await interaction.followup.send("Must be the bettor or an admin to edit units.", ephemeral=True)
            return

        # Perform the update
        update_query = "UPDATE unit_records SET units = %s, total = %s WHERE bet_serial = %s AND user_id = %s AND guild_id = %s"
        params = (units, total, bet_serial, bettor_id, guild_id)
        rows_affected = await db_manager.execute(update_query, params)

        if rows_affected > 0:
            logger.info(f"Updated unit_records for bet {bet_serial} by user {user_id}")
            await interaction.followup.send(f"Successfully updated unit records for bet #{bet_serial}.", ephemeral=True)
        else:
            logger.warning(f"Failed to update unit_records for bet {bet_serial} (0 rows affected). User: {user_id}")
            await interaction.followup.send(f"Could not find or update unit records for bet #{bet_serial}.", ephemeral=True)

    except DatabaseError as e:
        logger.error(f"DB error in /edit_units: {e}", exc_info=True)
        await interaction.followup.send("A database error occurred.", ephemeral=True)
    except Exception as e:
        logger.error(f"Unexpected error in /edit_units: {e}", exc_info=True)
        await interaction.followup.send("An unexpected error occurred.", ephemeral=True)

async def cancel_bet_command_interaction(interaction: Interaction, bet_service_instance: 'BetService'):
    """Handles the logic for the /cancel_bet command."""
    # We pass the bet_service_instance (self equivalent) to the handler
    # Ensure cancel_bet_command_handler is imported and accepts these args
    await cancel_bet_command_handler(interaction, bet_service_instance)


# --- BetService Class Definition ---
class BetService:
    # Keep __init__ as is
    def __init__(self, bot: discord.Client, command_tree: app_commands.CommandTree):
        self.bot = bot
        self.tree = command_tree # Keep reference if needed for other purposes
        self.pending_bets: Dict[int, int] = {} # message_id: bet_serial
        self.scheduler = AsyncIOScheduler()
        logger.info("BetService initialized.")

    # Modify start() to ONLY handle scheduler setup
    async def start(self) -> None:
        """Starts the BetService scheduler."""
        # REMOVED command registration and sync logic from here
        logger.info("Bet service starting (scheduler only).")
        self._setup_scheduler()
        logger.info("Bet service scheduler started.")

    # Keep stop() as is
    async def stop(self) -> None:
        """Stops the BetService scheduler."""
        logger.info("Bet service stopping.")
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False) # Don't wait for jobs to finish
                logger.info("APScheduler shut down.")
        except Exception as e:
            logger.error(f"Error shutting down APScheduler: {e}", exc_info=True)
        self.pending_bets.clear()
        logger.info("Bet service stopped.")

    # Keep _fetch_configured_guilds (if needed elsewhere)
    async def _fetch_configured_guilds(self) -> List[int]:
        """Fetch guild IDs from server_settings where commands should be registered."""
        # This might be redundant if core.py already fetches, but can be used internally
        try:
            query = "SELECT DISTINCT guild_id FROM server_settings WHERE guild_id IS NOT NULL" # Or check subscription status
            guilds = await db_manager.fetch(query)
            guild_ids = [int(guild['guild_id']) for guild in guilds if guild.get('guild_id')] # Ensure IDs are int
            logger.debug(f"BetService fetched configured guild IDs: {guild_ids}")
            return guild_ids
        except Exception as e:
            logger.error(f"BetService failed to fetch configured guilds: {e}", exc_info=True)
            return [] # Return empty list on error

    # Keep _setup_scheduler() as is
    def _setup_scheduler(self):
        """Sets up the APScheduler jobs."""
        if not self.scheduler.running:
            logger.info("Setting up APScheduler jobs for tallying.")
            try:
                # Schedule monthly tally slightly after midnight UTC on the 1st
                self.scheduler.add_job(self.run_monthly_tally, 'cron', day=1, hour=0, minute=1, timezone='utc', misfire_grace_time=3600, replace_existing=True, id='monthly_tally_job')
                # Schedule yearly tally slightly after midnight UTC on Jan 1st
                self.scheduler.add_job(self.run_yearly_tally, 'cron', month=1, day=1, hour=0, minute=5, timezone='utc', misfire_grace_time=3600, replace_existing=True, id='yearly_tally_job')
                self.scheduler.start()
                logger.info("APScheduler started successfully with tally jobs.")
            except Exception as e:
                logger.error(f"Failed to start or add jobs to APScheduler: {e}", exc_info=True)
        else:
            logger.info("APScheduler already running.")

    # Keep tally methods as is
    async def run_monthly_tally(self):
        """Runs the monthly tally process for all relevant guilds."""
        now = datetime.now(timezone.utc)
        # Calculate the year and month of the *previous* month
        first_day_of_current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
        year = last_day_of_previous_month.year
        month = last_day_of_previous_month.month
        logger.info(f"Running monthly tally job for Year: {year}, Month: {month}")
        try:
            # Fetch all guilds that might have records (consider fetching from unit_records if settings isn't definitive)
            query = "SELECT DISTINCT guild_id FROM unit_records WHERE YEAR(timestamp) = %s AND MONTH(timestamp) = %s AND guild_id IS NOT NULL" # Added NOT NULL check
            guilds = await db_manager.fetch(query, (year, month)) # Fetch guilds with activity in the target month
            if not guilds:
                logger.info(f"Monthly Tally: No guilds with activity found for {year}-{month:02d}.")
                return

            for guild_data in guilds:
                guild_id = guild_data.get('guild_id')
                if guild_id:
                    await self.tally_monthly_totals(int(guild_id), year, month) # Ensure int
                else: logger.warning("Monthly Tally: Found null guild_id in unit_records.")

        except DatabaseError as e: logger.error(f"Database error running monthly tally scheduler: {e}", exc_info=True)
        except Exception as e: logger.error(f"Unexpected error running monthly tally scheduler: {e}", exc_info=True)

    async def run_yearly_tally(self):
        """Runs the yearly tally process for all relevant guilds."""
        now = datetime.now(timezone.utc)
        year = now.year - 1 # Tally for the previous year
        logger.info(f"Running yearly tally job for Year: {year}")
        try:
             # Fetch guilds active in the target year
            query = "SELECT DISTINCT guild_id FROM unit_records WHERE YEAR(timestamp) = %s AND guild_id IS NOT NULL" # Added NOT NULL check
            guilds = await db_manager.fetch(query, (year,))
            if not guilds:
                logger.info(f"Yearly Tally: No guilds with activity found for year {year}.")
                return

            for guild_data in guilds:
                guild_id = guild_data.get('guild_id')
                if guild_id:
                    await self.tally_yearly_totals(int(guild_id), year) # Ensure int
                else: logger.warning("Yearly Tally: Found null guild_id in unit_records.")

        except DatabaseError as e: logger.error(f"Database error running yearly tally scheduler: {e}", exc_info=True)
        except Exception as e: logger.error(f"Unexpected error running yearly tally scheduler: {e}", exc_info=True)

    async def tally_monthly_totals(self, guild_id: int, year: int, month: int):
        """Calculates and stores the net unit total for a specific guild and month."""
        logger.info(f"Calculating monthly total for Guild: {guild_id}, Year: {year}, Month: {month}")
        try:
             # Sum 'total' from unit_records for the given guild/month/year, excluding the summary rows (where user_id is NULL)
            query = """
                SELECT SUM(total) as monthly_net_units
                FROM unit_records
                WHERE guild_id = %s
                  AND YEAR(timestamp) = %s
                  AND MONTH(timestamp) = %s
                  AND user_id IS NOT NULL
            """
            result = await db_manager.fetch_one(query, (guild_id, year, month))
            monthly_total = float(result.get('monthly_net_units') or 0.0) if result else 0.0

            # Insert or update the summary record (user_id = NULL)
            summary_timestamp = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc) # Use start of month for timestamp
            upsert_query = """
                 INSERT INTO unit_records (guild_id, user_id, units, total, timestamp)
                 VALUES (%s, NULL, %s, %s, %s)
                 ON DUPLICATE KEY UPDATE total = VALUES(total), units = VALUES(units)
            """
            # Store 0 for units in summary row, monthly_total for total
            await db_manager.execute(upsert_query, (guild_id, 0.0, monthly_total, summary_timestamp))
            logger.info(f"Stored/Updated monthly tally for Guild {guild_id}, {year}-{month:02d}: Net Units = {monthly_total:.2f}")

        except DatabaseError as e: logger.error(f"Database error tallying monthly totals for guild {guild_id}: {e}", exc_info=True)
        except Exception as e: logger.error(f"Unexpected error tallying monthly totals for guild {guild_id}: {e}", exc_info=True)


    async def tally_yearly_totals(self, guild_id: int, year: int):
        """Calculates and potentially stores yearly totals per user (e.g., in a 'cappers' table)."""
        logger.info(f"Calculating yearly totals for Guild: {guild_id}, Year: {year}")
        try:
            # Calculate yearly total per user from unit_records
            query = """
                 SELECT user_id, SUM(total) as yearly_net_units
                 FROM unit_records
                 WHERE guild_id = %s
                   AND user_id IS NOT NULL
                   AND YEAR(timestamp) = %s
                 GROUP BY user_id
            """
            results = await db_manager.fetch(query, (guild_id, year))
            if not results:
                logger.info(f"Yearly Tally: No user records found for guild {guild_id} in year {year}.")
                return

            updated_count = 0
            for record in results:
                user_id = record.get('user_id')
                yearly_total = float(record.get('yearly_net_units') or 0.0)
                if user_id:
                    # --- ADJUST THIS QUERY if your table/column is different ---
                    update_query = "UPDATE cappers SET year_total = %s WHERE guild_id = %s AND user_id = %s" # Example: updating 'cappers' table
                    params = (yearly_total, guild_id, user_id)
                    # --- END ADJUST ---
                    try:
                         rows_updated = await db_manager.execute(update_query, params)
                         if rows_updated > 0:
                              logger.info(f"Updated year_total for user {user_id}, year {year}: Net Units = {yearly_total:.2f}")
                              updated_count += 1
                         # else: logger.debug(f"No record found for user {user_id} in guild {guild_id} to update year_total.")
                    except DatabaseError as e_update:
                         logger.error(f"DB error updating yearly total for user {user_id}: {e_update}")
                    except Exception as e_other:
                         logger.error(f"Unexpected error updating yearly total for user {user_id}: {e_other}")

            logger.info(f"Yearly tally completed for Guild {guild_id}, Year {year}. Attempted updates for {len(results)} users, successful updates: {updated_count}.")

        except DatabaseError as e: logger.error(f"Database error tallying yearly totals for guild {guild_id}: {e}", exc_info=True)
        except Exception as e: logger.error(f"Unexpected error tallying yearly totals for guild {guild_id}: {e}", exc_info=True)

    async def handle_final_bet_reaction(self, payload: discord.RawReactionActionEvent) -> None:
        # Early return for invalid emojis
        if payload.emoji.name not in ["✅", "❌"]:
            logger.debug(f"Reaction ignored: Invalid emoji '{payload.emoji.name}' on MsgID={payload.message_id}")
            return

        logger.info(f"Entered handle_final_bet_reaction: Emoji={payload.emoji.name}, MsgID={payload.message_id}, UserID={payload.user_id}, GuildID={payload.guild_id}")

        # Ignore bot's own reactions
        if payload.user_id == self.bot.user.id:
            logger.debug("Ignoring bot's own reaction.")
            return

        # Check if message is a pending bet
        bet_serial = self.pending_bets.get(payload.message_id)
        logger.debug(f"Checking pending_bets: MsgID={payload.message_id}, BetSerial={bet_serial}, PendingBets={self.pending_bets}")
        if not bet_serial:
            logger.debug(f"Reaction ignored: MsgID {payload.message_id} not in pending_bets.")
            return

        # Validate guild, member, and channel
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            logger.warning(f"Guild {payload.guild_id} not found for bet {bet_serial}")
            return
        member = guild.get_member(payload.user_id)
        if not member:
            logger.warning(f"Member {payload.user_id} not found for bet {bet_serial}")
            return
        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(f"Channel {payload.channel_id} invalid for bet {bet_serial}")
            return

        # Check bot permissions
        perms = channel.permissions_for(guild.me)
        if not (perms.view_channel and perms.read_message_history):
            logger.error(f"Missing permissions in channel {payload.channel_id}: View={perms.view_channel}, ReadHistory={perms.read_message_history}")
            return

        try:
            # Fetch bet info to verify bettor
            bet_info_query = "SELECT user_id, units FROM bets WHERE bet_serial = %s AND guild_id = %s"
            bet_info = await db_manager.fetch_one(bet_info_query, (bet_serial, guild.id))
            if not bet_info:
                logger.warning(f"Bet {bet_serial} not found in DB.")
                if payload.message_id in self.pending_bets:
                    del self.pending_bets[payload.message_id]
                return
            bettor_id = bet_info.get("user_id")
            units_risked = float(bet_info.get("units", 0.0))
            logger.debug(f"Bet info: BettorID={bettor_id}, UnitsRisked={units_risked}")

            # Check if reaction is from the bettor
            if payload.user_id != bettor_id:
                logger.info(f"Reaction ignored: User {payload.user_id} is not the bettor {bettor_id} for bet {bet_serial}")
                if perms.manage_messages:
                    try:
                        message = await channel.fetch_message(payload.message_id)
                        await message.remove_reaction(payload.emoji, member)
                        logger.debug(f"Removed unauthorized reaction '{payload.emoji.name}' by {payload.user_id} from bet {bet_serial}")
                    except Exception as e:
                        logger.warning(f"Failed to remove unauthorized reaction for bet {bet_serial}: {e}")
                return

            logger.info(f"Processing reaction '{payload.emoji.name}' by bettor {member.id} for bet {bet_serial}")

            # Transaction for valid reaction
            async with db_manager._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("START TRANSACTION")
                    try:
                        # Lock and check bet
                        query = "SELECT user_id, guild_id, units, bet_won, bet_loss, odds, stake FROM bets WHERE bet_serial = %s FOR UPDATE"
                        await cur.execute(query, (bet_serial,))
                        bet_record = await cur.fetchone()
                        logger.debug(f"Bet record for {bet_serial}: {bet_record}")
                        if not bet_record:
                            logger.info(f"Bet {bet_serial} not found.")
                            if payload.message_id in self.pending_bets:
                                del self.pending_bets[payload.message_id]
                            await cur.execute("ROLLBACK")
                            return
                        if bet_record.get('bet_won') == 1 or bet_record.get('bet_loss') == 1:
                            logger.info(f"Bet {bet_serial} already resolved: Won={bet_record.get('bet_won')}, Loss={bet_record.get('bet_loss')}")
                            if payload.message_id in self.pending_bets:
                                del self.pending_bets[payload.message_id]
                            await cur.execute("ROLLBACK")
                            try:
                                await channel.send(f"Bet #{bet_serial} is already resolved.", delete_after=10)
                            except discord.Forbidden:
                                logger.warning(f"Cannot notify user about resolved bet {bet_serial}: Missing permissions")
                            return

                        # Verify unit_records row
                        check_query = "SELECT units, total FROM unit_records WHERE guild_id = %s AND user_id = %s AND bet_serial = %s"
                        await cur.execute(check_query, (bet_record.get("guild_id"), bet_record.get("user_id"), bet_serial))
                        unit_record = await cur.fetchone()
                        if not unit_record:
                            logger.error(f"No unit_records row found for bet {bet_serial}, guild {bet_record.get('guild_id')}, user {bet_record.get('user_id')}")
                            await cur.execute("ROLLBACK")
                            if payload.message_id in self.pending_bets:
                                del self.pending_bets[payload.message_id]
                            return
                        logger.debug(f"Unit_records before update for bet {bet_serial}: units={unit_record.get('units')}, total={unit_record.get('total')}")

                        # Fetch message
                        try:
                            message = await channel.fetch_message(payload.message_id)
                            if not message.embeds:
                                raise ValueError("No embeds in message")
                        except Exception as e:
                            logger.error(f"Failed to fetch message for bet {bet_serial}: {e}")
                            await cur.execute("ROLLBACK")
                            if payload.message_id in self.pending_bets:
                                del self.pending_bets[payload.message_id]
                            return

                        embed = message.embeds[0]
                        db_guild_id = bet_record.get("guild_id")
                        original_bettor_id = bet_record.get("user_id")
                        stake_db = float(bet_record.get("stake", units_risked))
                        logger.debug(f"Processing bet {bet_serial}: units_risked={units_risked}, stake_db={stake_db}")

                        # Set outcome
                        set_won, set_loss, new_status, units_update, net_unit_change, new_color = None, None, "Error", 0.0, 0.0, embed.color
                        if payload.emoji.name == "✅":
                            set_won, set_loss, new_status = 1, 0, "Won"
                            units_update = stake_db  # stake for win
                            net_unit_change = stake_db  # Total is stake for win
                            new_color = discord.Color.green()
                        elif payload.emoji.name == "❌":
                            set_won, set_loss, new_status = 0, 1, "Lost"
                            units_update = -stake_db  # negative stake for loss
                            net_unit_change = -units_risked  # Total is -units for loss
                            new_color = discord.Color.red()
                        logger.debug(f"Outcome: Status={new_status}, UnitsUpdate={units_update}, NetUnitChange={net_unit_change}")

                        # Update bets
                        update_bets_query = "UPDATE bets SET bet_won = %s, bet_loss = %s, resolved_by = %s, resolved_at = NOW() WHERE bet_serial = %s"
                        await cur.execute(update_bets_query, (set_won, set_loss, payload.user_id, bet_serial))
                        rows_updated = cur.rowcount
                        logger.debug(f"Bets update affected {rows_updated} rows")

                        if rows_updated > 0:
                            # Update cappers
                            cappers_update_query = """
                                INSERT INTO cappers (guild_id, user_id, bet_won, bet_loss) VALUES (%s, %s, %s, %s)
                                ON DUPLICATE KEY UPDATE bet_won = bet_won + VALUES(bet_won), bet_loss = bet_loss + VALUES(bet_loss)
                            """
                            await cur.execute(cappers_update_query, (db_guild_id, original_bettor_id, set_won or 0, set_loss or 0))
                            logger.debug(f"Cappers updated")

                            # Update unit_records
                            unit_records_update_query = """
                                UPDATE unit_records SET units = %s, total = %s WHERE guild_id = %s AND user_id = %s AND bet_serial = %s
                            """
                            await cur.execute(unit_records_update_query, (units_update, net_unit_change, db_guild_id, original_bettor_id, bet_serial))
                            rows_updated = cur.rowcount
                            logger.debug(f"Unit_records update for bet {bet_serial} affected {rows_updated} rows")
                            if rows_updated == 0:
                                logger.error(f"Failed to update unit_records for bet {bet_serial}: No rows matched")

                            await conn.commit()
                            logger.info(f"Transaction committed for bet {bet_serial}")

                            # Update embed
                            try:
                                embed.color = new_color
                                embed.set_footer(text=f"Resolved as {new_status} by {member.display_name} | Bet #{bet_serial}")
                                embed.timestamp = discord.utils.utcnow()
                                await message.edit(embed=embed)
                                await message.clear_reactions()
                                logger.debug(f"Message updated and reactions cleared")
                            except Exception as e:
                                logger.warning(f"Failed to edit message for bet {bet_serial}: {e}")

                            if payload.message_id in self.pending_bets:
                                del self.pending_bets[payload.message_id]
                        else:
                            logger.warning(f"Bet {bet_serial} update failed: 0 rows affected")
                            await conn.rollback()
                    except Exception as trans_err:
                        logger.error(f"Transaction error for bet {bet_serial}: {trans_err}", exc_info=True)
                        await conn.rollback()
        except Exception as e:
            logger.error(f"Unexpected error for bet {bet_serial}: {e}", exc_info=True)

# --- Setup Function for Core ---
# This MUST be at the top level (no indentation)

def setup_bet_service_commands(tree: app_commands.CommandTree, bet_service_instance: BetService, guild: discord.Object):
    """Adds BetService specific commands (/bet, /edit_units, /cancel_bet) to the tree for a specific guild."""
    logger.debug(f"Setting up BetService commands for guild {guild.id}")

    # Use wrapper functions or lambdas to correctly pass the bet_service_instance

    @tree.command(name="bet", description="Start the interactive bet placement process.", guild=guild)
    @app_commands.guild_only() # Ensure guild_only decorator if needed
    async def bet_cmd_wrapper(interaction: Interaction):
        # Calls the logic function, passing the service instance
        await bet_command_interaction(interaction, bet_service_instance)

    @tree.command(name="edit_units", description="Admin/Bettor: Edit units/total for a bet in unit_records.", guild=guild)
    @app_commands.guild_only()
    @app_commands.describe(bet_serial="The serial number of the bet to edit.", units="New units risked value (e.g., 1.0).", total="New potential profit/loss value.")
    async def edit_units_cmd_wrapper(interaction: Interaction, bet_serial: int, units: float, total: float):
        await edit_units_command_interaction(interaction, bet_serial, units, total)

    @tree.command(name="cancel_bet", description="Cancel one of your pending bets.", guild=guild)
    @app_commands.guild_only()
    async def cancel_bet_cmd_wrapper(interaction: Interaction):
        await cancel_bet_command_interaction(interaction, bet_service_instance)

    logger.info(f"BetService commands (/bet, /edit_units, /cancel_bet) added to tree for guild {guild.id}")

# --- End of bet_service.py ---
# bot/core.py
# Moved load_logos to global, simplified guild command registration.

import discord
import logging
import asyncio
import traceback
import importlib
import importlib.util
import os
import sys
from discord import app_commands
from typing import Dict, Callable, List, Tuple, Union, Coroutine, Any

# Use db_manager instance directly
from bot.data.db_manager import db_manager
from bot.data.cache_manager import cache_manager
from bot.services.game_service import GameService
from bot.services.voice_service import VoiceService
from bot.services.bet_service import BetService # Only import class
from web.server import setup_server, start_server, stop_server
from config.settings import TEST_GUILD_ID, DISCORD_TOKEN
from bot.utils.errors import (
    BettingBotError, DatabaseConnectionError, DatabaseQueryError, DatabaseError,
    APIConnectionError, APITimeoutError, APIResponseError,
    ValidationError, PermissionError, AuthenticationError
)
from bot.tasks.startup_checks import run_startup_checks

logger = logging.getLogger(__name__)

# --- UPDATED Command File Lists ---
# Moved 'load_logos' to GLOBAL
GLOBAL_COMMAND_FILES = ["admin", "subscription", "help", "load_logos"]
# --- END UPDATE ---

COMMANDS_DIR_PATH = os.path.join(os.path.dirname(__file__), 'commands')
GUILD_COMMAND_FILES = []
try:
    all_command_files = [f[:-3] for f in os.listdir(COMMANDS_DIR_PATH) if f.endswith('.py') and f != '__init__.py']
    # Exclude global commands
    GUILD_COMMAND_FILES = [cmd for cmd in all_command_files if cmd not in GLOBAL_COMMAND_FILES]
    logger.info(f"Identified Global command files: {GLOBAL_COMMAND_FILES}")
    logger.info(f"Identified Guild command files (from commands/ folder): {GUILD_COMMAND_FILES}")
except FileNotFoundError:
    logger.error(f"Could not find commands directory: {COMMANDS_DIR_PATH}. Guild command loading from folder will fail.")

GuildSetupFunc = Callable[[app_commands.CommandTree, discord.Object], Union[None, Coroutine[Any, Any, None]]]
GlobalSetupFunc = Callable[[app_commands.CommandTree], Union[None, Coroutine[Any, Any, None]]]

class BettingBot(discord.Client):
    def __init__(self, *args, **kwargs):
        # ... (Keep __init__ exactly as before) ...
        logger.info("--- BettingBot __init__ START ---")
        super().__init__(*args, **kwargs)
        logger.info("Initializing DB Manager instance...")
        self.db_manager = db_manager
        logger.info("Initializing Cache Manager instance...")
        self.cache_manager = cache_manager
        logger.info("Initializing Command Tree...")
        self.command_tree = app_commands.CommandTree(self)
        logger.info("Initializing Game Service...")
        self.game_service = GameService(self)
        logger.info("Initializing Voice Service...")
        self.voice_service = VoiceService(self)
        logger.info("Initializing Bet Service...")
        self.bet_service = BetService(self, self.command_tree)
        logger.info("Initializing Web App variable...")
        self.web_app = None
        self.guild_command_setup_functions: Dict[str, Union[GuildSetupFunc, Callable]] = {} # Allow generic callable for bet_service
        logger.info("--- BettingBot __init__ END ---")


    async def load_commands(self):
        logger.info("--- Starting Command Loading ---")
        commands_base_module = "bot.commands"
        self.guild_command_setup_functions = {}

        # Load and setup GLOBAL commands
        logger.info("Loading GLOBAL commands...")
        for cmd_name in GLOBAL_COMMAND_FILES: # Uses updated list including load_logos
            module_path = f"{commands_base_module}.{cmd_name}"
            try:
                spec = importlib.util.find_spec(module_path)
                if spec is None: logger.error(f"GLOBAL command module {module_path} not found."); continue
                module = importlib.import_module(module_path)
                if module_path in sys.modules: module = importlib.reload(sys.modules[module_path]) # Reload for dev
                else: module = importlib.import_module(module_path)

                if hasattr(module, "setup") and callable(module.setup):
                    setup_func: GlobalSetupFunc = module.setup
                    # Try calling setup without guild first (most global commands)
                    try:
                        result = setup_func(self.command_tree)
                        if asyncio.iscoroutine(result): await result
                        logger.info(f"Loaded and registered GLOBAL command: {cmd_name}")
                    except TypeError as te:
                        # Handle cases like setid which might accept guild=None globally? Unlikely needed here.
                        logger.warning(f"Global setup for '{cmd_name}' failed standard call: {te}. Might indicate unexpected signature.")
                else:
                    logger.warning(f"Global command module {cmd_name} is missing a callable setup(tree) function.")
            except ImportError as e: logger.error(f"Failed to import GLOBAL command module {cmd_name}: {e}", exc_info=True)
            except Exception as e: logger.error(f"Unexpected error loading GLOBAL command {cmd_name}: {e}", exc_info=True)


        # Load and store GUILD command setup functions from commands/ folder
        logger.info("Loading GUILD command modules from commands/ folder (storing setup functions)...")
        for cmd_name in GUILD_COMMAND_FILES: # Uses updated list excluding load_logos
            module_path = f"{commands_base_module}.{cmd_name}"
            try:
                spec = importlib.util.find_spec(module_path)
                if spec is None: logger.error(f"GUILD command module {module_path} not found."); continue
                if module_path in sys.modules: module = importlib.reload(sys.modules[module_path]) # Reload for dev
                else: module = importlib.import_module(module_path)

                if hasattr(module, "setup") and callable(module.setup):
                    # Store the setup function - it should now expect (tree, guild)
                    self.guild_command_setup_functions[cmd_name] = module.setup
                    logger.info(f"Stored setup function for GUILD command: {cmd_name}")
                else:
                    logger.warning(f"Guild command module {cmd_name} is missing a callable setup function.")
            except ImportError as e: logger.error(f"Failed to import GUILD command module {cmd_name}: {e}", exc_info=True)
            except Exception as e: logger.error(f"Unexpected error loading GUILD command {cmd_name}: {e}", exc_info=True)


        # Store BetService command setup function dynamically
        logger.info("Storing BetService command setup function...")
        try:
            bet_service_module = importlib.import_module("bot.services.bet_service")
            if hasattr(bet_service_module, "setup_bet_service_commands"):
                setup_func_ref = getattr(bet_service_module, "setup_bet_service_commands")
                if callable(setup_func_ref):
                    self.guild_command_setup_functions["bet_service"] = setup_func_ref
                    logger.info("Stored setup function for BetService commands.")
                else: logger.error("'setup_bet_service_commands' found but not callable.")
            else: logger.error("Attribute 'setup_bet_service_commands' not found in bet_service.py module.")
        except ImportError as e: logger.error(f"Failed to import bet_service module: {e}", exc_info=True)
        except Exception as e: logger.error(f"Error accessing BetService setup function: {e}", exc_info=True)

        logger.info("Command loading process finished.")
        logger.info(f"Stored setup functions for GUILD commands: {list(self.guild_command_setup_functions.keys())}")

    async def register_guild_commands(self, guild_id: int):
        """Registers all stored guild-specific commands (including BetService) for a given guild."""
        guild_object = discord.Object(id=guild_id)
        logger.info(f"--- Registering GUILD commands for Guild ID: {guild_id} ---")

        if not self.guild_command_setup_functions:
            logger.warning(f"No guild command setup functions loaded for guild {guild_id}.")
            return

        # Clear existing commands registered specifically for this guild
        try:
            self.command_tree.clear_commands(guild=guild_object)
            logger.debug(f"Cleared existing commands for guild {guild_id} before registration.")
        except Exception as e:
            logger.error(f"Failed to clear commands for guild {guild_id}: {e}", exc_info=True)

        # --- SIMPLIFIED Registration Loop ---
        # Now assumes all setup functions (except bet_service special case) expect (tree, guild)
        for cmd_key, setup_func in self.guild_command_setup_functions.items():
            logger.debug(f"Attempting registration for '{cmd_key}' in guild {guild_id}...")
            try:
                if cmd_key == "bet_service":
                     if callable(setup_func):
                         # Call setup_bet_service_commands(tree, bet_service_instance, guild)
                         setup_func(self.command_tree, self.bet_service, guild_object)
                         logger.info(f"Successfully called setup for BetService commands in guild {guild_id}.")
                     else:
                          logger.error(f"Stored setup function for 'bet_service' is not callable.")
                else:
                    # Call the standard setup function, now expecting guild object
                    result = setup_func(self.command_tree, guild=guild_object) # Pass guild
                    if asyncio.iscoroutine(result): await result
                    logger.info(f"Successfully called setup for '{cmd_key}' in guild {guild_id}.")

            except Exception as e:
                # Catch errors during the setup call for a specific command
                logger.error(f"Error calling setup function for '{cmd_key}' in guild {guild_id}: {e}", exc_info=True)
                # Continue to try registering other commands
        # --- END SIMPLIFIED Loop ---

        # Sync all registered commands for this specific guild
        try:
            logger.info(f"Attempting to sync all registered commands for guild {guild_id}...")
            await self.command_tree.sync(guild=guild_object)
            synced_commands = [cmd.name for cmd in self.command_tree.get_commands(guild=guild_object)]
            logger.info(f"Successfully synced commands for guild {guild_id}. Synced: {synced_commands}")
            # Optional: Add check for expected vs synced commands here if needed

        except discord.HTTPException as e: logger.error(f"Discord API HTTP error syncing for guild {guild_id}: Status={e.status}, Code={e.code}, Response='{e.text}'", exc_info=True)
        except discord.Forbidden as e: logger.error(f"Discord API Forbidden error syncing for guild {guild_id}. Check bot scope/perms.", exc_info=True)
        except Exception as e: logger.error(f"Unexpected error syncing commands for guild {guild_id}: {e}", exc_info=True)

        logger.info(f"--- Finished attempting GUILD command registration for Guild ID: {guild_id} ---")


    async def setup_hook(self):
        # ... (Keep setup_hook exactly as before, it calls the updated load/register functions) ...
        logger.info("--- Running setup_hook ---")
        try:
            logger.info("STEP: Connecting to Database...")
            await self.db_manager.connect()
            logger.info("STEP COMPLETE: Database connected.")

            logger.info("STEP: Connecting to Cache...")
            await self.cache_manager.connect()
            logger.info("STEP COMPLETE: Cache connected.")

            # Start services
            logger.info("STEP: Starting Game Service...")
            if hasattr(self.game_service, 'start') and asyncio.iscoroutinefunction(self.game_service.start): await self.game_service.start()
            logger.info("STEP: Starting Voice Service...")
            if hasattr(self.voice_service, 'start') and asyncio.iscoroutinefunction(self.voice_service.start): await self.voice_service.start()
            logger.info("STEP: Starting Bet Service (scheduler)...")
            if hasattr(self.bet_service, 'start') and asyncio.iscoroutinefunction(self.bet_service.start): await self.bet_service.start() # Starts scheduler now
            logger.info("STEP COMPLETE: Bet Service scheduler started.")

            logger.info("STEP: Running startup reconciliation checks...")
            await run_startup_checks(self)
            logger.info("STEP COMPLETE: Startup reconciliation checks finished.")

            logger.info("STEP: Setting up web server...")
            self.web_app = await setup_server(self)
            logger.info("STEP COMPLETE: Web server setup.")
            logger.info("STEP: Starting web server task...")
            asyncio.create_task(start_server(self.web_app))
            logger.info("STEP COMPLETE: Web server task created.")

            logger.info("STEP: Loading ALL command definitions...")
            await self.load_commands() # Loads globals, stores guild setups dynamically
            logger.info("STEP COMPLETE: Command definitions loaded/stored.")

            logger.info("STEP: Syncing GLOBAL commands...")
            await self.command_tree.sync(guild=None) # Sync global commands immediately
            global_commands = [cmd.name for cmd in self.command_tree.get_commands(guild=None)]
            logger.info(f"STEP COMPLETE: Global commands synced: {global_commands}")

            logger.info("STEP: Fetching configured guilds for command registration...")
            configured_guild_ids = []
            try:
                configured_guild_ids = await self.db_manager.get_configured_guilds()
                logger.info(f"Found {len(configured_guild_ids)} guilds marked as configured: {configured_guild_ids}")
            except Exception as e: logger.error(f"Failed to fetch configured guilds: {e}.", exc_info=True)

            if configured_guild_ids:
                logger.info("STEP: Registering and syncing GUILD commands for configured guilds...")
                for guild_id in configured_guild_ids:
                     await self.register_guild_commands(guild_id) # Calls updated function
                logger.info("STEP COMPLETE: Finished attempting registration & sync for all configured guilds.")
            else: logger.info("No configured guilds found. Skipping guild command registration.")

            logger.info("END: setup_hook completed successfully.")

        except DatabaseConnectionError as db_conn_err:
             logger.critical(f"CRITICAL DB CONNECTION ERROR during setup_hook: {db_conn_err}. Bot cannot start.", exc_info=True)
             await self.close()
        except Exception as e:
             logger.critical(f"CRITICAL UNEXPECTED ERROR during setup_hook: {e}", exc_info=True)
             await self.close()

    # Keep other methods like on_ready, on_raw_reaction_add, on_app_command_error, close etc. as they were
    async def on_ready(self):
        logger.info(f"Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"Discord.py version: {discord.__version__}")
        logger.info("Bot is ready and online.")
        await self.change_presence(activity=discord.Game(name="Ready | /help"))

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
         if payload.user_id != self.user.id and payload.guild_id:
             if hasattr(self.bet_service, 'handle_final_bet_reaction') and asyncio.iscoroutinefunction(self.bet_service.handle_final_bet_reaction):
                 asyncio.create_task(self.bet_service.handle_final_bet_reaction(payload))
             else: logger.warning("BetService handle_final_bet_reaction method missing/not awaitable.")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
         # Keep the detailed error handling logic
         user_message = "An unexpected error occurred while running this command."
         log_level = logging.ERROR
         command_name = interaction.command.name if interaction.command else "unknown"
         log_message = f"Error in command '{command_name}': {error}"
         original_error = getattr(error, 'original', error)

         if isinstance(original_error, BettingBotError): user_message = original_error.user_message; log_level = getattr(original_error, 'log_level', logging.WARNING)
         elif isinstance(original_error, (ValidationError, PermissionError, AuthenticationError)): user_message = str(original_error); log_level = logging.WARNING
         elif isinstance(error, app_commands.CommandAlreadyRegistered): log_message = f"Command '{error.name}' already registered (recovered)."; log_level = logging.WARNING; user_message = "Internal setup issue: command conflict." # Should be less common now
         elif isinstance(error, app_commands.CommandNotFound): user_message = "Sorry, I don't recognize that command."; log_level = logging.WARNING
         # ... (Keep all other specific error checks from original file) ...
         elif isinstance(error, app_commands.TransformerError): user_message = f"Invalid input provided: {error}"; log_level = logging.WARNING

         # Logging
         if log_level >= logging.ERROR: logger.log(log_level, log_message, exc_info=original_error if isinstance(original_error, Exception) else None)
         else: logger.log(log_level, log_message)

         # Responding to user
         try:
             if interaction.response.is_done(): await interaction.followup.send(user_message, ephemeral=True)
             else: await interaction.response.send_message(user_message, ephemeral=True)
         except discord.errors.InteractionResponded:
             try: await interaction.followup.send(user_message, ephemeral=True)
             except Exception as followup_e: logger.error(f"Failed to send error followup: {followup_e}")
         except Exception as send_e: logger.error(f"Failed to send error response: {send_e}")

    async def on_disconnect(self): logger.warning("Bot disconnected from Discord.")
    async def on_resumed(self): logger.info("Bot resumed connection to Discord.")
    async def close(self):
        # ... (Keep close method exactly as before) ...
        logger.info("--- Initiating bot shutdown sequence ---")
        logger.info("STEP: Stopping web server...")
        try:
            if self.web_app and asyncio.iscoroutinefunction(stop_server): await stop_server()
        except Exception as e: logger.error(f"Error stopping web server: {e}", exc_info=True)

        logger.info("STEP: Stopping Bet Service...")
        try:
            if hasattr(self.bet_service, 'stop') and asyncio.iscoroutinefunction(self.bet_service.stop): await self.bet_service.stop()
        except Exception as e: logger.error(f"Error stopping BetService: {e}", exc_info=True)

        logger.info("STEP: Stopping Voice Service...")
        try:
            if hasattr(self.voice_service, 'stop') and asyncio.iscoroutinefunction(self.voice_service.stop): await self.voice_service.stop()
        except Exception as e: logger.error(f"Error stopping VoiceService: {e}", exc_info=True)

        logger.info("STEP: Stopping Game Service...")
        try:
            if hasattr(self.game_service, 'stop') and asyncio.iscoroutinefunction(self.game_service.stop): await self.game_service.stop()
        except Exception as e: logger.error(f"Error stopping GameService: {e}", exc_info=True)

        logger.info("STEP: Closing Cache connection...")
        try:
             if hasattr(self.cache_manager, 'close') and asyncio.iscoroutinefunction(self.cache_manager.close): await self.cache_manager.close()
        except Exception as e: logger.error(f"Error closing cache connection: {e}", exc_info=True)

        logger.info("STEP: Closing Database connection...")
        try:
             if hasattr(self.db_manager, 'close') and asyncio.iscoroutinefunction(self.db_manager.close): await self.db_manager.close()
        except Exception as e: logger.error(f"Error closing database connection: {e}", exc_info=True)

        logger.info("STEP: Closing Discord client connection...")
        await super().close()
        logger.info("STEP COMPLETE: Discord client connection closed.")
        logger.info("--- Bot shutdown sequence complete ---")

# --- End of core.py ---
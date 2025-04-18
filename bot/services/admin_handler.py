# bot/services/admin_handler.py
# CONSOLIDATED commands_registered flag update into save_guild_settings call.

import logging
import re  # For time validation
import discord
# Import BettingBot for type hinting
from typing import Optional, List, Dict, Any, Literal, Tuple, TYPE_CHECKING
from discord import Interaction, TextChannel, Role, VoiceChannel, ChannelType, SelectOption
from discord.ui import View, Button, Modal, TextInput, RoleSelect, ChannelSelect, Select

# Use TYPE_CHECKING to avoid circular import issues if needed
if TYPE_CHECKING:
    from bot.core import BettingBot  # Import the bot class for type hinting

# Define logger EARLIER, right after standard imports
logger = logging.getLogger(__name__)

# Import only the db_manager instance
try:
    from bot.data.db_manager import db_manager
except ImportError as e:
    logger.critical(f"CRITICAL: Failed to import db_manager instance from bot.data.db_manager: {e}", exc_info=True)
    # Depending on severity, you might re-raise or handle differently
    raise ImportError("Could not import the necessary database manager instance.") from e

# Import custom errors (assuming utils.errors exists) or use fallbacks
try:
    from bot.utils.errors import DatabaseError, DatabaseQueryError
except ImportError:
    logger.warning("Custom error classes not found, using basic fallbacks.")
    class DatabaseError(Exception): pass
    class DatabaseQueryError(DatabaseError):
        def __init__(self, message, query=None, original_exception=None):
            super().__init__(message)
            self.message = message
            self.query = query
            self.original_exception = original_exception

# Define types for state tracking
ConfigState = Literal["MAIN", "CHANNELS", "ROLES"]
ChannelStep = Literal["EMBED_CH_1", "CMD_CH_1", "ADMIN_CH", "EMBED_CH_2", "CMD_CH_2", "DONE"]
# ADDED MEMBER_ROLE step
RoleStep = Literal["ADMIN_ROLE", "AUTH_ROLE", "MEMBER_ROLE", "DONE"]

# --- Helper Functions ---
async def check_admin_permissions(interaction: Interaction) -> bool:
    """Checks if the interacting user has administrator permissions in the guild."""
    guild = interaction.guild
    user = interaction.user
    if not guild or not isinstance(user, discord.Member):
        message = "This command must be used inside a server."
        # Defer first, then send followup if possible
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.InteractionResponded:
                 logger.debug("Interaction already responded before guild check defer.")
            except Exception as defer_err:
                 logger.error(f"Failed defer in check_admin_permissions (guild check): {defer_err}")
                 # Cannot reliably send message if defer fails badly
                 return False # Assume failure if defer has issues

        # Now send followup
        try:
            await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed followup (guild check): {e}")
        return False # Return False as the check failed

    if not user.guild_permissions.administrator:
        message = "You need administrator permissions to configure the bot for this server."
         # Defer first, then send followup if possible
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.InteractionResponded:
                 logger.debug("Interaction already responded before perm check defer.")
            except Exception as defer_err:
                 logger.error(f"Failed defer in check_admin_permissions (perm check): {defer_err}")
                 return False

        # Now send followup
        try:
            await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed followup (perm check): {e}")
        return False # Return False as the check failed

    return True # All checks passed

async def fetch_subscription_status(guild_id: int) -> str:
    """Fetches only the subscription status."""
    try:
        sub_query = "SELECT subscription_status FROM subscribers WHERE guild_id = %s"
        sub_data = await db_manager.fetch_one(sub_query, (guild_id,))
        sub_data_dict = dict(sub_data) if sub_data else {}
        status = sub_data_dict.get('subscription_status', 'free')
        logger.debug(f"Fetched subscription status for guild {guild_id}: {status}")
        return status
    except (DatabaseError, AttributeError) as e:
        logger.error(f"DB error/attribute error fetching subscription status for guild {guild_id}: {e}")
        return 'error'
    except Exception as e:
        logger.error(f"Unexpected error fetching subscription status for guild {guild_id}: {e}", exc_info=True)
        return 'error'

async def get_current_settings_with_sub(guild_id: int, guild_name: str) -> Optional[Dict[str, Any]]:
    """Gets existing settings (or creates defaults via db_manager) and adds subscription status."""
    logger.debug(f"Getting/Creating settings for guild_id: {guild_id}")
    try:
        # Ensure db_manager creates 'member_role' if it doesn't exist
        settings = await db_manager.get_or_create_server_settings(guild_id, guild_name)
        if settings is None:
            logger.error(f"get_or_create_server_settings returned None for guild {guild_id}.")
            return None
        settings['subscription_status'] = await fetch_subscription_status(guild_id)
        keys_to_convert = [
            'embed_channel_1', 'embed_channel_2', 'command_channel_1', 'command_channel_2',
            'admin_channel_1', 'admin_role', 'authorized_role', 'member_role', # ADDED member_role
            'voice_channel_id'
        ]
        internal_settings = {}
        for db_key, value in settings.items():
            internal_key = 'admin_channel_id' if db_key == 'admin_channel_1' else db_key
            if internal_key in keys_to_convert:
                if value is not None:
                    try:
                        internal_settings[internal_key] = int(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Value for '{internal_key}' non-numeric: '{value}'. Treating as None.")
                        internal_settings[internal_key] = None
                else:
                    internal_settings[internal_key] = None
            else:
                internal_settings[internal_key] = value
        # Ensure commands_registered is treated as bool
        # Convert DB value (0 or 1) to boolean
        internal_settings['commands_registered'] = bool(int(settings.get('commands_registered', 0)))
        logger.debug(f"Processed settings (after get/create & sub fetch): {internal_settings}")
        return internal_settings
    except (DatabaseError, AttributeError) as e:
        logger.error(f"DB/Attribute error in get_current_settings_with_sub for guild {guild_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_current_settings_with_sub for guild {guild_id}: {e}", exc_info=True)
        return None

async def save_guild_settings(guild_id: int, updates: Dict[str, Any]) -> bool:
    """Saves updates to the server_settings table using INSERT...ON DUPLICATE KEY UPDATE."""
    if not updates:
        logger.warning(f"save_guild_settings called with empty updates for guild {guild_id}. Skipping DB call.")
        return True # No changes needed is considered success
    logger.debug(f"Attempting to save settings for guild {guild_id}: {updates}")
    try:
        db_updates = {}
        # ADDED member_role to keys to stringify
        keys_to_str = ['embed_channel_1', 'embed_channel_2', 'command_channel_1', 'command_channel_2', 'admin_channel_id', 'admin_role', 'authorized_role', 'member_role', 'voice_channel_id']
        for key, value in updates.items():
            db_key = 'admin_channel_1' if key == 'admin_channel_id' else key
            if key in keys_to_str:
                db_updates[db_key] = str(value) if value is not None else None
            elif key == 'commands_registered': # Handle boolean conversion for DB
                db_updates[db_key] = 1 if value else 0
            else:
                db_updates[db_key] = value # Assume other values are directly savable
        if not db_updates:
            logger.warning(f"No valid DB updates derived from input for guild {guild_id}. Nothing to save.")
            return True # Nothing to update is considered success

        # Build the query parts
        update_parts = ", ".join([f"`{key}` = %s" for key in db_updates.keys()])
        params_list = list(db_updates.values()) # Parameters for the UPDATE part

        # Include guild_id for the INSERT part
        insert_columns = ["`guild_id`"] + [f"`{key}`" for key in db_updates.keys()]
        insert_placeholders = ["%s"] * (len(db_updates) + 1) # +1 for guild_id
        insert_params = [guild_id] + params_list # Parameters for the INSERT part

        # Combine params for the full query (INSERT values first, then UPDATE values)
        full_params = tuple(insert_params + params_list)

        query = f"INSERT INTO server_settings ({', '.join(insert_columns)}) VALUES ({', '.join(insert_placeholders)}) ON DUPLICATE KEY UPDATE {update_parts}"

        logger.debug(f"Executing save query for guild {guild_id}: {query} with params {full_params}")
        # Assuming db_manager.execute returns row count or similar, but we only care about exceptions here
        await db_manager.execute(query, full_params)
        logger.info(f"Guild {guild_id} settings successfully updated/inserted in DB via INSERT...ON DUPLICATE.")
        return True
    except (DatabaseError, AttributeError) as e:
        logger.error(f"DB/Attribute error saving settings for guild {guild_id}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving settings for guild {guild_id}: {e}", exc_info=True)
        return False

# --- Modals ---
class OtherSettingsModal(Modal):
    def __init__(self, current_settings: Dict[str, Any], is_paid: bool, title="Configure Other Settings"):
        super().__init__(title=title)
        self.is_paid = is_paid
        def get_str(key):
            v = current_settings.get(key)
            return str(v) if v is not None else ''
        self.voice_ch_id = TextInput(
            label="Total Units Voice Channel ID",
            style=discord.TextStyle.short,
            required=False,
            placeholder="Optional: Channel ID for Total Units display",
            default=get_str('voice_channel_id')
        )
        self.add_item(self.voice_ch_id)
        if self.is_paid:
            self.daily_time = TextInput(
                label="Daily Report Time (Paid, UTC)",
                style=discord.TextStyle.short,
                required=False,
                placeholder="HH:MM (24-hour format, e.g., 09:30)",
                default=get_str('daily_report_time')
            )
            self.add_item(self.daily_time)
        else:
            self.daily_time = None

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        updates = {}
        errors = []
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("Error: Guild context not found.", ephemeral=True)
            return
        vc_id_str = self.voice_ch_id.value.strip() if self.voice_ch_id.value else ''
        if not vc_id_str:
            updates['voice_channel_id'] = None
        else:
            try:
                vc_id = int(vc_id_str)
                channel = guild.get_channel(vc_id)
                if not channel or not isinstance(channel, VoiceChannel):
                    errors.append(f"Invalid or non-voice channel ID: {vc_id_str}")
                else:
                    updates['voice_channel_id'] = vc_id
            except ValueError:
                errors.append(f"Invalid Voice Channel ID format: '{vc_id_str}'")
        if self.is_paid and self.daily_time:
            time_str = self.daily_time.value.strip() if self.daily_time.value else ''
            if not time_str:
                updates['daily_report_time'] = None
            else:
                if re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str):
                    updates['daily_report_time'] = time_str
                else:
                    errors.append(f"Invalid Daily Report Time format: '{time_str}'. Use HH:MM.")
        if errors:
            await interaction.followup.send("Errors found:\n- " + "\n- ".join(errors), ephemeral=True)
            return
        # Save settings collected from the modal
        if await save_guild_settings(guild.id, updates):
            await interaction.followup.send("Other settings updated successfully!", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while saving other settings.", ephemeral=True)
        # Note: We don't rebuild the main view here as modals are separate flows

class BotAppearanceModal(Modal):
    def __init__(self, current_settings: Dict[str, Any], title="Configure Bot Appearance (Paid)"):
        super().__init__(title=title)
        def get_str(key):
            v = current_settings.get(key)
            return str(v) if v is not None else ''
        self.bot_name = TextInput(
            label="Bot Name Mask (Optional)",
            style=discord.TextStyle.short,
            required=False,
            placeholder="Nickname for the bot in this server",
            default=get_str('bot_name_mask'),
            max_length=32
        )
        self.add_item(self.bot_name)
        self.bot_image_url = TextInput(
            label="Bot Image Mask URL (Optional)",
            style=discord.TextStyle.short,
            required=False,
            placeholder="URL for bot's avatar in this server",
            default=get_str('bot_image_mask')
        )
        self.add_item(self.bot_image_url)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        updates = {}
        errors = []
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.followup.send("Error: Guild ID not found.", ephemeral=True)
            return
        name_mask = self.bot_name.value.strip() if self.bot_name.value else None
        image_url_mask = self.bot_image_url.value.strip() if self.bot_image_url.value else None
        updates['bot_name_mask'] = name_mask
        updates['bot_image_mask'] = image_url_mask
        if image_url_mask and not (image_url_mask.lower().startswith(('http://', 'https://')) and '.' in image_url_mask):
            errors.append("Invalid Bot Image Mask URL format.")
        if name_mask and len(name_mask) > 32:
            errors.append("Bot Name Mask cannot be longer than 32 characters.")
        if errors:
            await interaction.followup.send("Errors found:\n- " + "\n- ".join(errors), ephemeral=True)
            return
        # Save settings collected from the modal
        if await save_guild_settings(guild_id, updates):
            apply_msg = "\n(Note: Applying appearance changes may require separate logic or bot restart)."
            await interaction.followup.send("Bot appearance mask settings updated!" + apply_msg, ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while saving bot appearance settings.", ephemeral=True)
        # Note: We don't rebuild the main view here

# --- Main Admin Settings View ---
class AdminSettingsView(View):
    """Handles sequential configuration for admin settings via message edits."""
    def __init__(self, interaction: Interaction, settings: Dict[str, Any], bot: 'BettingBot'):
        super().__init__(timeout=360)
        self.initial_interaction = interaction
        self.guild_id = interaction.guild_id
        self.settings = settings # Store initial settings
        self.sub_status = self.settings.get('subscription_status', 'free').lower()
        self.is_paid = self.sub_status in ['paid', 'active']
        self.bot = bot
        logger.debug(f"AdminSettingsView initialized for guild {self.guild_id}. Paid: {self.is_paid}. Initial Settings: {self.settings}")
        self.current_config_state: ConfigState = "MAIN"
        self.current_channel_step: ChannelStep = "EMBED_CH_1"
        self.current_role_step: RoleStep = "ADMIN_ROLE"
        self.temp_settings: Dict[str, Any] = {} # Holds changes during sequential config
        self.current_select_component: Optional[discord.ui.Select | discord.ui.ChannelSelect | discord.ui.RoleSelect] = None
        self._build_main_view()

    def _add_item_safe(self, item: discord.ui.Item):
        if len(self.children) < 25:
            self.add_item(item)
        else:
            logger.warning(f"View component limit reached in guild {self.guild_id}, could not add item: {type(item)}")

    def _add_common_buttons(self, save_callback, cancel_callback, final_step: bool = False):
        save_label = "Save" if final_step else "Next"
        save_btn = Button(label=save_label, style=discord.ButtonStyle.success, custom_id="cfg_seq_save_next", row=4)
        save_btn.callback = save_callback
        self._add_item_safe(save_btn)
        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.grey, custom_id="cfg_seq_cancel", row=4)
        cancel_btn.callback = self.cancel_sequential_config_callback
        self._add_item_safe(cancel_btn)

    def _build_main_view(self):
        logger.debug(f"[View Build] Building main view for guild {self.guild_id}")
        self.clear_items()
        self.current_config_state = "MAIN"
        self.temp_settings = {} # Clear temporary changes when returning to main menu
        btn_channels = Button(label="Text Channels", style=discord.ButtonStyle.primary, custom_id="admin_cfg_channels", row=0)
        btn_channels.callback = self.start_channels_config
        self._add_item_safe(btn_channels)
        btn_roles = Button(label="Roles", style=discord.ButtonStyle.primary, custom_id="admin_cfg_roles", row=0)
        btn_roles.callback = self.start_roles_config
        self._add_item_safe(btn_roles)
        btn_other = Button(label="Other Settings", style=discord.ButtonStyle.secondary, custom_id="admin_cfg_other", row=1)
        btn_other.callback = self.configure_other_button
        self._add_item_safe(btn_other)
        appearance_label = "Bot Appearance" if self.is_paid else "Bot Appearance (Paid Only)"
        appearance_button = Button(label=appearance_label, style=discord.ButtonStyle.secondary, custom_id="admin_cfg_appearance_dynamic", disabled=not self.is_paid, row=1)
        appearance_button.callback = self.configure_appearance_callback
        self._add_item_safe(appearance_button)
        sub_label = f"Subscription (Status: {self.sub_status.upper()})"
        sub_button = Button(label=sub_label, style=discord.ButtonStyle.secondary, custom_id="admin_cfg_sub_dynamic", row=2)
        sub_button.callback = self.configure_subscription_callback
        self._add_item_safe(sub_button)
        self.current_select_component = None
        logger.debug("Main view built successfully.")

    async def _build_channel_config_step(self, interaction: Interaction):
        step = self.current_channel_step
        logger.debug(f"[View Build] Building channel config step: {step} for guild {self.guild_id}")
        self.clear_items()
        self.current_config_state = "CHANNELS"
        message_content = f"**Step: Configure {step.replace('_', ' ').title()}**\nSelect the desired channel below, or leave blank/deselect to clear."
        select_component = None
        is_final_step = False
        step_to_placeholder = {
            "EMBED_CH_1": "Select Embed Channel 1 (Optional)",
            "CMD_CH_1": "Select Command Channel 1 (Optional)",
            "ADMIN_CH": "Select Admin Channel (Optional)",
            "EMBED_CH_2": "Select Embed Channel 2 (Paid, Optional)",
            "CMD_CH_2": "Select Command Channel 2 (Paid, Optional)"
        }
        step_to_key = {
            "EMBED_CH_1": "embed_channel_1",
            "CMD_CH_1": "command_channel_1",
            "ADMIN_CH": "admin_channel_id", # Note: Key is admin_channel_id internally
            "EMBED_CH_2": "embed_channel_2",
            "CMD_CH_2": "command_channel_2"
        }

        settings_key = step_to_key.get(step)
        # Determine if this step should be skipped (only applies to paid steps)
        requires_paid = step in ["EMBED_CH_2", "CMD_CH_2"]
        if requires_paid and not self.is_paid:
            logger.debug(f"Skipping channel step {step} - user not paid.")
            # Interaction should be deferred from the previous step's button press
            # Directly call the next step function, effectively skipping this one
            await self.next_channel_step_callback(interaction, skip_store=True) # skip_store might be irrelevant now
            return

        placeholder = step_to_placeholder.get(step, "Select a Channel (Optional)")
        # Use the stored initial settings to show current value
        current_value_id = self.settings.get(settings_key)
        if current_value_id and interaction.guild:
            try:
                channel = interaction.guild.get_channel(int(current_value_id))
                placeholder = f"Current: #{channel.name} (Select to change)" if channel else placeholder
            except (ValueError, TypeError, AttributeError): # Catch if channel deleted or ID wrong
                logger.warning(f"Could not fetch current channel for {settings_key} ID {current_value_id}")
                placeholder = f"Current: ID {current_value_id} (Invalid/Deleted? Select to change)"

        async def channel_select_callback(select_interaction: Interaction):
            # This callback updates self.temp_settings which will be saved later
            if not settings_key:
                return
            try:
                logger.debug(f"ChannelSelect callback for step {step} triggered by user {select_interaction.user.id}")
                selected_value = select_interaction.data['values'][0] if select_interaction.data['values'] else None
                selected_id = None
                if selected_value:
                    try:
                        selected_id = int(selected_value)
                        logger.debug(f"Selected channel ID for {settings_key}: {selected_id}")
                    except ValueError:
                        logger.warning(f"Invalid channel ID format received: {selected_value}")

                # Update temp_settings with the new value (or None if deselected/invalid)
                self.temp_settings[settings_key] = selected_id
                logger.debug(f"Updated temp_settings: {self.temp_settings}")

                if not select_interaction.response.is_done():
                    # Defer to acknowledge the selection without modifying the main view yet
                    await select_interaction.response.defer(ephemeral=True, thinking=False)
                    logger.debug("Deferred ChannelSelect interaction.")
            except Exception as e:
                logger.error(f"Error in ChannelSelect callback: {e}", exc_info=True)
                try:
                     # Try to inform the user about the callback error
                     if not select_interaction.response.is_done():
                          await select_interaction.response.send_message("Error processing selection.", ephemeral=True)
                     else:
                          await select_interaction.followup.send("Error processing selection.", ephemeral=True)
                except:
                     logger.error("Failed to send error message in ChannelSelect callback.")

        if step == "DONE":
            logger.debug("Channel step DONE, preparing save.")
            # Interaction should be deferred from the button press
            await self.save_sequential_config(interaction) # Save collected temp_settings
            return
        elif settings_key:
            select_component = ChannelSelect(
                placeholder=placeholder,
                custom_id=f"seq_sel_{step.lower()}",
                channel_types=[ChannelType.text],
                min_values=0, # Allow deselecting to set to None
                max_values=1,
                row=0
            )
            select_component.callback = channel_select_callback
            next_step_after_this = self._get_next_channel_step(current_step=step)
            is_final_step = (next_step_after_this == "DONE")
        else:
            # This should not happen if step logic is correct
            logger.error(f"Invalid channel step configuration: {step}. Cancelling.")
            # Interaction is likely deferred, use followup
            try: await interaction.followup.send("Internal configuration error.", ephemeral=True)
            except: pass
            await self.cancel_sequential_config_callback(interaction) # Attempt to cancel
            return

        if select_component:
            self.current_select_component = select_component
            self._add_item_safe(select_component)
            # Add Next/Save and Cancel buttons
            self._add_common_buttons(self.next_channel_step_callback, self.cancel_sequential_config_callback, final_step=is_final_step)
            logger.debug(f"Added ChannelSelect for {step}. Final step: {is_final_step}")
        else:
            # This case should ideally not be reached
            logger.error(f"Failed to create select component for channel step {step}. Cancelling.")
            try: await interaction.followup.send("Internal configuration error.", ephemeral=True)
            except: pass
            await self.cancel_sequential_config_callback(interaction)
            return

        # Update the message with the current step's view
        try:
            # Use edit_original_response as the initial message was sent via followup.send
            # interaction here is the one passed from the button press or initial call
            await interaction.edit_original_response(content=message_content, view=self)
            logger.debug(f"Edited original response for channel step {step}.")
        except discord.NotFound:
            logger.warning(f"Could not edit original message for channel step {step}. Stopping config.")
            self.stop() # Stop the view if the message is gone
        except Exception as e:
            logger.error(f"Failed to edit message for channel step {step}: {e}", exc_info=True)
            # Attempt to cancel if edit fails
            await self.cancel_sequential_config_callback(interaction)

    def _get_next_channel_step(self, current_step: Optional[ChannelStep] = None) -> ChannelStep:
        current = current_step if current_step else self.current_channel_step
        if current == "EMBED_CH_1":
            return "CMD_CH_1"
        if current == "CMD_CH_1":
            return "ADMIN_CH"
        if current == "ADMIN_CH":
            # Skip paid steps if not paid
            return "EMBED_CH_2" if self.is_paid else "DONE"
        if current == "EMBED_CH_2":
             # Skip paid steps if not paid (redundant check, but safe)
            return "CMD_CH_2" if self.is_paid else "DONE"
        if current == "CMD_CH_2":
            return "DONE"
        # Default or if already done
        return "DONE"

    async def _build_role_config_step(self, interaction: Interaction):
        step = self.current_role_step
        logger.debug(f"[View Build] Building role config step: {step} for guild {self.guild_id}")
        self.clear_items()
        self.current_config_state = "ROLES"
        # ADDED MEMBER_ROLE step details
        step_to_label = {
            "ADMIN_ROLE": "Admin Role",
            "AUTH_ROLE": "Authorized Bet Placer Role",
            "MEMBER_ROLE": "Member Role (to @ on new bets)"
        }
        message_content = f"**Step: Configure {step_to_label.get(step, step.replace('_', ' ').title())}**\nSelect the desired role below, or leave blank/deselect to clear."
        select_component = None
        is_final_step = False
        step_to_placeholder = {
            "ADMIN_ROLE": "Select Admin Role (Optional)",
            "AUTH_ROLE": "Select Authorized Role (Optional)",
            "MEMBER_ROLE": "Select Member Role (Optional)" # ADDED
        }
        step_to_key = {
            "ADMIN_ROLE": "admin_role",
            "AUTH_ROLE": "authorized_role",
            "MEMBER_ROLE": "member_role" # ADDED
        }
        settings_key = step_to_key.get(step)
        placeholder = step_to_placeholder.get(step, "Select a Role (Optional)")
        # Use the stored initial settings to show current value
        current_value_id = self.settings.get(settings_key)
        if current_value_id and interaction.guild:
            try:
                role = interaction.guild.get_role(int(current_value_id))
                placeholder = f"Current: @{role.name} (Select to change)" if role else placeholder
            except (ValueError, TypeError, AttributeError):
                logger.warning(f"Could not fetch current role for {settings_key} ID {current_value_id}")
                placeholder = f"Current: ID {current_value_id} (Invalid/Deleted? Select to change)"


        async def role_select_callback(select_interaction: Interaction):
            # This callback updates self.temp_settings which will be saved later
            if not settings_key:
                return
            try:
                logger.debug(f"RoleSelect callback for step {step} triggered by user {select_interaction.user.id}")
                selected_value = select_interaction.data['values'][0] if select_interaction.data['values'] else None
                selected_id = None
                if selected_value:
                    try:
                        selected_id = int(selected_value)
                        logger.debug(f"Selected role ID for {settings_key}: {selected_id}")
                    except ValueError:
                        logger.warning(f"Invalid role ID format received: {selected_value}")

                # Update temp_settings with the new value (or None if deselected/invalid)
                self.temp_settings[settings_key] = selected_id
                logger.debug(f"Updated temp_settings: {self.temp_settings}")

                if not select_interaction.response.is_done():
                    # Defer to acknowledge selection
                    await select_interaction.response.defer(ephemeral=True, thinking=False)
                    logger.debug("Deferred RoleSelect interaction.")
            except Exception as e:
                logger.error(f"Error in RoleSelect callback: {e}", exc_info=True)
                try:
                    if not select_interaction.response.is_done():
                        await select_interaction.response.send_message("Error processing selection.", ephemeral=True)
                    else:
                        await select_interaction.followup.send("Error processing selection.", ephemeral=True)
                except:
                     logger.error("Failed to send error message in RoleSelect callback.")

        if step == "DONE":
            logger.debug("Role step DONE, preparing save.")
            # Interaction should be deferred
            await self.save_sequential_config(interaction) # Save collected temp_settings
            return
        elif settings_key:
            select_component = RoleSelect(
                placeholder=placeholder,
                custom_id=f"seq_sel_{step.lower()}",
                min_values=0, # Allow deselecting
                max_values=1,
                row=0
            )
            select_component.callback = role_select_callback
            next_step_after_this = self._get_next_role_step(current_step=step)
            is_final_step = (next_step_after_this == "DONE")
        else:
            logger.error(f"Invalid role step configuration: {step}. Cancelling.")
            try: await interaction.followup.send("Internal configuration error.", ephemeral=True)
            except: pass
            await self.cancel_sequential_config_callback(interaction)
            return

        if select_component:
            self.current_select_component = select_component
            self._add_item_safe(select_component)
            self._add_common_buttons(self.next_role_step_callback, self.cancel_sequential_config_callback, final_step=is_final_step)
            logger.debug(f"Added RoleSelect for {step}. Final step: {is_final_step}")
        else:
            logger.error(f"Failed create select component for role step {step}. Cancelling.")
            try: await interaction.followup.send("Internal configuration error.", ephemeral=True)
            except: pass
            await self.cancel_sequential_config_callback(interaction)
            return

        # Update the message
        try:
            await interaction.edit_original_response(content=message_content, view=self)
            logger.debug(f"Edited original response for role step {step}.")
        except discord.NotFound:
            logger.warning(f"Could not edit original message for role step {step}. Stopping config.")
            self.stop() # Stop the view
        except Exception as e:
            logger.error(f"Failed to edit message for role step {step}: {e}", exc_info=True)
            await self.cancel_sequential_config_callback(interaction)

    def _get_next_role_step(self, current_step: Optional[RoleStep] = None) -> RoleStep:
        # ADDED MEMBER_ROLE step logic
        current = current_step if current_step else self.current_role_step
        if current == "ADMIN_ROLE":
            return "AUTH_ROLE"
        if current == "AUTH_ROLE":
            return "MEMBER_ROLE"
        if current == "MEMBER_ROLE":
            return "DONE"
        # Default or if already done
        return "DONE"

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Checks if the interaction user is the original user who started the command."""
        user = interaction.user
        original_user_id = self.initial_interaction.user.id
        # Allow interaction if view is somehow finished but interaction is received? No, check first.
        if self.is_finished():
            logger.debug(f"Interaction check failed: View finished.")
            # Respond ephemerally if possible
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message("This configuration menu has expired or finished.", ephemeral=True)
                except Exception: pass # Ignore errors sending expiry message
            return False

        if user.id != original_user_id:
            logger.debug(f"Interaction check failed: User {user.id} != Original User {original_user_id}")
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message("Only the user who initiated the `/admin` command can use this menu.", ephemeral=True)
                except Exception as e:
                    logger.error(f"Error sending wrong user message: {e}")
            return False

        # Log component interactions
        if interaction.data and 'custom_id' in interaction.data:
            logger.debug(f"Interaction check passed for user {user.id}. Component: {interaction.data.get('custom_id')}")
        else:
            logger.debug(f"Interaction check passed for user {user.id}. (Non-component interaction type: {interaction.type})")
        return True

    # This method seems unused/deprecated, keep or remove as needed.
    # def _store_current_selection(self) -> Tuple[bool, str]:
    #     logger.warning("_store_current_selection called - logic deprecated.")
    #     return True, ""

    async def next_channel_step_callback(self, interaction: Interaction, skip_store: bool = False):
        # skip_store logic seems related to paid feature skipping, keep it
        logger.debug(f"next_channel_step_callback entered. skip_store={skip_store}, current_step={self.current_channel_step}")
        try:
            # Interaction should be deferred from the button press OR the _build_channel_config_step if skipping
            if not interaction.response.is_done():
                logger.warning("Interaction not deferred in next_channel_step_callback!")
                # Attempt to defer just in case, but this indicates a logic issue
                await interaction.response.defer(ephemeral=True)
            else:
                logger.debug("Interaction confirmed deferred in next_channel_step_callback.")
        except Exception as e:
            logger.error(f"Error confirming/deferring interaction in next_channel_step_callback: {e}", exc_info=True)
            # Don't try followup here as the state is uncertain
            return # Don't proceed if defer state is wrong

        # No need to explicitly store selection here if callbacks handle temp_settings

        self.current_channel_step = self._get_next_channel_step()
        logger.debug(f"Next channel step is: {self.current_channel_step}")

        if self.current_channel_step == "DONE":
            logger.debug("Channel config sequence finished. Proceeding to save.")
            await self.save_sequential_config(interaction) # Pass the button interaction
        else:
            logger.debug("Building next channel config step view.")
            # Pass the button interaction to build the next step
            await self._build_channel_config_step(interaction)

    async def next_role_step_callback(self, interaction: Interaction):
        logger.debug(f"next_role_step_callback entered. current_step={self.current_role_step}")
        try:
            # Interaction should be deferred from the button press
            if not interaction.response.is_done():
                logger.warning("Interaction not deferred in next_role_step_callback!")
                await interaction.response.defer(ephemeral=True)
            else:
                logger.debug("Interaction confirmed deferred in next_role_step_callback.")
        except Exception as e:
            logger.error(f"Error confirming/deferring interaction in next_role_step_callback: {e}", exc_info=True)
            return

        # No need to explicitly store selection here

        self.current_role_step = self._get_next_role_step()
        logger.debug(f"Next role step: {self.current_role_step}")

        if self.current_role_step == "DONE":
            logger.debug("Role config sequence finished. Proceeding to save.")
            await self.save_sequential_config(interaction) # Pass the button interaction
        else:
            logger.debug("Building next role config step view.")
             # Pass the button interaction to build the next step
            await self._build_role_config_step(interaction)

    # --- REVISED save_sequential_config ---
    async def save_sequential_config(self, interaction: Interaction):
        """Saves the collected temp_settings and triggers command registration."""
        logger.debug(f"Attempting save config ({self.current_config_state}). Temp settings: {self.temp_settings}")

        # Interaction should already be deferred by the button callback calling this
        if interaction.response.is_done():
             logger.debug("Interaction already deferred before save_sequential_config.")
        else:
             logger.warning("Interaction was NOT deferred before save_sequential_config call!")
             try:
                  await interaction.response.defer(ephemeral=True) # Attempt defer if needed
             except Exception as defer_err:
                  logger.error(f"Critical: Failed to defer interaction during save: {defer_err}", exc_info=True)
                  # Try to inform user, but saving might be impossible now
                  try: await interaction.followup.send("Error: Could not process save request.", ephemeral=True)
                  except: pass
                  return # Cannot proceed reliably

        guild = interaction.guild
        if not guild:
            logger.error("Save failed: Guild not found.")
            try: await interaction.followup.send("Error: Could not identify server.", ephemeral=True)
            except Exception as fe: logger.error(f"Failed followup for missing guild: {fe}")
            return

        # --- MODIFICATION: Add commands_registered flag to the updates ---
        # Ensure the flag is set to True when saving any sequential config successfully
        # Only add if there are actual settings changes to save
        if self.temp_settings:
             self.temp_settings['commands_registered'] = True
             logger.debug(f"Added 'commands_registered': True to temp_settings before save. Final temp: {self.temp_settings}")
        else:
             logger.info(f"No temporary settings changed in {self.current_config_state} sequence, skipping save and command registration trigger.")
             # Still rebuild main view and inform user nothing changed
             self._build_main_view()
             try:
                  await interaction.followup.send("No changes detected to save.", ephemeral=True)
                  await interaction.edit_original_response(content="Select a category to configure:", view=self)
             except discord.NotFound: logger.warning("Original message not found for no changes update.")
             except Exception as e: logger.error(f"Error updating view after no changes: {e}")
             return

        config_type = self.current_config_state
        logger.info(f"Saving {config_type} settings via save_guild_settings (includes commands_registered=True)...")
        # Now save_guild_settings handles setting the flag too
        save_successful = await save_guild_settings(guild.id, self.temp_settings)

        commands_registered_successfully = False

        # --- REMOVED the separate call to set_guild_commands_registered ---
        # The save_successful flag now implicitly includes marking configured.
        if save_successful:
            logger.info(f"Settings saved successfully for {guild.id} (including commands_registered).")
            # Update the view's stored settings immediately AFTER successful save
            self.settings.update(self.temp_settings) # Update the view's cache
            # Fetch potentially missing subscription status if it wasn't in temp_settings
            if 'subscription_status' not in self.settings:
                 self.settings['subscription_status'] = await fetch_subscription_status(guild.id)
            logger.debug(f"Updated view's internal settings cache: {self.settings}")

            # Proceed directly to registering commands
            logger.info(f"Guild {guild.id} settings saved. Proceeding to register commands...")
            try:
                if hasattr(self, 'bot') and self.bot and hasattr(self.bot, 'register_guild_commands'):
                     await self.bot.register_guild_commands(guild.id)
                     commands_registered_successfully = True
                     logger.info(f"Successfully triggered command registration for {guild.id}.")
                else:
                     logger.error(f"Bot instance or register_guild_commands method not available for guild {guild.id}.")
            except Exception as reg_err:
                logger.error(f"Error during dynamic command registration call for {guild.id}: {reg_err}", exc_info=True)
        # --- END REMOVAL ---

        self._build_main_view() # Rebuild the main menu
        final_content = "Select a category to configure:"
        followup_message = ""

        if save_successful:
            settings_msg = f"{config_type.title()} settings updated successfully!"
            # Simplified command registration message logic
            if commands_registered_successfully:
                command_msg = " Guild-specific commands registered/updated."
            else:
                 # This now means command registration failed, not marking configured
                 command_msg = " Error registering guild commands. Check logs."
            followup_message = settings_msg + command_msg
            logger.info(f"Followup for {guild.id}: {followup_message}")
        else:
            followup_message = f"Error saving {config_type.lower()} settings. Check logs."
            logger.error(followup_message + f" (Guild ID: {guild.id})")
            final_content = "Save failed. Select category:" # Update content if save failed

        # Send followup message
        try:
            # Use followup as the interaction should have been deferred successfully
            await interaction.followup.send(followup_message, ephemeral=True)
        except Exception as fe:
            logger.error(f"Failed sending followup message after save attempt: {fe}")

        # Edit the original message to show the main menu again
        try:
            await interaction.edit_original_response(content=final_content, view=self)
        except discord.NotFound:
            logger.warning("Original message not found for edit after save.")
        except Exception as e:
            logger.error(f"Failed to edit original response after save attempt: {e}", exc_info=True)
    # --- END REVISED save_sequential_config ---


    async def cancel_sequential_config_callback(self, interaction: Interaction):
        logger.debug("Cancel sequential config called.")
        original_state = self.current_config_state
        self._build_main_view() # Resets view to main menu
        self.temp_settings = {} # Clear any pending changes
        content = f"{original_state.title()} configuration cancelled. Select a category:"
        try:
            # Interaction should be deferred from the button press
            if not interaction.response.is_done():
                 logger.warning("Interaction was not deferred before cancel callback!")
                 await interaction.response.defer(ephemeral=True) # Attempt defer

            # Edit the original response to show the main menu
            await interaction.edit_original_response(content=content, view=self)
            logger.debug("Edited message for cancel.")
        except discord.NotFound:
            logger.warning("Could not edit msg on cancel - deleted/expired.")
            # If edit fails, try a followup
            try: await interaction.followup.send(content, ephemeral=True)
            except Exception as f_e: logger.error(f"Failed followup after failed cancel edit: {f_e}")
        except Exception as e:
            logger.error(f"Error updating message on cancel: {e}", exc_info=True)
            # Fallback followup if edit fails
            try: await interaction.followup.send(content, ephemeral=True)
            except Exception as f_e: logger.error(f"Failed followup after failed cancel edit: {f_e}")


    async def start_channels_config(self, interaction: Interaction):
        logger.debug(f"start_channels_config called by {interaction.user.id}")
        self.current_channel_step = "EMBED_CH_1" # Start from the beginning
        self.temp_settings = {} # Clear previous temp data for this sequence
        try:
            # Defer the interaction from the button press
            await interaction.response.defer(ephemeral=True)
            logger.debug("Deferred interaction for start_channels_config")
            # Pass the deferred interaction to build the first step
            await self._build_channel_config_step(interaction)
        except discord.InteractionResponded:
             logger.warning("Interaction already responded when starting channel config.")
             # Maybe try edit if defer failed? Unlikely to work well.
        except Exception as e:
            logger.error(f"Error during start_channels_config: {e}", exc_info=True)
            try:
                # Use followup since interaction was likely deferred (or attempted)
                await interaction.followup.send("Error starting channel configuration.", ephemeral=True)
            except: pass # Ignore error sending error message

    async def start_roles_config(self, interaction: Interaction):
        logger.debug(f"start_roles_config called by {interaction.user.id}")
        # Start at the beginning of role config sequence
        self.current_role_step = "ADMIN_ROLE"
        self.temp_settings = {} # Clear previous temp data
        try:
            # Defer the interaction from the button press
            await interaction.response.defer(ephemeral=True)
            logger.debug("Deferred interaction for start_roles_config")
            # Pass the deferred interaction to build the first step
            await self._build_role_config_step(interaction)
        except discord.InteractionResponded:
             logger.warning("Interaction already responded when starting role config.")
        except Exception as e:
            logger.error(f"Error during start_roles_config: {e}", exc_info=True)
            try:
                # Use followup since interaction was likely deferred
                await interaction.followup.send("Error starting role configuration.", ephemeral=True)
            except: pass

    async def configure_other_button(self, interaction: Interaction):
        logger.debug("configure_other_button pressed.")
        guild = interaction.guild
        if not guild:
            # Should not happen with guild_only commands
            if not interaction.response.is_done():
                 try: await interaction.response.send_message("Error: Guild not found.", ephemeral=True)
                 except: pass
            return

        # Fetch latest settings *before* showing modal
        latest_settings = await get_current_settings_with_sub(guild.id, guild.name)
        if latest_settings is None:
            logger.error("Failed get settings before Other modal.")
            if not interaction.response.is_done():
                try: await interaction.response.send_message("Error retrieving current settings.", ephemeral=True)
                except: pass
            return

        # Update view's internal settings cache before opening modal
        self.settings = latest_settings
        self.is_paid = self.settings.get('subscription_status', 'free') in ['paid', 'active']

        # Create and send the modal
        modal = OtherSettingsModal(current_settings=latest_settings, is_paid=self.is_paid)
        try:
            # Use send_modal for the initial interaction
            await interaction.response.send_modal(modal)
            logger.debug("OtherSettingsModal sent.")
        except discord.InteractionResponded:
             logger.error(f"Interaction {interaction.id} already responded before sending Other modal!")
             # Try followup if initial response failed
             try: await interaction.followup.send("Error: Could not open settings modal.", ephemeral=True)
             except: pass
        except Exception as e:
            logger.error(f"Error sending OtherSettingsModal: {e}", exc_info=True)
            # Try to respond if possible
            if not interaction.response.is_done():
                try: await interaction.response.send_message("Failed to open other settings modal.", ephemeral=True)
                except: pass


    async def configure_subscription_callback(self, interaction: Interaction):
        logger.debug("configure_subscription_callback pressed.")
        guild = interaction.guild
        if not guild:
            # Should not happen
             if not interaction.response.is_done():
                  try: await interaction.response.send_message("Error: Guild not found.", ephemeral=True)
                  except: pass
             return

        try:
            # Defer button press
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            else:
                logger.debug("Sub callback interaction already handled.")
        except Exception as e:
            logger.error(f"Defer failed in sub callback: {e}")
            try:
                # Use followup as interaction might be done
                await interaction.followup.send("Error processing subscription status request.", ephemeral=True)
            except: pass
            return

        # Fetch latest settings to get current status
        latest_settings = await get_current_settings_with_sub(guild.id, guild.name)
        if latest_settings is None:
            try:
                await interaction.followup.send("Error fetching current subscription status.", ephemeral=True)
            except Exception as fe:
                logger.error(f"Failed followup fetch err sub cb: {fe}")
            return

        # Update view's internal cache AND use latest fetched for response
        self.settings = latest_settings
        status = latest_settings.get('subscription_status', 'unknown')
        daily_time = latest_settings.get('daily_report_time')
        daily_time_str = str(daily_time) if daily_time is not None else 'Not Set'

        message = (
            f"**Subscription Status:** `{status.upper()}`\n"
            f"Daily Report Time (UTC): `{daily_time_str}`\n\n"
            f"(Use `/subscription` cmd for details/management.)"
        )
        try:
            # Send info via followup
            await interaction.followup.send(message, ephemeral=True)
            logger.debug("Subscription info sent.")
        except Exception as e:
            logger.error(f"Error sending sub info followup: {e}", exc_info=True)

    async def configure_appearance_callback(self, interaction: Interaction):
        logger.debug("configure_appearance_callback pressed.")
        guild = interaction.guild
        if not guild:
             if not interaction.response.is_done():
                  try: await interaction.response.send_message("Error: Guild not found.", ephemeral=True)
                  except: pass
             return

        # Fetch latest settings first
        latest_settings = await get_current_settings_with_sub(guild.id, guild.name)
        if latest_settings is None:
            logger.error("Failed get settings before Appearance modal.")
            if not interaction.response.is_done():
                try: await interaction.response.send_message("Error retrieving current settings.", ephemeral=True)
                except: pass
            return

        # Update view's internal cache AND use latest fetched
        self.settings = latest_settings
        self.is_paid = latest_settings.get('subscription_status', 'free') in ['paid', 'active'] # Use updated status

        try:
            if not self.is_paid:
                 # Respond directly if not paid
                 await interaction.response.send_message("Bot Appearance requires paid subscription.", ephemeral=True)
                 logger.debug("Sent 'paid only' msg for appearance.")
            else:
                 # Create and send modal if paid
                 modal = BotAppearanceModal(current_settings=latest_settings)
                 await interaction.response.send_modal(modal)
                 logger.debug("BotAppearanceModal sent.")
        except discord.InteractionResponded:
            logger.error(f"Interaction {interaction.id} already responded before sending Appearance modal/message!")
            try: await interaction.followup.send("Error: Could not open appearance settings.", ephemeral=True)
            except: pass
        except Exception as e:
            logger.error(f"Error sending BotAppearanceModal/paid msg: {e}", exc_info=True)
            if not interaction.response.is_done():
                try: await interaction.response.send_message("Failed to open appearance settings.", ephemeral=True)
                except: pass

    async def on_timeout(self):
        """Called when the view times out."""
        logger.info(f"Admin settings view timed out for guild {self.guild_id}, user {self.initial_interaction.user.id}")
        # Disable all components visually
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        try:
            # Try to edit the original message to show it's timed out
            await self.initial_interaction.edit_original_response(content="Admin configuration timed out.", view=self) # Keep disabled view
        except discord.NotFound:
            logger.warning(f"Original message for admin view {self.guild_id} not found on timeout.")
        except discord.HTTPException as e:
             logger.error(f"HTTP Error editing admin view on timeout for {self.guild_id}: {e}")
        except Exception as e:
            logger.error(f"Error editing admin view on timeout for {self.guild_id}: {e}", exc_info=True)
        # super().on_timeout() # Call parent if needed, though stop() is implicitly called

    async def on_error(self, interaction: Interaction, error: Exception, item: discord.ui.Item) -> None:
        """Handle errors within view item callbacks."""
        logger.error(f"Error in AdminSettingsView item callback (Item: {item.custom_id if hasattr(item, 'custom_id') else type(item)}, Guild: {self.guild_id}): {error}", exc_info=True)
        # Try to inform the user ephemerally
        message = "An unexpected error occurred. Please try again later."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                # If not responded, try deferring then following up, or just responding
                 try:
                      await interaction.response.send_message(message, ephemeral=True)
                 except discord.InteractionResponded: # If it became done just now
                      await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send error message to user during view on_error handler: {e}")
        # Optionally stop the view on error
        # self.stop()


# --- Main Command Handler ---
async def admin_settings_command_handler(interaction: Interaction):
    """Handles the /admin command, checking permissions and launching the settings view."""
    # Ensure client is accessible
    if not hasattr(interaction, 'client') or not interaction.client:
         logger.error("Bot client instance not found on interaction.")
         if not interaction.response.is_done():
              try: await interaction.response.send_message("Internal error: Bot client not available.", ephemeral=True)
              except: pass
         return
    bot_instance = interaction.client

    guild = interaction.guild
    if not guild:
        logger.warning("Admin handler called without guild context.")
        if not interaction.response.is_done():
            try: await interaction.response.send_message("Command must be used in a server.", ephemeral=True)
            except: pass
        return

    logger.info(f"Admin handler invoked by {interaction.user} (ID: {interaction.user.id}) in guild {guild.id}")

    # Defer immediately before permission checks
    try:
        await interaction.response.defer(ephemeral=True, thinking=True)
        logger.debug(f"Deferred initial /admin interaction for {guild.id}")
    except discord.InteractionResponded:
         logger.warning(f"Interaction for /admin {guild.id} already handled before defer.")
         return # Cannot proceed if already responded
    except Exception as e:
        logger.error(f"Failed initial deferral for /admin {interaction.id}: {e}", exc_info=True)
        # Try followup since defer failed
        try: await interaction.followup.send("Error processing command start.", ephemeral=True)
        except: pass
        return

    # Check admin permissions AFTER deferring
    # Pass the already deferred interaction
    if not await check_admin_permissions(interaction):
        # check_admin_permissions now handles sending the error message via followup
        logger.warning(f"Admin cmd denied for {interaction.user.id} in {guild.id} (no perms).")
        return # Stop execution if no permissions

    # Fetch initial settings AFTER deferring and permission check
    settings = await get_current_settings_with_sub(guild.id, guild.name)
    if settings is None:
        logger.critical(f"get_current_settings_with_sub failed critically for {guild.id}.")
        try:
            await interaction.followup.send("Critical error retrieving server settings. Cannot open admin menu.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed followup after critical settings fetch err: {e}")
        return

    # Check subscription status for warning message
    warning_message = ""
    sub_status = settings.get('subscription_status', 'unknown')
    if sub_status == 'error':
         warning_message = "**Warning:** Could not retrieve subscription status.\n\n"
    elif sub_status == 'free':
         warning_message = "**Note:** Some features require a paid subscription.\n\n"

    # Create and send the view using followup
    try:
        logger.debug(f"Creating AdminSettingsView for {guild.id}...")
        # Pass the fetched initial settings and bot instance
        view = AdminSettingsView(interaction, settings, bot_instance)
        message_content = f"{warning_message}Select a category to configure:"
        logger.debug("Sending initial view via followup...")
        await interaction.followup.send(message_content, view=view, ephemeral=True)
        logger.info(f"Admin settings view sent to {interaction.user.id} in {guild.id}")
    except Exception as e:
        logger.error(f"Failed send AdminSettingsView for {guild.id}: {e}", exc_info=True)
        try:
            # Try followup if sending view failed
            await interaction.followup.send("Error displaying admin menu.", ephemeral=True)
        except Exception as final_e:
            logger.error(f"Failed final err followup: {final_e}")
# bot/services/setid_handler.py
import logging
import discord
from discord import Interaction, TextStyle, Attachment, ButtonStyle
from discord.ui import Modal, TextInput, Button, View
import re
from typing import Optional
from pathlib import Path
from datetime import datetime

from bot.data.db_manager import db_manager
from bot.utils.errors import DatabaseError

logger = logging.getLogger(__name__)

IMAGE_SAVE_PATH = Path("/home/container/bot/static/user_images")
IMAGE_SAVE_PATH.mkdir(parents=True, exist_ok=True)

def is_valid_hex_color(color_string: Optional[str]) -> bool:
    """Checks if a string is a valid hex color code (e.g., #RRGGBB or RRGGBB)."""
    if not color_string:
        return False
    match = re.search(r'^(?:#)?[0-9a-fA-F]{6}$', color_string)
    return bool(match)

class ModalButton(View):
    def __init__(self, user_id: int, image_path: str, guild_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.image_path = image_path
        self.guild_id = guild_id

    @discord.ui.button(label="Complete Profile Setup", style=ButtonStyle.primary)
    async def complete_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button is not for you!", ephemeral=True)
            return
        modal = SetIDModal(image_path=self.image_path, user_id=self.user_id, guild_id=self.guild_id)
        await interaction.response.send_modal(modal)
        self.children[0].disabled = True
        try:
            await interaction.message.edit(view=self)
        except discord.errors.NotFound:
            logger.warning(f"Could not edit button message for user {self.user_id}: Message not found")
        except Exception as e:
            logger.error(f"Failed to edit button message for user {self.user_id}: {e}", exc_info=True)

class SetIDModal(Modal):
    def __init__(self, image_path: str, user_id: int, guild_id: int):
        super().__init__(title="Set Capper Profile")
        self.image_path = image_path
        self.user_id = user_id
        self.guild_id = guild_id

        self.display_name_input = TextInput(
            label="Display Name",
            placeholder="Enter the name you want displayed on bets",
            required=True,
            max_length=100
        )
        self.add_item(self.display_name_input)

        self.banner_color_input = TextInput(
            label="Banner Color",
            placeholder="Enter hex code (e.g., 00FF29)",
            required=False,
            max_length=6
        )
        self.add_item(self.banner_color_input)

    async def on_submit(self, interaction: Interaction):
        """Handles the submission of the modal."""
        logger.info(f"Modal submitted by user {self.user_id} in guild {self.guild_id}")
        await interaction.response.defer(ephemeral=True, thinking=True)

        display_name = self.display_name_input.value.strip()
        banner_color = self.banner_color_input.value.strip() or None
        errors = []
        valid_banner_color = None
        if banner_color:
            if not is_valid_hex_color(banner_color):
                errors.append("Invalid Banner Color format provided (e.g., 00FF29). Color was ignored.")
            else:
                valid_banner_color = f"#{banner_color}" if not banner_color.startswith("#") else banner_color

        # Prepare data
        data = {
            'guild_id': self.guild_id,
            'user_id': self.user_id,
            'display_name': display_name[:100] if display_name else interaction.user.display_name,
            'image_path': self.image_path
        }
        if valid_banner_color:
            data['banner_color'] = valid_banner_color

        # Database operation
        db_success = False
        response_message = ""
        try:
            # Check for existing row
            sql_check = "SELECT 1 FROM cappers WHERE guild_id = %s AND user_id = %s"
            exists = await db_manager.fetch_one(sql_check, (self.guild_id, self.user_id))

            if exists:
                # Update existing row
                update_fields = [f"{k} = %s" for k in data.keys() if k not in ('guild_id', 'user_id')]
                update_sql = f"UPDATE cappers SET {', '.join(update_fields)} WHERE guild_id = %s AND user_id = %s"
                update_values = [data[k] for k in data.keys() if k not in ('guild_id', 'user_id')] + [self.guild_id, self.user_id]
                rows_affected = await db_manager.execute(update_sql, update_values)
                logger.info(f"Updated capper row for user {self.user_id} in guild {self.guild_id}. Rows affected: {rows_affected}")
                response_message += "**Profile Updated:**\n"
            else:
                # Insert new row
                columns = list(data.keys())
                placeholders = ', '.join(['%s'] * len(columns))
                columns_str = ', '.join(columns)
                insert_sql = f"INSERT INTO cappers ({columns_str}) VALUES ({placeholders})"
                rows_affected = await db_manager.execute(insert_sql, tuple(data.values()))
                logger.info(f"Inserted new capper row for user {self.user_id} in guild {self.guild_id}. Rows affected: {rows_affected}")
                response_message += "**Profile Created:**\n"

            db_success = True
            response_message += "\n".join([f"- {key.replace('_', ' ').title()}: {data[key]}" for key in data])
        except DatabaseError as e:
            logger.error(f"DB error processing capper for user {self.user_id}: {e}", exc_info=True)
            errors.append("Failed to save profile data.")
        except Exception as e:
            logger.error(f"Unexpected error processing capper for user {self.user_id}: {e}", exc_info=True)
            errors.append("Unexpected error saving profile data.")

        if not db_success:
            response_message += "**Failed to save profile.**\n"

        if errors:
            response_message += "\n**Notes:**\n- " + "\n- ".join(errors)

        await interaction.followup.send(response_message, ephemeral=True)

async def handle_setid_command(interaction: Interaction, attachment: Attachment):
    """Handles the /setid command with a required image attachment."""
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    logger.info(f"Processing /setid for user {user_id} in guild {guild_id}")

    if not guild_id:
        logger.error(f"Missing guild ID for user {user_id}.")
        await interaction.response.send_message("Error: This command must be used in a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    errors = []
    image_path = None
    valid_extensions = {'.png', '.jpg', '.jpeg'}
    ext = Path(attachment.filename).suffix.lower()
    if ext not in valid_extensions:
        errors.append("Invalid file type. Please upload a PNG or JPEG image.")
    else:
        try:
            timestamp = int(datetime.utcnow().timestamp())
            file_path = IMAGE_SAVE_PATH / f"{user_id}_{guild_id}_{timestamp}{ext}"
            await attachment.save(file_path)
            logger.info(f"Saved profile image for user {user_id} to {file_path}")
            image_path = str(file_path)
        except Exception as e:
            logger.error(f"Failed to save image for user {user_id}: {e}", exc_info=True)
            errors.append("Failed to save profile image.")

    if not image_path:
        error_msg = "Could not process the image upload."
        if errors:
            error_msg += "\nIssues:\n- " + "\n- ".join(errors)
        await interaction.followup.send(error_msg, ephemeral=True)
        return

    try:
        view = ModalButton(user_id=user_id, image_path=image_path, guild_id=guild_id)
        await interaction.followup.send(
            "Your image has been saved. Click the button below to complete your profile setup.",
            view=view,
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Failed to send modal button to user {user_id}: {e}", exc_info=True)
        await interaction.followup.send("An error occurred while setting up the profile form.", ephemeral=True)
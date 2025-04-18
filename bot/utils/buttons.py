import logging
import discord
from discord import Interaction
from discord.ui import Button
from typing import Optional

logger = logging.getLogger(__name__)

class CancelButton(Button):
    def __init__(self, row: Optional[int] = None):
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel_bet_setup", row=row)

    async def callback(self, interaction: Interaction):
        view = self.view
        if interaction.user.id != view.original_interaction.user.id:
            await interaction.response.send_message("You cannot cancel someone else's bet setup.", ephemeral=True)
            return
        logger.info(f"Bet setup cancelled by {interaction.user.id} for bet serial {view.bet_serial}")
        if not interaction.response.is_done():
            try:
                await interaction.response.edit_message(content="*Bet setup cancelled.*", view=None, embed=None)
            except discord.NotFound:
                logger.warning(f"Original interaction message not found on cancel for bet {view.bet_serial}.")
            except discord.HTTPException as e:
                logger.error(f"HTTPException editing message on cancel for bet {view.bet_serial}: {e}")
            except Exception as e:
                logger.error(f"Error editing message on cancel for bet {view.bet_serial}: {e}", exc_info=True)
                if not interaction.response.is_done():
                    try:
                        await interaction.followup.send("*Bet setup cancelled.*", ephemeral=True)
                    except Exception as followup_e:
                        logger.warning(f"Failed followup on cancel: {followup_e}")
        view.stop()
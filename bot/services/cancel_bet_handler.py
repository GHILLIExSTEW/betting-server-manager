import logging
import discord
from discord import Interaction, SelectOption
from discord.ui import View, Select
from typing import List, Dict

from bot.data.db_manager import db_manager
from bot.utils.errors import DatabaseError
from bot.utils.buttons import CancelButton

logger = logging.getLogger(__name__)

class SelectBetView(View):
    def __init__(self, interaction: Interaction, bets: List[Dict], bet_service: 'BetService', timeout=180):
        super().__init__(timeout=timeout)
        self.original_interaction = interaction
        self.bet_service = bet_service
        self.add_item(BetSelect(bets))
        self.add_item(CancelButton())

    async def on_timeout(self):
        logger.info(f"Bet selection timed out for user {self.original_interaction.user.id}")
        try:
            await self.original_interaction.edit_original_response(content="Bet selection timed out.", view=None, embed=None)
        except discord.NotFound:
            logger.warning("Original interaction message not found on timeout.")
        except discord.HTTPException as e:
            logger.error(f"HTTPException editing message on timeout: {e}")
        self.stop()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message("This isn't your selection!", ephemeral=True)
            return False
        return True

class BetSelect(Select):
    def __init__(self, bets: List[Dict]):
        options = []
        for bet in bets[:25]:  # Discord limits to 25 options
            serial = bet.get('bet_serial')
            team = bet.get('team', 'Unknown')
            opponent = bet.get('opponent', 'Unknown')
            label = f"#{serial}: {team} vs {opponent}"[:100]  # Discord label limit
            options.append(SelectOption(label=label, value=str(serial)))
        if not options:
            options.append(SelectOption(label="No bets found", value="none"))
        super().__init__(placeholder="Select a bet to cancel...", options=options, custom_id="bet_select")

    async def callback(self, interaction: Interaction):
        view: SelectBetView = self.view
        if self.values[0] == "none":
            await interaction.response.edit_message(content="No bets available to cancel.", view=None)
            view.stop()
            return
        bet_serial = int(self.values[0])
        logger.info(f"User {interaction.user.id} selected bet {bet_serial} to cancel")
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            guild_id = interaction.guild_id
            user_id = interaction.user.id

            # Verify bet ownership
            bet_query = """
                SELECT user_id, message_id
                FROM bets
                WHERE bet_serial = %s AND guild_id = %s
            """
            bet_record = await db_manager.fetch_one(bet_query, (bet_serial, guild_id))
            if not bet_record:
                await interaction.followup.send(f"Bet #{bet_serial} not found.", ephemeral=True)
                view.stop()
                return

            if bet_record['user_id'] != user_id and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("You can only cancel your own bets unless you're an admin.", ephemeral=True)
                view.stop()
                return

            # Delete from bets
            bet_delete_query = """
                DELETE FROM bets
                WHERE bet_serial = %s AND guild_id = %s
            """
            await db_manager.execute(bet_delete_query, (bet_serial, guild_id))

            # Delete from unit_records
            unit_delete_query = """
                DELETE FROM unit_records
                WHERE guild_id = %s AND embed_id = %s
            """
            await db_manager.execute(unit_delete_query, (guild_id, bet_record['message_id']))

            # Update cappers (decrement bet counts if necessary)
            cappers_update_query = """
                UPDATE cappers
                SET bet_won = GREATEST(bet_won - (SELECT bet_won FROM bets WHERE bet_serial = %s), 0),
                    bet_loss = GREATEST(bet_loss - (SELECT bet_loss FROM bets WHERE bet_serial = %s), 0)
                WHERE guild_id = %s AND user_id = %s
            """
            await db_manager.execute(cappers_update_query, (bet_serial, bet_serial, guild_id, user_id))

            # Remove from pending_bets
            if bet_record['message_id'] in view.bet_service.pending_bets:
                del view.bet_service.pending_bets[bet_record['message_id']]

            await interaction.followup.send(f"Bet #{bet_serial} and all associated records canceled successfully.", ephemeral=True)
            await view.original_interaction.edit_original_response(content=f"Bet #{bet_serial} canceled.", view=None)
            view.stop()

        except DatabaseError as e:
            logger.error(f"Database error canceling bet {bet_serial}: {e}", exc_info=True)
            await interaction.followup.send("A database error occurred while canceling the bet.", ephemeral=True)
            view.stop()
        except Exception as e:
            logger.error(f"Unexpected error canceling bet {bet_serial}: {e}", exc_info=True)
            await interaction.followup.send("An unexpected error occurred while canceling the bet.", ephemeral=True)
            view.stop()

async def cancel_bet_command_handler(interaction: Interaction, bet_service: 'BetService'):
    """Handles the /cancel_bet command with a dropdown for bet selection."""
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    logger.debug(f"Deferred /cancel_bet interaction for user {interaction.user.id}")

    try:
        query = """
            SELECT bet_serial, team, opponent
            FROM bets
            WHERE guild_id = %s AND user_id = %s
            AND bet_won IS NULL AND bet_loss IS NULL
            ORDER BY bet_serial DESC
        """
        bets = await db_manager.fetch(query, (interaction.guild_id, interaction.user.id))

        if not bets:
            await interaction.followup.send("You have no pending bets to cancel.", ephemeral=True)
            return

        view = SelectBetView(interaction, bets, bet_service)
        await interaction.followup.send("Select a bet to cancel:", view=view, ephemeral=True)

    except DatabaseError as e:
        logger.error(f"Database error fetching bets for user {interaction.user.id}: {e}", exc_info=True)
        await interaction.followup.send("A database error occurred while fetching your bets.", ephemeral=True)
    except Exception as e:
        logger.error(f"Unexpected error in /cancel_bet for user {interaction.user.id}: {e}", exc_info=True)
        await interaction.followup.send("An unexpected error occurred while processing the command.", ephemeral=True)
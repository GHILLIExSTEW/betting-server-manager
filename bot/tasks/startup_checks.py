# Modified content for bot/tasks/startup_checks.py
# Fixes SyntaxError caused by invalid comment style.

"""
Contains tasks to run once on bot startup to reconcile bet states
and ensure data integrity between bets and unit_records tables based on specific rules.
"""
import logging
import asyncio
import aiomysql
from datetime import datetime, timedelta, timezone
from decimal import Decimal # Import Decimal for accuracy

# Import custom errors
from bot.utils.errors import DatabaseError, DatabaseQueryError

logger = logging.getLogger(__name__)

async def run_startup_checks(bot):
    """
    Runs startup checks for pending and resolved bets according to specific reconciliation logic.
    """
    logger.info("Running startup checks (Logic Update 2025-04-15 v3 - FINAL)...")
    if not bot.db_manager or not bot.db_manager._pool or bot.db_manager._pool.closed:
         logger.error("Startup checks cannot run: DB Manager not connected.")
         return

    await _load_pending_bets_and_create_units_placeholder(bot)
    await _reconcile_resolved_units_column(bot)
    logger.info("Startup checks completed.")

async def _load_pending_bets_and_create_units_placeholder(bot):
    """
    Loads pending bets (won=0, loss=0) from DB, populates BetService.pending_bets,
    checks for ✅/❌ reactions in embed channels from server_settings,
    updates bets and unit_records using guild_id and bet_serial.
    """
    logger.info("Checking for pending bets (0/0) missing unit records (will insert units=0, total=0)...")
    count_loaded = 0
    count_created = 0
    count_resolved_by_reaction = 0
    count_skipped = 0
    if not hasattr(bot, 'bet_service') or not hasattr(bot.bet_service, 'pending_bets'):
        logger.error("BetService or pending_bets dictionary not found on bot instance.")
        return

    bot.bet_service.pending_bets.clear()

    try:
        # Create placeholders for missing unit_records
        query_missing_check = """
            SELECT b.bet_serial, b.message_id, b.user_id, b.guild_id
            FROM bets b
            LEFT JOIN unit_records ur ON b.bet_serial = ur.bet_serial AND b.guild_id = ur.guild_id
            WHERE b.bet_won = 0
              AND b.bet_loss = 0
              AND b.message_id IS NOT NULL
              AND ur.id IS NULL
        """
        missing_records = await bot.db_manager.fetch(query_missing_check)

        if missing_records:
            logger.info(f"Found {len(missing_records)} pending bets (0/0) missing unit_records. Creating placeholders...")
            for record in missing_records:
                bet_serial = record.get('bet_serial')
                user_id = record.get('user_id')
                guild_id = record.get('guild_id')

                if not all([bet_serial, user_id, guild_id]):
                    logger.warning(f"Cannot create unit_record placeholder for bet_serial {bet_serial}: missing data")
                    count_skipped += 1
                    continue

                try:
                    insert_query = """
                        INSERT INTO unit_records
                        (guild_id, bet_serial, user_id, units, timestamp, total)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                        ON DUPLICATE KEY UPDATE bet_serial=bet_serial
                    """
                    insert_params = (guild_id, bet_serial, user_id, Decimal("0.00"), Decimal("0.00"))
                    await bot.db_manager.execute(insert_query, insert_params)
                    count_created += 1
                    logger.info(f"Created missing unit_record placeholder for pending bet {bet_serial}.")
                except Exception as unit_create_err:
                    logger.error(f"Error creating unit_record for bet {bet_serial}: {unit_create_err}", exc_info=True)
                    count_skipped += 1

        else:
            logger.info("No pending bets (0/0) found missing unit records.")

        # Load pending bets and check reactions in embed channels
        all_pending_query = """
            SELECT bet_serial, message_id, guild_id, user_id, units
            FROM bets
            WHERE bet_won = 0 AND bet_loss = 0 AND message_id IS NOT NULL
        """
        all_pending_results = await bot.db_manager.fetch(all_pending_query)

        for record in all_pending_results:
            message_id = record.get('message_id')
            bet_serial = record.get('bet_serial')
            guild_id = record.get('guild_id')
            user_id = record.get('user_id')
            units_risked = Decimal(record.get('units', '0.00')).copy_abs()

            if not all([message_id, bet_serial, guild_id, user_id]):
                logger.warning(f"Skipping bet {bet_serial}: missing data: {record}")
                count_skipped += 1
                continue

            try:
                msg_id_int = int(message_id)
                serial_int = int(bet_serial)

                # Fetch guild
                guild = bot.get_guild(int(guild_id))
                if not guild:
                    try:
                        guild = await bot.fetch_guild(int(guild_id))
                        logger.info(f"Fetched guild {guild_id} via API for bet {bet_serial}")
                    except Exception as guild_err:
                        logger.warning(f"Guild {guild_id} not found for bet {bet_serial}: {guild_err}")
                        count_skipped += 1
                        bot.bet_service.pending_bets[msg_id_int] = serial_int
                        count_loaded += 1
                        continue

                # Get embed channels from server_settings
                settings_query = """
                    SELECT embed_channel_1, embed_channel_2
                    FROM server_settings
                    WHERE guild_id = %s
                    LIMIT 1
                """
                settings = await bot.db_manager.fetch_one(settings_query, (guild_id,))
                if not settings or not any([settings.get('embed_channel_1'), settings.get('embed_channel_2')]):
                    logger.warning(f"No embed channels found in server_settings for guild {guild_id}, bet {bet_serial}")
                    count_skipped += 1
                    bot.bet_service.pending_bets[msg_id_int] = serial_int
                    count_loaded += 1
                    continue

                embed_channels = [settings.get('embed_channel_1'), settings.get('embed_channel_2')]
                embed_channels = [ch for ch in embed_channels if ch]  # Remove None/empty

                # Check message in embed channels
                message = None
                for channel_id in embed_channels:
                    try:
                        channel = guild.get_channel(int(channel_id))
                        if not channel:
                            channel = await guild.fetch_channel(int(channel_id))
                            logger.info(f"Fetched channel {channel_id} for bet {bet_serial}")
                        message = await channel.fetch_message(msg_id_int)
                        logger.debug(f"Found message {msg_id_int} in channel {channel_id} for bet {bet_serial}")
                        break
                    except Exception:
                        continue  # Message not in this channel; try next

                if not message:
                    logger.warning(f"Message {msg_id_int} not found in embed channels {embed_channels} of guild {guild_id} for bet {bet_serial}")
                    count_skipped += 1
                    bot.bet_service.pending_bets[msg_id_int] = serial_int
                    count_loaded += 1
                    continue

                # Check reactions
                reaction_status = None
                for reaction in message.reactions:
                    if str(reaction.emoji) == "✅":
                        reaction_status = "win"
                        break
                    elif str(reaction.emoji) == "❌":
                        reaction_status = "loss"
                        break

                if reaction_status:
                    # Update bets table
                    try:
                        update_bet_query = """
                            UPDATE bets
                            SET bet_won = %s, bet_loss = %s
                            WHERE bet_serial = %s AND guild_id = %s
                        """
                        bet_won = 1 if reaction_status == "win" else 0
                        bet_loss = 1 if reaction_status == "loss" else 0
                        await bot.db_manager.execute(update_bet_query, (bet_won, bet_loss, bet_serial, guild_id))
                        logger.info(f"Updated bet {bet_serial} to {reaction_status} based on reaction")

                        # Update or create unit_records using guild_id and bet_serial
                        expected_units = units_risked if reaction_status == "win" else -units_risked
                        unit_query = """
                            SELECT id, units FROM unit_records
                            WHERE bet_serial = %s AND guild_id = %s LIMIT 1
                        """
                        unit_record = await bot.db_manager.fetch_one(unit_query, (bet_serial, guild_id))

                        if unit_record:
                            update_unit_query = """
                                UPDATE unit_records
                                SET units = %s
                                WHERE bet_serial = %s AND guild_id = %s
                            """
                            await bot.db_manager.execute(update_unit_query, (expected_units, bet_serial, guild_id))
                            logger.info(f"Updated unit_record for bet {bet_serial}: units={expected_units}")
                        else:
                            insert_unit_query = """
                                INSERT INTO unit_records
                                (guild_id, bet_serial, user_id, units, timestamp, total)
                                VALUES (%s, %s, %s, %s, NOW(), %s)
                            """
                            await bot.db_manager.execute(insert_unit_query, (guild_id, bet_serial, user_id, expected_units, Decimal("0.00")))
                            logger.info(f"Created unit_record for bet {bet_serial}: units={expected_units}")

                        count_resolved_by_reaction += 1
                    except Exception as update_err:
                        logger.error(f"Error updating bet {bet_serial} status: {update_err}", exc_info=True)
                        bot.bet_service.pending_bets[msg_id_int] = serial_int
                        count_loaded += 1
                else:
                    # No relevant reaction; keep as pending
                    bot.bet_service.pending_bets[msg_id_int] = serial_int
                    count_loaded += 1

            except (ValueError, TypeError):
                logger.warning(f"Skipping invalid bet record: msg_id='{message_id}', serial='{bet_serial}'")
                count_skipped += 1
                continue

        logger.info(f"Loaded {count_loaded} pending bets into memory. Created {count_created} missing placeholder unit records. Resolved {count_resolved_by_reaction} bets by reaction. Skipped {count_skipped} bets.")

    except DatabaseQueryError as e:
        logger.error(f"DB query error loading pending bets/units: {e}", exc_info=True)
    except DatabaseError as e:
        logger.error(f"DB error loading pending bets/units: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error loading pending bets/units: {e}", exc_info=True)


async def _reconcile_resolved_units_column(bot):
    """
    Checks ALL resolved bets (bet_won=1 or bet_loss=1).
    If unit_record exists AND units=0, updates 'units' column to +/- risked amount.
    If unit_record is MISSING, creates it with 'units' = +/- risked amount and total=0.
    Does NOT modify the 'total' column for existing records in this script.
    """
    logger.info("Reconciling 'units' column for ALL resolved bets (Create if Missing, Update if Exists AND units=0)...")
    count_updated = 0
    count_created_resolved = 0
    count_missing_critical_data = 0
    try:
        query_resolved = "SELECT bet_serial, units, odds, bet_won, bet_loss, user_id, guild_id, message_id FROM bets WHERE (bet_won = 1 OR bet_loss = 1)"
        resolved_bets = await bot.db_manager.fetch(query_resolved)

        if not resolved_bets: logger.info("No resolved bets (status 1/0 or 0/1) found to reconcile."); return
        logger.info(f"Found {len(resolved_bets)} resolved bets to check/reconcile.")

        for bet in resolved_bets:
            bet_serial = bet.get('bet_serial')
            units_risked_dec = Decimal(bet.get('units', '0.00')).copy_abs()
            bet_won = bet.get('bet_won'); bet_loss = bet.get('bet_loss')
            user_id = bet.get('user_id'); guild_id = bet.get('guild_id')
            # message_id = bet.get('message_id') # Not used in insert below currently

            if not all([bet_serial, units_risked_dec is not None, user_id, guild_id]):
                logger.warning(f"Skipping reconciliation for bet {bet_serial}: missing essential data."); count_missing_critical_data += 1; continue

            try:
                expected_units_val = Decimal("0.00")
                if bet_won == 1: expected_units_val = units_risked_dec
                elif bet_loss == 1: expected_units_val = -units_risked_dec

                unit_query = "SELECT id, units FROM unit_records WHERE bet_serial = %s AND guild_id = %s AND user_id = %s LIMIT 1"
                unit_record = await bot.db_manager.fetch_one(unit_query, (bet_serial, guild_id, user_id))

                if unit_record: # Record EXISTS
                    record_id = unit_record.get('id')
                    current_units_raw = unit_record.get('units')
                    current_units = Decimal(current_units_raw if current_units_raw is not None else '0.00')

                    if record_id is None: logger.error(f"Could not retrieve 'id' for existing unit_record of bet {bet_serial}. Cannot update."); continue

                    # Only update if current units is 0
                    if abs(current_units) < Decimal("0.001"):
                        if expected_units_val != Decimal("0.00"):
                             logger.warning(f"Unit record 'units' is 0 for resolved bet {bet_serial} (ID: {record_id}). Updating to expected {expected_units_val}...")
                             update_query = "UPDATE unit_records SET units = %s WHERE guild_id = %s AND id = %s"
                             update_params = (expected_units_val, guild_id, record_id)
                             await bot.db_manager.execute(update_query, update_params)
                             count_updated += 1
                             logger.info(f"Reconciled unit_record 'units' (ID: {record_id}, Guild: {guild_id}) for bet {bet_serial}. Set units={expected_units_val}")
                    # else: logger.debug(f"Unit record units for resolved bet {bet_serial} is already non-zero ({current_units}). Skipping update.")

                else: # Record is MISSING for a RESOLVED bet
                    logger.error(f"Unit_record missing for RESOLVED bet {bet_serial}! Creating entry with resolved units={expected_units_val}, total=0...")

                    # Assuming no embed_id column used in unit_records
                    insert_query = """
                        INSERT INTO unit_records
                        (guild_id, bet_serial, user_id, units, timestamp, total /*, embed_id */)
                        VALUES (%s, %s, %s, %s, NOW(), %s /*, %s */)
                    """
                     # --- SYNTAX FIX: Removed invalid comment ---
                    insert_params = (guild_id, bet_serial, user_id, expected_units_val, Decimal("0.00"))
                    # --- END FIX ---

                    await bot.db_manager.execute(insert_query, insert_params)
                    count_created_resolved += 1
                    logger.info(f"Created missing unit_record for resolved bet {bet_serial} (Units: {expected_units_val}, Total: 0.00)")

            except Exception as unit_check_err:
                logger.error(f"Error checking/reconciling unit_record for resolved bet {bet_serial}: {unit_check_err}", exc_info=True)

        logger.info(f"Checked resolved unit records. Updated {count_updated} entries where units were 0. Created {count_created_resolved} missing records for resolved bets.")
        if count_missing_critical_data > 0: logger.warning(f"Skipped {count_missing_critical_data} resolved bets during reconciliation due to missing data in bets table.")

    except DatabaseQueryError as e: logger.error(f"DB query error reconciling resolved units column: {e}", exc_info=True)
    except DatabaseError as e: logger.error(f"DB error reconciling resolved units column: {e}", exc_info=True)
    except Exception as e: logger.error(f"Unexpected error reconciling resolved units column: {e}", exc_info=True)
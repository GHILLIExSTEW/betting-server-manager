# Filename: bot/services/load_logos_handler.py

import discord
from discord import Interaction, Attachment
import logging
import csv
import io
import asyncio

# Import necessary components from your project
from bot.data.db_manager import db_manager # Assuming db_manager is initialized and ready
from bot.utils.image_utils.helpers import fetch_image # Helper to fetch image from URL
from bot.utils.image_utils.logo_sync import sync_logos_from_db # Function to trigger sync
from bot.utils.errors import DatabaseError # Assuming you have custom DB errors

logger = logging.getLogger(__name__)

# Your User ID for permission check
OWNER_USER_ID = 761388542965448767

async def load_logos_command_handler(interaction: Interaction, file: Attachment):
    """Handles the logic for the /load_logos command."""

    # 1. Permission Check
    if interaction.user.id != OWNER_USER_ID:
        logger.warning(f"User {interaction.user.id} attempted to use /load_logos without permission.")
        await interaction.response.send_message("Error: You do not have permission to use this command.", ephemeral=True)
        return

    # 2. Defer Response (ephemeral so only user sees progress)
    await interaction.response.defer(ephemeral=True, thinking=True)

    # 3. File Validation
    if not file:
        await interaction.followup.send("Error: No file attached.", ephemeral=True)
        return
    if not file.content_type or not file.content_type.startswith('text/csv'):
        await interaction.followup.send(f"Error: Invalid file type ('{file.content_type}'). Please upload a CSV file.", ephemeral=True)
        return

    logger.info(f"Processing logo CSV upload '{file.filename}' initiated by user {interaction.user.id}.")

    # Statistics counters
    processed_rows = 0
    success_count = 0
    fetch_errors = 0
    db_errors = 0
    skipped_rows = 0
    other_errors = 0

    # 4. Read and Process CSV
    try:
        csv_data = await file.read()
        csv_content = csv_data.decode('utf-8')
        csvfile = io.StringIO(csv_content)
        # Define expected headers (case-insensitive check later)
        expected_headers = ['league', 'conference', 'team', 'car', 'first_name', 'last_name', 'logo_url']
        reader = csv.DictReader(csvfile)

        # Validate headers (case-insensitive)
        actual_headers_lower = {h.lower().strip() for h in reader.fieldnames} if reader.fieldnames else set()
        expected_headers_lower = {h.lower() for h in expected_headers}
        if not expected_headers_lower.issubset(actual_headers_lower):
             missing = expected_headers_lower - actual_headers_lower
             await interaction.followup.send(f"Error: CSV is missing required headers: {', '.join(missing)}", ephemeral=True)
             return

        # Prepare DB connection outside the loop if needed by your db_manager
        # await db_manager.connect() # Depending on your db_manager implementation

        for row_num, row_raw in enumerate(reader, start=1):
            processed_rows += 1
            # Normalize keys (lowercase, strip whitespace) and get values
            row = {k.lower().strip(): v.strip() if isinstance(v, str) else v for k, v in row_raw.items()}

            try:
                # Extract data, providing defaults for potentially missing/empty values
                league = row.get('league')
                conference = row.get('conference') or None # Use None if empty/missing
                team = row.get('team') or None
                car = row.get('car') or None
                first_name = row.get('first_name') or None
                last_name = row.get('last_name') or None
                logo_url = row.get('logo_url')

                # Basic validation
                if not league:
                    logger.warning(f"Skipping row {row_num}: Missing required 'league'.")
                    skipped_rows += 1
                    continue
                if not logo_url:
                    logger.warning(f"Skipping row {row_num}: Missing required 'logo_url' for league '{league}'.")
                    skipped_rows += 1
                    continue

                # Determine entity type for DB query (simple heuristic)
                is_person = first_name and last_name
                is_team = team and not is_person # Assume team if team name exists and it's not identified as a person
                entity_name_for_log = f"{first_name} {last_name}" if is_person else team if is_team else "Unknown Entity"

                # 5. Fetch Image Blob
                image_blob = await fetch_image(logo_url)
                if image_blob is None:
                    logger.warning(f"Skipping row {row_num}: Failed to fetch image from URL '{logo_url}' for {league}/{entity_name_for_log}.")
                    fetch_errors += 1
                    continue

                # 6. Database Upsert (Replace/Update)
                # IMPORTANT: This query structure is specific to MySQL/MariaDB's
                # INSERT ... ON DUPLICATE KEY UPDATE syntax.
                # It also ASSUMES specific unique keys exist on your table:
                # - UNIQUE KEY `uq_team` (`league`, `team`) WHERE team IS NOT NULL
                # - UNIQUE KEY `uq_person` (`league`, `first_name`, `last_name`) WHERE first_name IS NOT NULL AND last_name IS NOT NULL
                # Adjust the query and keys based on your actual DB schema and engine!
                # This example tries to insert/update based on detected type, nullifying irrelevant columns.

                # NOTE: Using COALESCE in the query might be better for handling NULLs in keys if supported.
                # The current approach uses separate INSERT statements based on type, which might be simpler
                # if your table structure allows NULLs appropriately.

                query = None
                params = None

                # Build query based on identified entity type
                if is_person:
                     # Assume unique key on (league, first_name, last_name)
                     query = """
                        INSERT INTO league_teams_logos (league, conference, team, car, first_name, last_name, logo_image)
                        VALUES (%s, %s, NULL, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            conference=VALUES(conference),
                            team=NULL,
                            car=VALUES(car),
                            logo_image=VALUES(logo_image)
                     """
                     params = (league, conference, car, first_name, last_name, image_blob)
                elif is_team:
                     # Assume unique key on (league, team)
                     query = """
                        INSERT INTO league_teams_logos (league, conference, team, car, first_name, last_name, logo_image)
                        VALUES (%s, %s, %s, NULL, NULL, NULL, %s)
                        ON DUPLICATE KEY UPDATE
                            conference=VALUES(conference),
                            car=NULL,
                            first_name=NULL,
                            last_name=NULL,
                            logo_image=VALUES(logo_image)
                     """
                     params = (league, conference, team, image_blob)
                else:
                     # Handle cases where it's neither a clear person nor team (e.g., league logo only?)
                     # This might need specific handling based on your CSV conventions.
                     # Maybe update based on league only? Assumes a row exists for the league logo.
                     # Example: Update logo for a league based on league name only
                     # query = "UPDATE league_teams_logos SET logo_image = %s WHERE league = %s AND team IS NULL AND first_name IS NULL AND last_name IS NULL"
                     # params = (image_blob, league)
                     # Or Insert if league logo row might not exist (needs unique key on league with NULLs for others)
                      logger.warning(f"Skipping row {row_num}: Cannot determine clear entity type (Team or Person) for league '{league}'.")
                      skipped_rows += 1
                      continue # Skip if type is unclear

                # Execute DB operation
                try:
                    await db_manager.execute(query, params)
                    success_count += 1
                    # logger.debug(f"Successfully processed row {row_num} for {league}/{entity_name_for_log}")
                except DatabaseError as db_e:
                    logger.error(f"Database error on row {row_num} ({league}/{entity_name_for_log}): {db_e}", exc_info=True)
                    db_errors += 1
                except Exception as db_e_other:
                    logger.error(f"Unexpected database error on row {row_num} ({league}/{entity_name_for_log}): {db_e_other}", exc_info=True)
                    db_errors += 1

            except KeyError as e:
                logger.warning(f"Skipping row {row_num}: Missing expected column header '{e}'.")
                skipped_rows += 1
            except Exception as row_err:
                logger.error(f"Error processing row {row_num}: {row_err}", exc_info=True)
                other_errors += 1

        # await db_manager.close() # Close connection if opened earlier

        # Log overall results before sync
        logger.info(f"CSV '{file.filename}' processing complete. Total: {processed_rows}, Success: {success_count}, Skipped: {skipped_rows}, Fetch Errors: {fetch_errors}, DB Errors: {db_errors}, Other Errors: {other_errors}.")

        # 7. Trigger Sync Function
        sync_status = "Sync not attempted."
        if success_count > 0 or db_errors > 0: # Trigger sync if any potential changes were made or attempted
            try:
                logger.info("Triggering logo synchronization (sync_logos_from_db)...")
                await sync_logos_from_db()
                sync_status = "Sync function completed successfully."
                logger.info("Logo synchronization finished.")
            except Exception as sync_err:
                sync_status = f"Sync function failed: {sync_err}"
                logger.error(f"Error during sync_logos_from_db execution: {sync_err}", exc_info=True)
        else:
             sync_status = "Sync skipped (no successful DB operations)."


        # 8. Report Results to User
        await interaction.followup.send(
            f"**Logo Upload Results for '{file.filename}':**\n"
            f"- Rows Processed: {processed_rows}\n"
            f"- Successfully Saved/Updated: {success_count}\n"
            f"- Rows Skipped (Missing Data): {skipped_rows}\n"
            f"- Image Fetch Errors: {fetch_errors}\n"
            f"- Database Save Errors: {db_errors}\n"
            f"- Other Row Errors: {other_errors}\n\n"
            f"**Sync Status:** {sync_status}",
            ephemeral=True
        )

    except UnicodeDecodeError:
        logger.error(f"Failed to decode file '{file.filename}' as UTF-8.")
        await interaction.followup.send("Error: Could not read the file. Please ensure it is UTF-8 encoded.", ephemeral=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during /load_logos handling: {e}", exc_info=True)
        await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)
    # finally:
        # Ensure DB connection is closed if managed here
        # await db_manager.close()
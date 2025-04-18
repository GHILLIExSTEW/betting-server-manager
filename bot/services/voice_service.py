import asyncio
import logging
import discord
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from calendar import monthrange

from data.db_manager import db_manager
from data.cache_manager import cache_manager

logger = logging.getLogger(__name__)

class VoiceService:
    """Service for managing Discord voice channel updates."""
    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self._update_task: Optional[asyncio.Task] = None
        self._monthly_total_task: Optional[asyncio.Task] = None
        self._yearly_total_task: Optional[asyncio.Task] = None  # New task for yearly updates

    async def start(self) -> None:
        """Start the voice channel update, monthly total, and yearly total loops."""
        if not self.running:
            self.running = True
            if self._update_task is None or self._update_task.done():
                self._update_task = asyncio.create_task(self._update_loop())
                logger.info("Voice service update loop started.")
            if self._monthly_total_task is None or self._monthly_total_task.done():
                self._monthly_total_task = asyncio.create_task(self._monthly_total_loop())
                logger.info("Monthly total update loop started.")
            if self._yearly_total_task is None or self._yearly_total_task.done():
                self._yearly_total_task = asyncio.create_task(self._yearly_total_loop())
                logger.info("Yearly total update loop started.")
            logger.info("Voice service started.")

    async def stop(self) -> None:
        """Stop the service."""
        self.running = False
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            logger.info("Voice service update task cancelled.")
        if self._monthly_total_task and not self._monthly_total_task.done():
            self._monthly_total_task.cancel()
            logger.info("Monthly total update task cancelled.")
        if self._yearly_total_task and not self._yearly_total_task.done():
            self._yearly_total_task.cancel()
            logger.info("Yearly total update task cancelled.")
        logger.info("Voice service stopped.")

    async def _get_current_month_units(self, guild: discord.Guild) -> float:
        """Get the total units for the current month from unit_records.units."""
        query = """
            SELECT SUM(units) as total_monthly_units
            FROM unit_records
            WHERE guild_id = %s
              AND MONTH(timestamp) = MONTH(CURDATE())
              AND YEAR(timestamp) = YEAR(CURDATE())
        """
        try:
            result = await db_manager.fetch_one(query, (guild.id,))
            total_units = float(result.get('total_monthly_units', 0.0) or 0.0)
            logger.debug(f"Fetched current month units for guild {guild.id}: {total_units:.2f}")
            return total_units
        except Exception as e:
            logger.error(f"Failed to get current month units for guild {guild.id}: {e}", exc_info=True)
            return 0.00

    async def _get_yearly_units(self, guild: discord.Guild) -> float:
        """Get the total units for the current year from unit_records.total."""
        query = """
            SELECT SUM(total) as yearly_units
            FROM unit_records
            WHERE guild_id = %s
              AND YEAR(timestamp) = YEAR(CURDATE())
        """
        try:
            result = await db_manager.fetch_one(query, (guild.id,))
            total_units = float(result.get('yearly_units', 0.0) or 0.0)
            logger.debug(f"Fetched yearly units for guild {guild.id}: {total_units:.2f}")
            return total_units
        except Exception as e:
            logger.error(f"Failed to get yearly units for guild {guild.id}: {e}", exc_info=True)
            return 0.00

    async def _calculate_monthly_total(self, guild: discord.Guild, year: int, month: int) -> float:
        """Calculate the total units for a specific month and guild."""
        query = """
            SELECT SUM(units) as monthly_total
            FROM unit_records
            WHERE guild_id = %s
              AND YEAR(timestamp) = %s
              AND MONTH(timestamp) = %s
        """
        try:
            result = await db_manager.fetch_one(query, (guild.id, year, month))
            total_units = float(result.get('monthly_total', 0.0) or 0.0)
            logger.debug(f"Calculated monthly total for guild {guild.id}, {year}-{month:02d}: {total_units:.2f}")
            return total_units
        except Exception as e:
            logger.error(f"Failed to calculate monthly total for guild {guild.id}, {year}-{month:02d}: {e}", exc_info=True)
            return 0.00

    async def _update_monthly_total(self, guild: discord.Guild, year: int, month: int) -> None:
        """Update the total column of the last unit_records row for the month."""
        query = """
            SELECT id, total
            FROM unit_records
            WHERE guild_id = %s
              AND YEAR(timestamp) = %s
              AND MONTH(timestamp) = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        try:
            result = await db_manager.fetch_one(query, (guild.id, year, month))
            if not result:
                logger.warning(f"No unit_records found for guild {guild.id} in {year}-{month:02d}. Skipping total update.")
                return

            record_id = result.get('id')
            current_total = result.get('total')
            if current_total is None or float(current_total) == 0.0:
                monthly_total = await self._calculate_monthly_total(guild, year, month)
                update_query = """
                    UPDATE unit_records
                    SET total = %s
                    WHERE id = %s
                """
                await db_manager.execute(update_query, (monthly_total, record_id))
                logger.info(f"Updated total to {monthly_total:.2f} for unit_records id {record_id} in guild {guild.id}, {year}-{month:02d}")
            else:
                logger.debug(f"Total already set to {current_total:.2f} for guild {guild.id}, {year}-{month:02d}. Skipping update.")
        except Exception as e:
            logger.error(f"Failed to update monthly total for guild {guild.id}, {year}-{month:02d}: {e}", exc_info=True)

    async def _check_past_months_totals(self, guild: discord.Guild) -> None:
        """Check and update missing total values for past months in the current year."""
        try:
            now = datetime.now(timezone.utc)
            current_year = now.year
            current_month = now.month

            # Check all months in the current year up to the previous month
            for month in range(1, current_month):
                await self._update_monthly_total(guild, current_year, month)
        except Exception as e:
            logger.error(f"Failed to check past months' totals for guild {guild.id}: {e}", exc_info=True)

    async def _update_yearly_totals(self, guild: discord.Guild, year: int) -> None:
        """Update year_total in subscribers table for a guild."""
        try:
            # Calculate the yearly units
            yearly_units = await self._get_yearly_units(guild)
            logger.debug(f"Calculated yearly units for guild {guild.id} for {year}: {yearly_units:.2f}")

            # Check if guild has a record in subscribers table
            subscriber = await db_manager.fetch_one(
                "SELECT year_total, lifetime_units FROM subscribers WHERE guild_id = %s",
                (guild.id,)
            )

            if not subscriber:
                logger.warning(f"No subscriber record for guild {guild.id}. Creating one.")
                await db_manager.execute(
                    """
                    INSERT INTO subscribers (guild_id, subscription_status, year_total, lifetime_units)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (guild.id, 'free', yearly_units, 0.0)
                )
                logger.info(f"Created subscriber record for guild {guild.id} with year_total: {yearly_units:.2f}")
                return

            # Update year_total in subscribers table
            await db_manager.execute(
                """
                UPDATE subscribers
                SET year_total = %s
                WHERE guild_id = %s
                """,
                (yearly_units, guild.id)
            )
            logger.info(f"Updated year_total to {yearly_units:.2f} for guild {guild.id} in subscribers table.")

        except Exception as e:
            logger.error(f"Failed to update yearly totals for guild {guild.id}: {e}", exc_info=True)

    async def _finalize_yearly_totals(self, guild: discord.Guild, year: int) -> None:
        """At year-end, add year_total to lifetime_units and reset year_total."""
        try:
            # Fetch current year_total and lifetime_units
            subscriber = await db_manager.fetch_one(
                "SELECT year_total, lifetime_units FROM subscribers WHERE guild_id = %s",
                (guild.id,)
            )

            if not subscriber:
                logger.warning(f"No subscriber record for guild {guild.id}. Creating one with zeroed values.")
                await db_manager.execute(
                    """
                    INSERT INTO subscribers (guild_id, subscription_status, year_total, lifetime_units)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (guild.id, 'free', 0.0, 0.0)
                )
                logger.info(f"Created subscriber record for guild {guild.id} with year_total: 0.00")
                return

            year_total = float(subscriber.get('year_total', 0.0) or 0.0)
            lifetime_units = float(subscriber.get('lifetime_units', 0.0) or 0.0)

            # Add year_total to lifetime_units and reset year_total
            new_lifetime_units = lifetime_units + year_total
            await db_manager.execute(
                """
                UPDATE subscribers
                SET lifetime_units = %s, year_total = %s
                WHERE guild_id = %s
                """,
                (new_lifetime_units, 0.0, guild.id)
            )
            logger.info(f"Finalized yearly totals for guild {guild.id}: Added {year_total:.2f} to lifetime_units (new total: {new_lifetime_units:.2f}), reset year_total to 0.00")

        except Exception as e:
            logger.error(f"Failed to finalize yearly totals for guild {guild.id}: {e}", exc_info=True)

    async def _get_total_units_channel(self, guild: discord.Guild) -> Optional[discord.VoiceChannel]:
        """Get the CURRENT UNITS voice channel from server_settings."""
        try:
            settings = await db_manager.fetch_one(
                "SELECT voice_channel_id FROM server_settings WHERE guild_id = %s",
                (guild.id,)
            )
            channel_id = settings.get('voice_channel_id') if settings else None
            logger.debug(f"Queried voice_channel_id for guild {guild.id}: {channel_id}")
            if not channel_id:
                logger.warning(f"No voice_channel_id set in server_settings for guild {guild.id}")
                return None
            channel = guild.get_channel(int(channel_id)) if channel_id else None
            if channel and isinstance(channel, discord.VoiceChannel):
                logger.debug(f"Found CURRENT UNITS channel {channel_id} for guild {guild.id}")
                return channel
            else:
                logger.warning(f"Channel ID {channel_id} is not a valid voice channel for guild {guild.id}")
                return None
        except Exception as e:
            logger.error(f"Failed to get CURRENT UNITS channel for guild {guild.id}: {e}", exc_info=True)
            return None

    async def _get_yearly_channel(self, guild: discord.Guild) -> Optional[discord.VoiceChannel]:
        """Get the UNITS THIS YEAR voice channel from server_settings."""
        try:
            settings = await db_manager.fetch_one(
                "SELECT yearly_channel_id FROM server_settings WHERE guild_id = %s",
                (guild.id,)
            )
            channel_id = settings.get('yearly_channel_id') if settings else None
            logger.debug(f"Queried yearly_channel_id for guild {guild.id}: {channel_id}")
            if not channel_id:
                logger.warning(f"No yearly_channel_id set in server_settings for guild {guild.id}")
                return None
            channel = guild.get_channel(int(channel_id)) if channel_id else None
            if channel and isinstance(channel, discord.VoiceChannel):
                logger.debug(f"Found UNITS THIS YEAR channel {channel_id} for guild {guild.id}")
                return channel
            else:
                logger.warning(f"Channel ID {channel_id} is not a valid voice channel for guild {guild.id}")
                return None
        except Exception as e:
            logger.error(f"Failed to get UNITS THIS YEAR channel for guild {guild.id}: {e}", exc_info=True)
            return None

    async def _is_premium_guild(self, guild: discord.Guild) -> bool:
        """Check if the guild has a premium subscription via subscribers table."""
        try:
            settings = await db_manager.fetch_one(
                "SELECT subscription_status FROM subscribers WHERE guild_id = %s",
                (guild.id,)
            )
            if not settings:
                logger.info(f"No subscription record found for guild {guild.id} in subscribers table")
                return False
            status = settings.get('subscription_status')
            is_premium = status.lower() == 'paid'  # Case-insensitive check
            logger.info(f"Guild {guild.id} subscription_status: {status}, premium: {is_premium}")
            return is_premium
        except Exception as e:
            logger.error(f"Failed to check premium status for guild {guild.id}: {e}", exc_info=True)
            return False

    async def _reset_units(self, guild: discord.Guild) -> None:
        """Placeholder for monthly/yearly unit resets."""
        logger.debug(f"Skipping unit reset logic for guild {guild.id} due to schema incompatibility.")
        pass

    async def _update_all_guilds(self) -> None:
        """Update voice channels for all guilds and check past months' totals."""
        try:
            for guild in self.bot.guilds:
                logger.debug(f"Processing guild: {guild.name} ({guild.id})")

                # Check if guild is premium
                is_premium = await self._is_premium_guild(guild)
                if not is_premium:
                    logger.debug(f"Guild {guild.id} is not premium, skipping premium features")
                    continue

                # Update total and yearly channels and check past totals for premium guilds
                # Check past months for missing totals
                await self._check_past_months_totals(guild)

                # Update year_total in subscribers table
                now = datetime.now(timezone.utc)
                await self._update_yearly_totals(guild, now.year)

                # CURRENT UNITS
                total_units_channel = await self._get_total_units_channel(guild)
                if total_units_channel:
                    current_units = await self._get_current_month_units(guild)
                    new_name = f"CURRENT UNITS: {current_units:+.2f}"
                    if total_units_channel.name != new_name:
                        try:
                            await total_units_channel.edit(name=new_name)
                            logger.info(f"Updated CURRENT UNITS channel {total_units_channel.id} to '{new_name}' in guild {guild.id}")
                        except discord.Forbidden:
                            logger.error(f"Permission error updating CURRENT UNITS channel for guild {guild.id}")
                        except Exception as e:
                            logger.error(f"Error updating CURRENT UNITS channel for guild {guild.id}: {e}", exc_info=True)
                    else:
                        logger.debug(f"CURRENT UNITS channel {total_units_channel.id} name unchanged: '{new_name}'")
                else:
                    logger.warning(f"No valid CURRENT UNITS channel found for guild {guild.id}")

                # UNITS THIS YEAR
                yearly_channel = await self._get_yearly_channel(guild)
                if yearly_channel:
                    yearly_units = await self._get_yearly_units(guild)
                    new_name = f"UNITS THIS YEAR: {yearly_units:+.2f}"
                    if yearly_channel.name != new_name:
                        try:
                            await yearly_channel.edit(name=new_name)
                            logger.info(f"Updated UNITS THIS YEAR channel {yearly_channel.id} to '{new_name}' in guild {guild.id}")
                        except discord.Forbidden:
                            logger.error(f"Permission error updating UNITS THIS YEAR channel for guild {guild.id}")
                        except Exception as e:
                            logger.error(f"Error updating UNITS THIS YEAR channel for guild {guild.id}: {e}", exc_info=True)
                    else:
                        logger.debug(f"UNITS THIS YEAR channel {yearly_channel.id} name unchanged: '{new_name}'")
                else:
                    logger.warning(f"No valid UNITS THIS YEAR channel found for guild {guild.id}")

                # Update individual bet voice channels (for all guilds)
                now = datetime.now(timezone.utc)
                pending_bets_query = """
                    SELECT bet_serial, event_id, league, team, opponent, game_start
                    FROM bets
                    WHERE guild_id = %s
                      AND bet_won IS NULL
                      AND bet_loss IS NULL
                      AND game_start IS NOT NULL
                      AND game_start BETWEEN %s AND %s
                """
                start_window = now - timedelta(days=1)
                end_window = now + timedelta(days=2)

                pending_bets: List[Dict] = await db_manager.fetch(pending_bets_query, (guild.id, start_window, end_window))
                logger.debug(f"Found {len(pending_bets)} relevant pending bets for guild {guild.id}")

                if not pending_bets:
                    continue

                bet_serials = [bet['bet_serial'] for bet in pending_bets]
                vc_query = """
                    SELECT bet_serial, voice_channel_id
                    FROM voice_bet_updates
                    WHERE bet_serial IN %s
                """
                vc_results: List[Dict] = await db_manager.fetch(vc_query, (tuple(bet_serials),))
                vc_map: Dict[str, int] = {str(row['bet_serial']): row['voice_channel_id'] for row in vc_results if row.get('voice_channel_id')}

                game_service = getattr(self.bot, 'game_service', None)
                if not game_service:
                    logger.error("GameService not found on bot instance.")
                    continue

                for bet in pending_bets:
                    bet_serial = bet['bet_serial']
                    event_id = bet.get('event_id')
                    league = bet.get('league', 'N/A')
                    team = bet.get('team', 'N/A')
                    opponent = bet.get('opponent', 'N/A')
                    game_start = bet.get('game_start')
                    voice_channel_id = vc_map.get(str(bet_serial))
                    channel = guild.get_channel(voice_channel_id) if voice_channel_id else None

                    new_channel_name = f"{team} vs {opponent} | Pending Fetch"

                    if event_id:
                        game_data = await game_service.get_game(str(event_id))
                        if game_data:
                            home_team = game_data.get("home_team", team)
                            away_team = game_data.get("away_team", opponent)
                            home_score = game_data.get("home_score", "0")
                            away_score = game_data.get("away_score", "0")
                            status = game_data.get("game_status", "Scheduled")
                            display_clock = game_data.get("display_clock", "")
                            period = game_data.get("game_period", 1)

                            if status == "Scheduled":
                                est_tz = timezone(timedelta(hours=-5))
                                start_time_str = game_start.astimezone(est_tz).strftime("%H:%M EST") if game_start else "TBD"
                                new_channel_name = f"{home_team} vs {away_team} | {start_time_str}"
                            elif status == "In Progress":
                                period_suffix = f" P{period}" if league == "NHL" else (f" Q{period}" if league == "NBA" else f" H{period}" if "NCAA" in league else "")
                                clock_str = f" ({display_clock}{period_suffix})" if display_clock else f" ({period_suffix})"
                                new_channel_name = f"{home_team} vs {away_team} | {home_score}:{away_score}{clock_str}"
                            elif status == "Finished":
                                try:
                                    winner = home_team if int(home_score) > int(away_score) else away_team if int(away_score) > int(home_score) else "TIE"
                                except (ValueError, TypeError):
                                    winner = "N/A"
                                new_channel_name = f"{winner} Wins! | {home_score}:{away_score}" if winner != "TIE" and winner != "N/A" else f"Final {home_score}:{away_score}"
                            else:
                                new_channel_name = f"{home_team} vs {away_team} | {status}"
                        else:
                            new_channel_name = f"{team} vs {opponent} | Waiting..."
                    else:
                        new_channel_name = f"{team} vs {opponent} | Event ID Missing"

                    if channel and isinstance(channel, discord.VoiceChannel):
                        if channel.name != new_channel_name[:100]:
                            try:
                                await channel.edit(name=new_channel_name[:100])
                                logger.info(f"Updated VC {channel.id} name for bet {bet_serial} to '{new_channel_name}'")
                            except discord.Forbidden:
                                logger.error(f"Permission error editing VC {channel.id} for guild {guild.id}")
                            except Exception as e:
                                logger.error(f"Error editing VC {channel.id}: {e}", exc_info=True)
                        if game_data and game_data.get("game_status") == "Finished":
                            logger.info(f"Scheduling deletion for finished game VC {channel.id} (bet {bet_serial})")
                            asyncio.create_task(self._delete_channel_later(channel, bet_serial))
                    elif not channel and game_data and game_data.get("game_status") != "Finished":
                        try:
                            category = discord.utils.get(guild.categories, name="ACTIVE BETS") or await guild.create_category("ACTIVE BETS")
                            overwrites = {guild.default_role: discord.PermissionOverwrite(connect=False)}
                            new_channel = await category.create_voice_channel(name=new_channel_name[:100], overwrites=overwrites)
                            logger.info(f"Created VC {new_channel.id} for bet {bet_serial}")
                            await db_manager.execute(
                                "INSERT INTO voice_bet_updates (bet_serial, voice_channel_id, created_at) VALUES (%s, %s, NOW()) ON DUPLICATE KEY UPDATE voice_channel_id = VALUES(voice_channel_id)",
                                (bet_serial, new_channel.id)
                            )
                        except discord.Forbidden:
                            logger.error(f"Permission error creating VC for bet {bet_serial} in guild {guild.id}")
                        except Exception as e:
                            logger.error(f"Error creating VC for bet {bet_serial}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Unexpected error in _update_all_guilds: {e}", exc_info=True)

    async def _monthly_total_loop(self) -> None:
        """Loop to update monthly totals at midnight EST on the last day of each month."""
        await self.bot.wait_until_ready()
        logger.info("Monthly total update loop started.")
        while self.running:
            try:
                now = datetime.now(timezone(timedelta(hours=-5)))  # EST
                year = now.year
                month = now.month
                last_day = monthrange(year, month)[1]

                # Calculate seconds until midnight EST of the last day
                target = datetime(year, month, last_day, 0, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
                if now.day > last_day or (now.day == last_day and now.hour >= 0):
                    next_month = month % 12 + 1
                    next_year = year + (1 if month == 12 else 0)
                    target = datetime(next_year, next_month, monthrange(next_year, next_month)[1], 0, 0, 0, tzinfo=timezone(timedelta(hours=-5)))

                seconds_until = (target - now).total_seconds()
                if seconds_until < 0:
                    seconds_until += 86400

                logger.debug(f"Monthly total loop sleeping for {seconds_until:.2f} seconds until {target}")
                await asyncio.sleep(seconds_until)

                # Update totals for premium guilds
                for guild in self.bot.guilds:
                    if await self._is_premium_guild(guild):
                        await self._update_monthly_total(guild, year, month)

            except asyncio.CancelledError:
                logger.info("Monthly total update loop cancelled.")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in monthly total loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _yearly_total_loop(self) -> None:
        """Loop to finalize yearly totals at midnight EST on December 31st."""
        await self.bot.wait_until_ready()
        logger.info("Yearly total update loop started.")
        while self.running:
            try:
                now = datetime.now(timezone(timedelta(hours=-5)))  # EST
                year = now.year

                # Calculate seconds until midnight EST of December 31st
                target = datetime(year, 12, 31, 0, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
                if now.month > 12 or (now.month == 12 and now.day >= 31):
                    target = datetime(year + 1, 12, 31, 0, 0, 0, tzinfo=timezone(timedelta(hours=-5)))

                seconds_until = (target - now).total_seconds()
                if seconds_until < 0:
                    seconds_until += 86400

                logger.debug(f"Yearly total loop sleeping for {seconds_until:.2f} seconds until {target}")
                await asyncio.sleep(seconds_until)

                # Finalize yearly totals for premium guilds
                for guild in self.bot.guilds:
                    if await self._is_premium_guild(guild):
                        await self._finalize_yearly_totals(guild, year)

            except asyncio.CancelledError:
                logger.info("Yearly total update loop cancelled.")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in yearly total loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _delete_channel_later(self, channel: discord.VoiceChannel, bet_serial: int, delay: int = 3600) -> None:
        """Delete a bet channel after a delay and update DB."""
        await asyncio.sleep(delay)
        try:
            channel_id = channel.id
            await channel.delete(reason=f"Bet {bet_serial} finished.")
            await db_manager.execute(
                "DELETE FROM voice_bet_updates WHERE bet_serial = %s AND voice_channel_id = %s",
                (bet_serial, channel_id)
            )
            logger.info(f"Deleted voice channel {channel_id} for bet {bet_serial} after {delay}s delay.")
        except discord.NotFound:
            logger.warning(f"Channel {channel_id} already deleted for bet {bet_serial}.")
            await db_manager.execute(
                "DELETE FROM voice_bet_updates WHERE bet_serial = %s AND voice_channel_id = %s",
                (bet_serial, channel_id)
            )
        except discord.Forbidden:
            logger.error(f"Permission error deleting channel {channel.id} for bet {bet_serial}.")
        except Exception as e:
            logger.error(f"Failed to delete channel {channel.id} or update DB for bet {bet_serial}: {e}", exc_info=True)

    async def _update_loop(self) -> None:
        """Main loop to update all guilds every 5 minutes, synchronized."""
        await self.bot.wait_until_ready()
        logger.info("Voice service entering update loop.")
        while self.running:
            try:
                now = datetime.now(timezone.utc)
                seconds_since_midnight = (now.hour * 3600) + (now.minute * 60) + now.second
                seconds_per_interval = 300
                seconds_to_next = seconds_per_interval - (seconds_since_midnight % seconds_per_interval)

                logger.debug(f"Voice service sleeping for {seconds_to_next:.2f} seconds until next 5-min mark.")
                await asyncio.sleep(seconds_to_next)

                logger.info("Voice service starting synchronized update cycle.")
                await self._update_all_guilds()
                logger.info("Voice service update cycle finished.")

            except asyncio.CancelledError:
                logger.info("Voice service update loop cancelled.")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in voice update loop: {e}", exc_info=True)
                await asyncio.sleep(60)
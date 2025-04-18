"""
Database manager for the Discord betting bot.
Provides a centralized interface for MySQL interactions using a connection pool.
"""

import aiomysql
import logging
from typing import Any, List, Tuple, Optional, Dict
from config.settings import DB_CONFIG
from bot.utils.errors import DatabaseConnectionError, DatabaseQueryError, DatabaseError

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Singleton-like class for managing MySQL connections."""
    _instance = None
    _pool: Optional[aiomysql.Pool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Initialize the connection pool if not already connected."""
        if self._pool is None or self._pool._closed:
            try:
                db_name = DB_CONFIG.get('db', 'unknown_db')
                host = DB_CONFIG.get('host', 'unknown_host')
                port = DB_CONFIG.get('port', 3306)
                logger.info(f"Attempting to connect to database '{db_name}' at {host}:{port}")

                required_keys = {"host", "port", "user", "password", "db"}
                if not required_keys.issubset(DB_CONFIG):
                    missing = required_keys - set(DB_CONFIG.keys())
                    raise DatabaseConnectionError(f"Missing required database configuration keys: {missing}")

                self._pool = await aiomysql.create_pool(
                    host=DB_CONFIG["host"],
                    port=int(DB_CONFIG["port"]),
                    user=DB_CONFIG["user"],
                    password=DB_CONFIG["password"],
                    db=DB_CONFIG["db"],
                    autocommit=True,
                    pool_recycle=3600,
                    minsize=1,
                    maxsize=10,
                    connect_timeout=10
                )
                logger.info("Database connection pool initialized successfully")
                await self._setup_tables()
            except aiomysql.Error as e:
                logger.error(f"Failed to initialize database pool: {e}", exc_info=True)
                self._pool = None
                raise DatabaseConnectionError(message=f"Database connection failed during pool creation: {e}", original_exception=e)
            except ValueError as e:
                logger.error(f"Configuration error (e.g., port not an integer): {e}")
                self._pool = None
                raise DatabaseConnectionError(message=f"Database configuration error: {e}", original_exception=e)
            except Exception as e:
                logger.error(f"Unexpected error during database initialization: {e}", exc_info=True)
                self._pool = None
                raise DatabaseConnectionError(message=f"Unexpected database initialization error: {e}", original_exception=e)

    async def _ensure_connected(self):
        """Check connection and attempt reconnect if necessary."""
        if self._pool is None or self._pool._closed:
            logger.warning("Database pool closed or not initialized. Attempting to reconnect.")
            await self.connect()

    async def _setup_tables(self) -> None:
        """Check if necessary tables and columns exist in the database. Assumes pool is connected."""
        if self._pool is None:
            logger.error("Cannot check tables: Database pool is not available.")
            raise DatabaseConnectionError("Database pool not initialized before table check.")

        expected_tables = [
            "bets",
            "cappers",
            "server_settings",
            "subscribers",
            "subscriptions",
            "unit_records",
            "users",
            "user_images",
            "voice_bet_updates"
        ]

        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT DATABASE()")
                    current_db = (await cur.fetchone())[0]
                    if not current_db:
                        logger.error("No database selected for table check.")
                        raise DatabaseConnectionError("No database selected.")

                    # Check for tables
                    query = """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                        AND table_name IN %s
                    """
                    await cur.execute(query, (current_db, tuple(expected_tables)))
                    existing_tables = {row[0] for row in await cur.fetchall()}

                    missing_tables = [table for table in expected_tables if table not in existing_tables]
                    if missing_tables:
                        logger.error(f"Missing tables in database '{current_db}': {', '.join(missing_tables)}")
                        raise DatabaseError(f"Missing tables: {', '.join(missing_tables)}")

                    # Check for commands_registered column in server_settings
                    query = """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = %s
                        AND table_name = 'server_settings'
                        AND column_name = 'commands_registered'
                    """
                    await cur.execute(query, (current_db,))
                    column_exists = await cur.fetchone()
                    if not column_exists:
                        logger.info("Adding commands_registered column to server_settings.")
                        alter_query = """
                            ALTER TABLE server_settings
                            ADD COLUMN commands_registered TINYINT DEFAULT 0 NOT NULL AFTER guild_id
                        """
                        await cur.execute(alter_query)
                        logger.info("Added commands_registered column to server_settings.")

                    logger.info(f"All expected tables ({', '.join(expected_tables)}) and server_settings.commands_registered column found in database '{current_db}'.")

        except aiomysql.Error as e:
            logger.error(f"Database connection error during table check: {e}", exc_info=True)
            raise DatabaseConnectionError(message=f"Failed during table check connection: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during table check: {e}", exc_info=True)
            raise DatabaseError(message=f"Unexpected error during table check: {e}", original_exception=e)

    async def execute(self, query: str, params: Optional[Tuple] = None) -> int:
        await self._ensure_connected()
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    logger.debug(f"Executing DB query: {query[:200]}... with params: {params}")
                    await cur.execute(query, params)
                    rowcount = cur.rowcount
                    logger.debug(f"Query executed successfully. Row count: {rowcount}")
                    return rowcount if rowcount is not None else 0
        except aiomysql.Error as e:
            logger.error(f"Database query execution failed: {query[:200]}... | Params: {params} | Error: {e}", exc_info=True)
            raise DatabaseQueryError(message=f"Query execution failed: {e}", query=query, original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during query execution: {query[:200]}... | Error: {e}", exc_info=True)
            raise DatabaseError(message=f"Unexpected error during query execution: {e}", original_exception=e)

    async def fetch(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        await self._ensure_connected()
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    logger.debug(f"Fetching DB query: {query[:200]}... with params: {params}")
                    await cur.execute(query, params)
                    results = await cur.fetchall()
                    logger.debug(f"Query fetch successful. Row count: {len(results)}")
                    return results if results else []
        except aiomysql.Error as e:
            logger.error(f"Database query fetch failed: {query[:200]}... | Params: {params} | Error: {e}", exc_info=True)
            raise DatabaseQueryError(message=f"Query fetch failed: {e}", query=query, original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during query fetch: {query[:200]}... | Error: {e}", exc_info=True)
            raise DatabaseError(message=f"Unexpected error during query fetch: {e}", original_exception=e)

    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        await self._ensure_connected()
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    logger.debug(f"Fetching one DB query: {query[:200]}... with params: {params}")
                    await cur.execute(query, params)
                    result = await cur.fetchone()
                    logger.debug(f"Query fetch_one successful. Result found: {'Yes' if result else 'No'}")
                    return result
        except aiomysql.Error as e:
            logger.error(f"Database query fetch_one failed: {query[:200]}... | Params: {params} | Error: {e}", exc_info=True)
            raise DatabaseQueryError(message=f"Query fetch_one failed: {e}", query=query, original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during query fetch_one: {query[:200]}... | Error: {e}", exc_info=True)
            raise DatabaseError(message=f"Unexpected error during query fetch_one: {e}", original_exception=e)

    async def get_or_create_server_settings(self, guild_id: int, guild_name: str = "Unknown Guild") -> Dict[str, Any]:
        await self._ensure_connected()
        default_settings = {
            "guild_id": guild_id,
            "commands_registered": 0,
            "embed_channel_1": None,
            "embed_channel_2": None,
            "command_channel_1": None,
            "command_channel_2": None,
            "admin_channel_1": None,
            "admin_role": None,
            "authorized_role": None,
            "daily_report_time": None,
            "voice_channel_id": None,
            "yearly_channel_id": None,
            "bot_name_mask": None,
            "bot_image_mask": None
        }
        select_query = "SELECT * FROM server_settings WHERE guild_id = %s"
        try:
            settings = await self.fetch_one(select_query, (guild_id,))
            if settings:
                logger.debug(f"Found settings for guild {guild_id}")
                return {**default_settings, **settings}
            logger.info(f"No settings found for guild {guild_id} ({guild_name}). Creating default entry.")
            insert_query = "INSERT INTO server_settings (guild_id) VALUES (%s) ON DUPLICATE KEY UPDATE guild_id = VALUES(guild_id)"
            await self.execute(insert_query, (guild_id,))
            settings = await self.fetch_one(select_query, (guild_id,))
            if settings:
                logger.debug(f"Fetched settings after creation for guild {guild_id}")
                return {**default_settings, **settings}
            else:
                logger.warning(f"Could not fetch settings immediately after creation for guild {guild_id}. Returning defaults.")
                return default_settings
        except aiomysql.Error as e:
            logger.error(f"Database error in get_or_create_settings for guild {guild_id}: {e}", exc_info=True)
            raise DatabaseQueryError(message=f"Failed to get or create server settings: {e}", query=select_query, original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error in get_or_create_settings for guild {guild_id}: {e}", exc_info=True)
            raise DatabaseError(message=f"Unexpected error during get_or_create_server_settings: {e}", original_exception=e)

    async def set_guild_commands_registered(self, guild_id: int, registered: bool) -> bool:
        """
        Updates the commands_registered flag for a guild in server_settings.
        Returns True if successful, False otherwise.
        """
        await self._ensure_connected()
        query = "UPDATE server_settings SET commands_registered = %s WHERE guild_id = %s"
        try:
            rowcount = await self.execute(query, (1 if registered else 0, guild_id))
            logger.debug(f"Updated commands_registered to {registered} for guild {guild_id}. Rows affected: {rowcount}")
            return rowcount > 0
        except aiomysql.Error as e:
            logger.error(f"Database error setting commands_registered for guild {guild_id}: {e}", exc_info=True)
            raise DatabaseQueryError(message=f"Failed to set commands_registered: {e}", query=query, original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error setting commands_registered for guild {guild_id}: {e}", exc_info=True)
            raise DatabaseError(message=f"Unexpected error during set_guild_commands_registered: {e}", original_exception=e)

    async def get_configured_guilds(self) -> List[int]:
        """
        Fetches guild IDs where commands are registered from the server_settings table.
        Returns a list of guild IDs.
        """
        await self._ensure_connected()
        query = "SELECT guild_id FROM server_settings WHERE commands_registered = 1"
        try:
            results = await self.fetch(query)
            guild_ids = [row['guild_id'] for row in results] if results else []
            logger.debug(f"Fetched configured guild IDs: {guild_ids}")
            return guild_ids
        except aiomysql.Error as e:
            logger.error(f"Database error fetching configured guilds: {e}", exc_info=True)
            raise DatabaseQueryError(message=f"Failed to fetch configured guilds: {e}", query=query, original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error fetching configured guilds: {e}", exc_info=True)
            raise DatabaseError(message=f"Unexpected error during get_configured_guilds: {e}", original_exception=e)

    async def close(self) -> None:
        """Closes the database connection pool."""
        if self._pool and not self._pool._closed:
            try:
                self._pool.close()
                await self._pool.wait_closed()
                logger.info("Database connection pool closed")
            except Exception as e:
                logger.error(f"Error closing database pool: {e}", exc_info=True)
            finally:
                self._pool = None

db_manager = DatabaseManager()
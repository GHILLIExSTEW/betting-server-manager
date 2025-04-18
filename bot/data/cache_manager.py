"""
Cache manager for the Discord betting bot.
Provides a centralized interface for Redis caching.
"""

import redis.asyncio as redis
import logging
from typing import Any, Optional
# Assume settings loads correctly now
from config.settings import REDIS_CONFIG
# Import custom errors if needed for connection handling
from utils.errors import DatabaseConnectionError # Reusing for Redis connection issues

logger = logging.getLogger(__name__)

class CacheManager:
    """Singleton-like class for managing Redis connections."""
    _instance = None
    _client: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Initialize the Redis connection if not already connected."""
        # Check if client exists and if we can ping it
        # Note: pinging repeatedly might not be ideal, consider connection state check if available
        needs_connection = True
        if self._client:
            try:
                await self._client.ping()
                needs_connection = False
                logger.debug("Redis connection already active.")
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, ConnectionRefusedError):
                logger.warning("Redis ping failed. Attempting to reconnect.")
                # Attempt to close existing broken connection before reconnecting
                try:
                    await self._client.close() # Ensure close is awaitable
                except Exception as close_err:
                    logger.error(f"Error closing potentially broken Redis client: {close_err}")
                self._client = None # Reset client
            except Exception as ping_err: # Catch other potential errors during ping
                logger.error(f"Unexpected error during Redis ping: {ping_err}")
                needs_connection = False # Avoid loop if ping fails unexpectedly

        if needs_connection:
            try:
                logger.info(f"Attempting to connect to Redis at {REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}")
                self._client = redis.Redis(
                    host=REDIS_CONFIG["host"],
                    port=REDIS_CONFIG["port"],
                    username=REDIS_CONFIG.get("username"), # Use .get for optional keys
                    password=REDIS_CONFIG.get("password"), # Use .get for optional keys
                    db=REDIS_CONFIG["db"],
                    # decode_responses=True, # Consider if you need bytes or strings
                    decode_responses=False, # Keep as bytes for broader compatibility initially
                    socket_connect_timeout=5, # Add connection timeout
                    socket_keepalive=True, # Enable keepalive
                )
                # Test connection
                await self._client.ping()
                logger.info("Redis connection initialized successfully")
            except redis.exceptions.ConnectionError as e:
                logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
                self._client = None # Ensure client is None on failure
                raise DatabaseConnectionError(message=f"Redis connection failed: {e}", original_exception=e)
            except redis.exceptions.AuthenticationError as e:
                 logger.error(f"Redis authentication failed: {e}", exc_info=True)
                 self._client = None
                 raise DatabaseConnectionError(message=f"Redis authentication failed: {e}", original_exception=e)
            except Exception as e:
                logger.error(f"Failed to initialize Redis connection: {e}", exc_info=True)
                self._client = None
                raise DatabaseConnectionError(message=f"Unexpected Redis connection error: {e}", original_exception=e)

    async def _ensure_connected(self):
        """Check connection and attempt reconnect if necessary."""
        if self._client is None:
             logger.warning("Redis client not initialized. Attempting connection.")
             await self.connect() # Will raise if connection fails
        else:
             try:
                  await self._client.ping()
             except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, ConnectionRefusedError):
                  logger.warning("Redis connection lost. Attempting to reconnect.")
                  await self.connect() # Try to reconnect
             except Exception as e:
                  logger.error(f"Unexpected error during Redis connection check: {e}")
                  # Decide how to handle - maybe raise error?
                  raise DatabaseConnectionError(f"Redis connection check failed: {e}", original_exception=e)

    async def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set a value in the cache with an optional time-to-live (in seconds)."""
        await self._ensure_connected()
        try:
            # Serialize value if it's not bytes/str/int/float
            if not isinstance(value, (bytes, str, int, float)):
                 import jsonpickle # Or standard json
                 value = jsonpickle.encode(value)
            await self._client.set(key, value, ex=ttl)
            logger.debug(f"Cache set: {key} (TTL: {ttl if ttl else 'None'})")
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {e}")
            # Optionally raise a custom cache error
            raise

    async def get(self, key: str) -> Optional[bytes]: # Changed return type hint to bytes
        """Get a value from the cache. Returns raw bytes or None."""
        await self._ensure_connected()
        try:
            value_bytes = await self._client.get(key)
            if value_bytes is not None:
                logger.debug(f"Cache hit: {key}")
                # --- REMOVED DECODING LOGIC ---
                # No longer attempts to decode here.
                # Returns raw bytes directly from Redis.
                # --- ----------------------- ---
                return value_bytes # Return raw bytes
            else:
                logger.debug(f"Cache miss: {key}")
                return None
        except Exception as e:
            logger.error(f"Failed to get cache key {key}: {e}")
            # Optionally raise a custom cache error
            raise # Re-raise the exception

    async def delete(self, key: str) -> int:
        """Delete a key from the cache. Returns number of keys deleted."""
        await self._ensure_connected()
        try:
            result = await self._client.delete(key)
            logger.debug(f"Cache delete: {key} - Deleted {result} keys")
            return result
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {e}")
            # Optionally raise a custom cache error
            raise

    async def zadd(self, name: str, mapping: dict[str, float]) -> int:
        """Add elements to a sorted set with scores."""
        await self._ensure_connected()
        try:
            result = await self._client.zadd(name, mapping)
            logger.debug(f"ZADD to {name}: {mapping}")
            return result
        except Exception as e:
            logger.error(f"Failed to zadd to {name}: {e}")
            raise

    async def zrange(self, name: str, start: int, end: int, withscores: bool = False) -> list[Any]:
        """Get a range of elements from a sorted set."""
        await self._ensure_connected()
        try:
            # Result format depends on decode_responses and withscores
            result = await self._client.zrange(name, start, end, withscores=withscores)
            logger.debug(f"ZRANGE from {name}: {result}")
            # Decode bytes if needed (assuming decode_responses=False)
            if not self._client.decode_responses:
                decoded_result = []
                for item in result:
                    if isinstance(item, tuple): # (member_bytes, score_float)
                        try:
                             member = item[0].decode('utf-8')
                             decoded_result.append((member, item[1]))
                        except: # Handle potential decode errors
                             decoded_result.append((item[0], item[1])) # Keep bytes
                    elif isinstance(item, bytes): # member_bytes
                         try:
                              decoded_result.append(item.decode('utf-8'))
                         except:
                              decoded_result.append(item) # Keep bytes
                    else: # Should be float if score only, or already decoded?
                         decoded_result.append(item)
                return decoded_result
            else: # Already decoded by client
                 return result

        except Exception as e:
            logger.error(f"Failed to zrange from {name}: {e}")
            raise

    async def close(self) -> None:
        """Close the Redis connection."""
        # Remove the '.closed' check which caused the AttributeError
        if self._client:
            try:
                await self._client.close() # Close the client first
                # await self._client.wait_closed() # Deprecated/Removed in later versions? Check redis-py docs.
                logger.info("Redis connection closed")
            except Exception as e:
                 logger.error(f"Error during Redis client close: {e}")
            finally:
                 self._client = None # Ensure client attribute is reset

# Singleton instance
cache_manager = CacheManager()
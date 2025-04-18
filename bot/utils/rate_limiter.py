"""
Rate limiting utilities for the Discord betting bot.
Manages API and Discord interaction limits to prevent overuse.
"""
import discord
import asyncio
import logging
from typing import Callable, Any, Coroutine
from functools import wraps

logger = logging.getLogger(__name__)

# Rate limits (adjust based on API-Football and Discord limits)
API_LIMIT = 50  # Max 50 API requests concurrently (API-Football free tier allows ~100/minute, adjust as needed)
DISCORD_LIMIT = 20  # Max 20 Discord interactions concurrently (conservative estimate)

# Semaphores for concurrent limits
api_semaphore = asyncio.Semaphore(API_LIMIT)
discord_semaphore = asyncio.Semaphore(DISCORD_LIMIT)

def limit_api_call(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
    """
    Decorator to limit concurrent API calls.

    Args:
        func: The async function to decorate.

    Returns:
        A wrapped async function with rate limiting applied.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with api_semaphore:
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"Rate-limited API call completed: {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Rate-limited API call failed: {func.__name__} - {e}")
                raise
    return wrapper

def limit_discord_call(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
    """
    Decorator to limit concurrent Discord interactions.

    Args:
        func: The async function to decorate.

    Returns:
        A wrapped async function with rate limiting applied.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with discord_semaphore:
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"Rate-limited Discord call completed: {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Rate-limited Discord call failed: {func.__name__} - {e}")
                raise
    return wrapper

async def rate_limited_call(coro: Coroutine[Any, Any, Any], is_api: bool = True) -> Any:
    """
    Explicitly limit a coroutine call (for non-decorator use).

    Args:
        coro: The coroutine to execute.
        is_api: True for API calls, False for Discord calls.

    Returns:
        The result of the coroutine.
    """
    semaphore = api_semaphore if is_api else discord_semaphore
    async with semaphore:
        try:
            result = await coro
            logger.debug(f"Rate-limited call completed (API={is_api})")
            return result
        except Exception as e:
            logger.error(f"Rate-limited call failed (API={is_api}): {e}")
            raise
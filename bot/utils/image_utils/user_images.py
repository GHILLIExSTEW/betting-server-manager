# bot/utils/image_utils/user_images.py
import csv
import io
import logging
import discord
from typing import Dict, Optional
from PIL import Image, UnidentifiedImageError
from .helpers import USER_CSV_PATH, USER_IMAGES_DIR, DEFAULT_AVATAR_URL, LOGO_BASE_URL, csv_lock, logger

# Initialize USER_CSV_PATH if it doesn't exist
if not USER_CSV_PATH.exists():
    try:
        with open(USER_CSV_PATH, "w", newline="", encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["guild_id", "user_id", "display_name", "user_url"])
            writer.writeheader()
        logger.info(f"Initialized user URL CSV file at {USER_CSV_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize user URL CSV file: {e}")

def load_user_image_urls_from_csv() -> Dict[str, Dict[str, str]]:
    """Loads user avatar URLs from the static CSV file."""
    user_urls: Dict[str, Dict[str, str]] = {}
    if not USER_CSV_PATH.exists():
        logger.warning(f"User URLs CSV not found, cannot load: {USER_CSV_PATH}")
        return user_urls
    try:
        with open(USER_CSV_PATH, "r", newline="", encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            required_headers = {'guild_id', 'user_id', 'user_url'}
            if not reader.fieldnames or not required_headers.issubset(reader.fieldnames):
                logger.error(f"Invalid or missing headers in user URLs CSV: {USER_CSV_PATH}. Headers found: {reader.fieldnames}")
                return user_urls

            for row_num, row in enumerate(reader, 1):
                guild_id = row.get('guild_id')
                user_id = row.get('user_id')
                user_url = row.get('user_url')
                if guild_id and user_id and user_url:
                    key = f"{guild_id}:{user_id}"
                    user_urls[key] = {'display_name': row.get('display_name', 'N/A'), 'user_url': user_url}
                else:
                    missing = [h for h in required_headers if not row.get(h)]
                    logger.warning(f"Skipping invalid row {row_num} in {USER_CSV_PATH}. Missing fields: {missing}. Row data: {row}")
        logger.debug(f"Loaded {len(user_urls)} user URLs from {USER_CSV_PATH}")
        return user_urls
    except Exception as e:
        logger.error(f"Error loading user URLs from {USER_CSV_PATH}: {e}", exc_info=True)
        return user_urls

async def save_user_image_url_to_csv(guild_id: str, user_id: str, display_name: str, user_url: str):
    """Saves or updates a user's avatar URL in the static CSV file."""
    if not all([guild_id, user_id, user_url]):
        logger.warning(f"Skipping save_user_image_url_to_csv due to missing data: G={guild_id}, U={user_id}, URL={user_url}")
        return

    async with csv_lock:
        user_urls = load_user_image_urls_from_csv()
        key = f"{guild_id}:{user_id}"
        user_urls[key] = {'display_name': display_name or 'N/A', 'user_url': user_url}

        try:
            with open(USER_CSV_PATH, "w", newline="", encoding='utf-8') as csvfile:
                fieldnames = ["guild_id", "user_id", "display_name", "user_url"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for k, data in user_urls.items():
                    try:
                        gid, uid = k.split(":", 1)
                        writer.writerow({
                            "guild_id": gid,
                            "user_id": uid,
                            "display_name": data.get('display_name', 'N/A'),
                            "user_url": data.get('user_url', '')
                        })
                    except ValueError:
                        logger.warning(f"Skipping save for invalid key format found in memory: {k}")
            logger.debug(f"Saved user URL ({key}) to {USER_CSV_PATH}")
        except Exception as e:
            logger.error(f"Error saving user URL ({key}) to {USER_CSV_PATH}: {e}", exc_info=True)

async def get_user_image_url(guild_id: Optional[str], user_id: Optional[str], interaction: Optional[discord.Interaction] = None) -> str:
    """Retrieves the user's image URL from DB, CSV, Discord, or default."""
    from bot.data.db_manager import db_manager  # Lazy import to avoid circular dependency

    if not guild_id or not user_id:
        logger.debug("get_user_image_url called with missing guild_id or user_id.")
        return DEFAULT_AVATAR_URL
    try:
        user_id_int = int(user_id)
        guild_id_int = int(guild_id)
    except ValueError:
        logger.warning(f"Invalid non-integer ID format for get_user_image_url: G='{guild_id}', U='{user_id}'.")
        return DEFAULT_AVATAR_URL

    cache_key = f"user_avatar_url:{guild_id}:{user_id}"
    base_url = LOGO_BASE_URL if LOGO_BASE_URL.endswith('/') else LOGO_BASE_URL + "/"

    # Cache Check
    try:
        cached_url_bytes = await cache_manager.get(cache_key)
        if cached_url_bytes is not None:
            cached_url = cached_url_bytes.decode('utf-8')
            if cached_url and cached_url.lower().startswith(('http://', 'https://')):
                logger.debug(f"Cache hit user URL ({cache_key}): {cached_url}")
                return cached_url
            else:
                logger.warning(f"Invalid URL found in cache for {cache_key}: '{cached_url}'. Ignoring.")
    except Exception as cache_err:
        logger.error(f"Redis GET error for user URL ({cache_key}): {cache_err}")

    # Database Check
    db_generated_url: Optional[str] = None
    try:
        await db_manager.connect()
        query = "SELECT user_image FROM cappers WHERE user_id = %s AND guild_id = %s"
        result = await db_manager.fetch_one(query, (user_id_int, guild_id_int))

        if result and result.get('user_image'):
            image_blob = result['user_image']
            if isinstance(image_blob, bytes) and len(image_blob) > 100:
                logger.debug(f"DB hit: Found user image BLOB for {guild_id}:{user_id}, size: {len(image_blob)}")
                file_name = f"user_{user_id}.png"
                file_path = USER_IMAGES_DIR / file_name
                try:
                    with Image.open(io.BytesIO(image_blob)) as img:
                        img.verify()
                    with Image.open(io.BytesIO(image_blob)) as img:
                        if img.mode in ('RGBA', 'LA', 'P'):
                            logger.debug(f"Converting user image {user_id} from mode {img.mode} to RGBA for PNG save.")
                            img = img.convert('RGBA')
                        else:
                            img = img.convert('RGB')
                        img.save(file_path, "PNG")
                    db_generated_url = f"{base_url}static/user_images/{file_name}"
                    logger.info(f"Successfully saved user BLOB to {file_path} and generated URL: {db_generated_url}")
                    await cache_manager.set(cache_key, db_generated_url, ttl=3600)
                    return db_generated_url
                except UnidentifiedImageError:
                    logger.error(f"FAILED (UnidentifiedImageError) processing DB BLOB for user {user_id}. BLOB size: {len(image_blob)}. Skipping BLOB.", exc_info=False)
                except Exception as img_err:
                    logger.error(f"FAILED saving user BLOB {user_id} to {file_path}: {img_err}. Skipping BLOB.", exc_info=True)
    except Exception as db_err:
        logger.error(f"Database error querying cappers table for {user_id}/{guild_id}: {db_err}", exc_info=True)
    finally:
        await db_manager.close()

    # CSV Check
    user_urls_csv = load_user_image_urls_from_csv()
    key = f"{guild_id}:{user_id}"
    if key in user_urls_csv:
        csv_url = user_urls_csv[key].get('user_url')
        if csv_url and csv_url.lower().startswith(('http://', 'https://')):
            logger.debug(f"CSV hit user URL ({key}): {csv_url}")
            await cache_manager.set(cache_key, csv_url, ttl=3600)
            return csv_url

    # Discord Avatar Check
    member: Optional[discord.Member] = None
    if interaction and interaction.guild and isinstance(interaction.user, discord.Member) and str(interaction.user.id) == user_id:
        member = interaction.user
    elif interaction and interaction.guild:
        try:
            member = interaction.guild.get_member(user_id_int) or await interaction.guild.fetch_member(user_id_int)
        except Exception as fetch_err:
            logger.error(f"Error fetching member {user_id} in guild {guild_id}: {fetch_err}")

    if member:
        discord_avatar_url = member.display_avatar.url
        display_name = member.display_name
        logger.info(f"Fetched live Discord avatar URL for {key}: {discord_avatar_url}")
        await save_user_image_url_to_csv(guild_id, user_id, display_name, discord_avatar_url)
        await cache_manager.set(cache_key, discord_avatar_url, ttl=3600)
        return discord_avatar_url

    logger.warning(f"Could not find any valid image URL for user {key} (DB/CSV/Discord). Returning default.")
    await cache_manager.set(cache_key, DEFAULT_AVATAR_URL, ttl=600)
    return DEFAULT_AVATAR_URL
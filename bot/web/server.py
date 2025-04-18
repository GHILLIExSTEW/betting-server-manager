"""
Web server for the Discord betting bot.
Provides a RESTful API with admin features and static file serving for the dashboard and guild homepages.
"""
import aiohttp
from aiohttp import web
import asyncio
import logging
from pathlib import Path
from config.settings import BASE_DIR, LOGO_BASE_URL, FERNET_KEY, DEFAULT_AVATAR_URL
from data.db_manager import db_manager
from cryptography.fernet import Fernet, InvalidToken
import json
import base64
from utils.image_utils import get_team_logo_url_from_csv
import discord

logger = logging.getLogger(__name__)

# Define static paths
STATIC_DIR = BASE_DIR / "static"
STATIC_SITE_DIR = BASE_DIR / "web" / "static_site"
GUILDS_DIR = STATIC_SITE_DIR / "guilds"
STATIC_DIR.mkdir(exist_ok=True)
STATIC_SITE_DIR.mkdir(exist_ok=True)
GUILDS_DIR.mkdir(exist_ok=True)

# Define static_path globally
static_path = BASE_DIR / "web" / "static_site"

if not FERNET_KEY:
    raise ValueError("FERNET_KEY is not configured.")
fernet = Fernet(FERNET_KEY.encode())

_web_runner_instance = None

async def authenticate(request: web.Request) -> bool:
    """Check if the request is authenticated with a valid token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise web.HTTPUnauthorized(text="Missing Authorization header")
    try:
        fernet.decrypt(auth_header.encode())
        return True
    except InvalidToken:
        raise web.HTTPUnauthorized(text="Invalid or expired token")
    except Exception as e:
        logger.error(f"Token decrypt error: {e}")
        raise web.HTTPUnauthorized(text="Invalid token format or key")

async def index(request: web.Request) -> web.Response:
    """Serve the main dashboard HTML."""
    return web.FileResponse(BASE_DIR / "web" / "static_site" / "index.html")

async def live_scores_page_handler(request: web.Request) -> web.Response:
    """Serve the live scores page."""
    return web.FileResponse(BASE_DIR / "web" / "static_site" / "live-scores.html")

async def guild_page_handler(request: web.Request) -> web.Response:
    """Serve guild-specific homepage."""
    guild_id = request.match_info.get("guild_id")
    guild_page_path = BASE_DIR / "web" / "static_site" / "guilds" / f"guild{guild_id}" / "index.html"
    if not guild_page_path.exists():
        raise web.HTTPNotFound(text=f"Homepage for guild {guild_id} not found")
    return web.FileResponse(guild_page_path)

async def guild_subpage_handler(request: web.Request) -> web.Response:
    """Serve guild-specific subpages."""
    guild_id = request.match_info.get("guild_id")
    page = request.match_info.get("page")
    guild_page_path = BASE_DIR / "web" / "static_site" / "guilds" / f"guild{guild_id}" / page
    if not guild_page_path.exists():
        raise web.HTTPNotFound(text=f"Page {page} for guild {guild_id} not found")
    return web.FileResponse(guild_page_path)

async def guilds_handler(request: web.Request) -> web.Response:
    """API endpoint to list guild stats."""
    await authenticate(request)
    bot_instance = request.app.get("bot")
    if not bot_instance:
        return web.json_response({"error": "Bot not found"}, status=500)
    try:
        guilds_data = []
        unit_records = await db_manager.fetch("SELECT guild_id, units_monthly FROM unit_records")
        units_map = {str(row['guild_id']): row['units_monthly'] for row in unit_records}
        for guild in bot_instance.guilds:
            guild_id_str = str(guild.id)
            monthly_units = units_map.get(guild_id_str, 0.0)
            guilds_data.append({
                "id": guild.id,
                "name": guild.name,
                "member_count": guild.member_count,
                "monthly_units": float(monthly_units or 0.0)
            })
        return web.json_response(guilds_data)
    except Exception as e:
        logger.error(f"Failed fetch guilds: {e}", exc_info=True)
        return web.json_response({"error": f"Server error fetching guilds: {e}"}, status=500)

async def guild_stats_handler(request: web.Request) -> web.Response:
    """API endpoint to get stats for a specific guild."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    try:
        query = "SELECT guild_id, units_monthly FROM unit_records WHERE guild_id = %s"
        record = await db_manager.fetch_one(query, (guild_id,))
        if not record:
            return web.json_response({"error": f"Guild {guild_id} not found"}, status=404)
        bot_instance = request.app.get("bot")
        guild = bot_instance.get_guild(int(guild_id)) if bot_instance else None
        data = {
            "id": record["guild_id"],
            "name": guild.name if guild else f"Guild {guild_id}",
            "member_count": guild.member_count if guild else 0,
            "monthly_units": float(record.get("units_monthly", 0.0))
        }
        return web.json_response(data)
    except Exception as e:
        logger.error(f"Failed fetch guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def guild_settings_handler(request: web.Request) -> web.Response:
    """API endpoint to get guild settings."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    try:
        query = """
            SELECT embed_channel_1, command_channel_1, admin_channel_1 AS admin_channel_id,
                   embed_channel_2, command_channel_2, admin_role, authorized_role,
                   voice_channel_id, daily_report_time
            FROM server_settings WHERE guild_id = %s
        """
        settings = await db_manager.fetch_one(query, (guild_id,))
        if not settings:
            return web.json_response({"error": f"Settings for guild {guild_id} not found"}, status=404)
        return web.json_response({
            "embed_channel_1": settings.get("embed_channel_1"),
            "command_channel_1": settings.get("command_channel_1"),
            "admin_channel_id": settings.get("admin_channel_id"),
            "embed_channel_2": settings.get("embed_channel_2"),
            "command_channel_2": settings.get("command_channel_2"),
            "admin_role": settings.get("admin_role"),
            "authorized_role": settings.get("authorized_role"),
            "voice_channel_id": settings.get("voice_channel_id"),
            "daily_report_time": settings.get("daily_report_time")
        })
    except Exception as e:
        logger.error(f"Failed fetch settings for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def guild_settings_update_handler(request: web.Request) -> web.Response:
    """API endpoint to update guild settings."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    try:
        data = await request.json()
        query = """
            INSERT INTO server_settings (
                guild_id, embed_channel_1, command_channel_1, admin_channel_1,
                embed_channel_2, command_channel_2, admin_role, authorized_role,
                voice_channel_id, daily_report_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                embed_channel_1 = %s, command_channel_1 = %s, admin_channel_1 = %s,
                embed_channel_2 = %s, command_channel_2 = %s, admin_role = %s,
                authorized_role = %s, voice_channel_id = %s, daily_report_time = %s
        """
        params = (
            guild_id,
            data.get("embed_channel_1"), data.get("command_channel_1"), data.get("admin_channel_id"),
            data.get("embed_channel_2"), data.get("command_channel_2"), data.get("admin_role"),
            data.get("authorized_role"), data.get("voice_channel_id"), data.get("daily_report_time"),
            data.get("embed_channel_1"), data.get("command_channel_1"), data.get("admin_channel_id"),
            data.get("embed_channel_2"), data.get("command_channel_2"), data.get("admin_role"),
            data.get("authorized_role"), data.get("voice_channel_id"), data.get("daily_report_time")
        )
        await db_manager.execute(query, params)
        logger.info(f"Updated settings for guild {guild_id}")
        return web.json_response({"status": "success", "guild_id": guild_id})
    except Exception as e:
        logger.error(f"Failed update settings for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def capper_stats_handler(request: web.Request) -> web.Response:
    """API endpoint to get capper stats for a guild."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    try:
        query = """
            SELECT user_id, SUM(units) AS total_units,
                   SUM(CASE WHEN bet_won = 1 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN bet_loss = 1 THEN 1 ELSE 0 END) AS losses
            FROM bets
            WHERE guild_id = %s
            GROUP BY user_id
        """
        stats = await db_manager.fetch(query, (guild_id,))
        capper_stats = []
        for stat in stats:
            total_bets = stat["wins"] + stat["losses"]
            win_rate = stat["wins"] / total_bets if total_bets > 0 else 0
            capper_stats.append({
                "user_id": stat["user_id"],
                "total_units": float(stat["total_units"] or 0.0),
                "wins": stat["wins"],
                "losses": stat["losses"],
                "win_rate": win_rate
            })
        return web.json_response(capper_stats)
    except Exception as e:
        logger.error(f"Failed fetch capper stats for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def leaderboard_handler(request: web.Request) -> web.Response:
    """API endpoint to get guild leaderboard."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    try:
        query = """
            SELECT u.user_id, u.display_name, SUM(b.units) AS total_units,
                   SUM(CASE WHEN b.bet_won = 1 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN b.bet_loss = 1 THEN 1 ELSE 0 END) AS losses
            FROM bets b
            JOIN users u ON b.user_id = u.user_id
            WHERE b.guild_id = %s
            GROUP BY u.user_id, u.display_name
            ORDER BY total_units DESC
            LIMIT 50
        """
        records = await db_manager.fetch(query, (guild_id,))
        leaderboard = []
        for record in records:
            total_bets = record["wins"] + record["losses"]
            win_rate = record["wins"] / total_bets if total_bets > 0 else 0
            leaderboard.append({
                "user_id": record["user_id"],
                "display_name": record["display_name"],
                "total_units": float(record["total_units"] or 0.0),
                "wins": record["wins"],
                "losses": record["losses"],
                "win_rate": win_rate
            })
        return web.json_response(leaderboard)
    except Exception as e:
        logger.error(f"Failed fetch leaderboard for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def guild_bets_handler(request: web.Request) -> web.Response:
    """API endpoint to get guild bets, optionally filtered by status."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    status = request.query.get("status")  # e.g., 'pending', 'resolved'
    user_id = request.query.get("user_id")
    date_range = request.query.get("date_range")  # e.g., '7d', '30d'
    try:
        query = """
            SELECT bet_serial, user_id, league, team, opponent, units, bet_won, bet_loss, player_id, prop_type, bet_type, game_start
            FROM bets
            WHERE guild_id = %s
        """
        params = [guild_id]
        if status == "pending":
            query += " AND bet_won IS NULL AND bet_loss IS NULL"
        elif status == "resolved":
            query += " AND (bet_won = 1 OR bet_loss = 1)"
        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)
        if date_range:
            if date_range == "7d":
                query += " AND created_at >= NOW() - INTERVAL 7 DAY"
            elif date_range == "30d":
                query += " AND created_at >= NOW() - INTERVAL 30 DAY"
        query += " ORDER BY created_at DESC LIMIT 100"
        bets = await db_manager.fetch(query, tuple(params))
        bet_list = []
        for bet in bets:
            team = bet.get('team')
            opponent = bet.get('opponent')
            league = bet.get('league')
            bet_type = bet.get('bet_type')
            team_logo_url = await get_team_logo_url_from_csv(league, team) if team and league and bet_type != 'prop' else None
            opp_logo_url = await get_team_logo_url_from_csv(league, opponent) if opponent and league and bet_type == 'standard' else None
            bet_list.append({
                "bet_serial": bet.get('bet_serial'),
                "user_id": bet.get('user_id'),
                "league": league,
                "team": team,
                "opponent": opponent,
                "units": float(bet.get('units', 0.0)),
                "bet_won": bet.get('bet_won'),
                "bet_loss": bet.get('bet_loss'),
                "player_id": bet.get('player_id'),
                "prop_type": bet.get('prop_type'),
                "bet_type": bet_type,
                "team_logo": team_logo_url,
                "opponent_logo": opp_logo_url,
                "game_start": bet.get('game_start').isoformat() if bet.get('game_start') else None
            })
        return web.json_response(bet_list)
    except Exception as e:
        logger.error(f"Failed fetch bets for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def news_handler(request: web.Request) -> web.Response:
    """API endpoint to get guild news."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    try:
        query = """
            SELECT news_id, title, content, created_at, posted_by
            FROM news
            WHERE guild_id = %s
            ORDER BY created_at DESC
            LIMIT 20
        """
        news_items = await db_manager.fetch(query, (guild_id,))
        news_list = [
            {
                "news_id": item["news_id"],
                "title": item["title"],
                "content": item["content"],
                "created_at": item["created_at"].isoformat(),
                "posted_by": item["posted_by"]
            }
            for item in news_items
        ]
        return web.json_response(news_list)
    except Exception as e:
        logger.error(f"Failed fetch news for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def news_post_handler(request: web.Request) -> web.Response:
    """API endpoint to post guild news."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    try:
        data = await request.json()
        title = data.get("title")
        content = data.get("content")
        posted_by = data.get("posted_by")
        if not all([title, content, posted_by]):
            return web.json_response({"error": "Missing required fields"}, status=400)
        query = """
            INSERT INTO news (guild_id, title, content, posted_by)
            VALUES (%s, %s, %s, %s)
        """
        await db_manager.execute(query, (guild_id, title, content, posted_by))
        logger.info(f"Posted news for guild {guild_id} by {posted_by}")
        return web.json_response({"status": "success", "message": "News posted"})
    except Exception as e:
        logger.error(f"Failed post news for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def challenges_handler(request: web.Request) -> web.Response:
    """API endpoint to get guild challenges."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    try:
        query = """
            SELECT challenge_id, title, description, start_date, end_date, created_by
            FROM challenges
            WHERE guild_id = %s AND end_date >= NOW()
            ORDER BY start_date ASC
        """
        challenges = await db_manager.fetch(query, (guild_id,))
        challenge_list = [
            {
                "challenge_id": item["challenge_id"],
                "title": item["title"],
                "description": item["description"],
                "start_date": item["start_date"].isoformat(),
                "end_date": item["end_date"].isoformat(),
                "created_by": item["created_by"]
            }
            for item in challenges
        ]
        return web.json_response(challenge_list)
    except Exception as e:
        logger.error(f"Failed fetch challenges for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def challenges_post_handler(request: web.Request) -> web.Response:
    """API endpoint to create a guild challenge."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    try:
        data = await request.json()
        title = data.get("title")
        description = data.get("description")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        created_by = data.get("created_by")
        if not all([title, description, start_date, end_date, created_by]):
            return web.json_response({"error": "Missing required fields"}, status=400)
        query = """
            INSERT INTO challenges (guild_id, title, description, start_date, end_date, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        await db_manager.execute(query, (guild_id, title, description, start_date, end_date, created_by))
        logger.info(f"Created challenge for guild {guild_id} by {created_by}")
        return web.json_response({"status": "success", "message": "Challenge created"})
    except Exception as e:
        logger.error(f"Failed create challenge for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def challenge_leaderboard_handler(request: web.Request) -> web.Response:
    """API endpoint to get leaderboard for a specific challenge."""
    await authenticate(request)
    guild_id = request.match_info.get("guild_id")
    challenge_id = request.match_info.get("challenge_id")
    try:
        query = """
            SELECT u.user_id, u.display_name, SUM(b.units) AS total_units
            FROM bets b
            JOIN users u ON b.user_id = u.user_id
            JOIN challenge_bets cb ON b.bet_serial = cb.bet_serial
            WHERE cb.challenge_id = %s AND b.guild_id = %s
            GROUP BY u.user_id, u.display_name
            ORDER BY total_units DESC
            LIMIT 50
        """
        records = await db_manager.fetch(query, (challenge_id, guild_id))
        leaderboard = [
            {
                "user_id": record["user_id"],
                "display_name": record["display_name"],
                "total_units": float(record["total_units"] or 0.0)
            }
            for record in records
        ]
        return web.json_response(leaderboard)
    except Exception as e:
        logger.error(f"Failed fetch challenge leaderboard for guild {guild_id}, challenge {challenge_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def bets_handler(request: web.Request) -> web.Response:
    """API endpoint to list recent bets, optionally filtered by guild_id."""
    await authenticate(request)
    guild_id = request.query.get("guild_id")
    try:
        query = """
            SELECT bet_serial, user_id, league, team, opponent, units, bet_won, bet_loss, player_id, prop_type, bet_type, game_start
            FROM bets
            WHERE (%s IS NULL OR guild_id = %s)
            ORDER BY created_at DESC LIMIT 50
        """
        bets = await db_manager.fetch(query, (guild_id, guild_id))
        bet_list = []
        for bet_row in bets:
            team = bet_row.get('team')
            opponent = bet_row.get('opponent')
            league = bet_row.get('league')
            bet_type = bet_row.get('bet_type')
            team_logo_url = await get_team_logo_url_from_csv(league, team) if team and league and bet_type != 'prop' else None
            opp_logo_url = await get_team_logo_url_from_csv(league, opponent) if opponent and league and bet_type == 'standard' else None
            bet_data = {
                "bet_serial": bet_row.get('bet_serial'),
                "user_id": bet_row.get('user_id'),
                "league": league,
                "team": team,
                "opponent": opponent,
                "units": float(bet_row.get('units', 0.0)),
                "bet_won": bet_row.get('bet_won'),
                "bet_loss": bet_row.get('bet_loss'),
                "player_id": bet_row.get('player_id'),
                "prop_type": bet_row.get('prop_type'),
                "bet_type": bet_type,
                "team_logo": team_logo_url,
                "opponent_logo": opp_logo_url
            }
            bet_list.append(bet_data)
        return web.json_response(bet_list)
    except Exception as e:
        logger.error(f"Failed fetch bets for guild {guild_id}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error fetching bets: {e}"}, status=500)

async def place_bet_handler(request: web.Request) -> web.Response:
    """API endpoint to place a bet."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        guild_id = data.get("guild_id")
        league = data.get("league")
        bet_type = data.get("bet_type")
        team = data.get("team")
        opponent = data.get("opponent")
        units = float(data.get("units", 0.0))
        if not all([user_id, guild_id, league, bet_type, units]):
            return web.json_response({"error": "Missing required fields"}, status=400)
        query = """
            INSERT INTO bets (user_id, guild_id, league, bet_type, team, opponent, units)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        await db_manager.execute(query, (user_id, guild_id, league, bet_type, team, opponent, units))
        logger.info(f"Placed bet for user {user_id} in guild {guild_id}: {units} units")
        return web.json_response({"status": "success", "message": "Bet placed"})
    except ValueError:
        return web.json_response({"error": "Invalid units format"}, status=400)
    except Exception as e:
        logger.error(f"Failed place bet: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def bet_detail_handler(request: web.Request) -> web.Response:
    """API endpoint to get details of a specific bet."""
    await authenticate(request)
    bet_serial_str = request.match_info.get("bet_serial")
    if not bet_serial_str:
        return web.json_response({"error": "Missing bet_serial"}, status=400)
    try:
        bet_serial = int(bet_serial_str)
        query = """
            SELECT bet_serial, user_id, league, team, opponent, units, bet_won, bet_loss, game_start, player_id, prop_type, bet_type
            FROM bets WHERE bet_serial = %s
        """
        bet = await db_manager.fetch_one(query, (bet_serial,))
        if not bet:
            return web.json_response({"error": f"Bet {bet_serial} not found"}, status=404)
        team = bet.get('team')
        opponent = bet.get('opponent')
        league = bet.get('league')
        game_start = bet.get('game_start')
        bet_type = bet.get('bet_type')
        team_logo_url = await get_team_logo_url_from_csv(league, team) if team and league else None
        opp_logo_url = await get_team_logo_url_from_csv(league, opponent) if opponent and league and bet_type == 'standard' else None
        bet_data = {
            "bet_serial": bet.get('bet_serial'),
            "user_id": bet.get('user_id'),
            "league": league,
            "team": team,
            "opponent": opponent,
            "units": float(bet.get('units', 0.0)),
            "bet_won": bet.get('bet_won'),
            "bet_loss": bet.get('bet_loss'),
            "game_start": game_start.isoformat() if game_start else None,
            "player_id": bet.get('player_id'),
            "prop_type": bet.get('prop_type'),
            "bet_type": bet_type,
            "team_logo": team_logo_url,
            "opponent_logo": opp_logo_url
        }
        return web.json_response(bet_data)
    except ValueError:
        return web.json_response({"error": "Invalid bet_serial"}, status=400)
    except Exception as e:
        logger.error(f"Failed fetch bet {bet_serial_str}: {e}", exc_info=True)
        return web.json_response({"error": f"Server error fetching bet: {e}"}, status=500)

async def leagues_handler(request: web.Request) -> web.Response:
    """API endpoint to list supported leagues."""
    try:
        leagues = [
            "BUNDESLIGA", "CFL", "EPL", "LALIGA", "LIGUE1", "MLB", "MLS", "NBA",
            "NCAAF", "NCAAM", "NCAAW", "NCAAWVB", "NFL", "NHL", "SERIEA", "WNBA",
            "PGA", "LPGA", "EUROPEANTOUR", "MASTERS", "ESPORTS_PLAYERS", "CSGO",
            "LOL", "VALORANT", "NASCAR", "ATP", "WTA", "UFC", "HORSERACING", "KENTUCKY_DERBY"
        ]
        return web.json_response(leagues)
    except Exception as e:
        logger.error(f"Failed fetch leagues: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def verify_user_handler(request: web.Request) -> web.Response:
    """API endpoint to verify user for paid guild access."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        query = """
            SELECT s.guild_id
            FROM subscribers s
            JOIN bets b ON b.guild_id = s.guild_id
            WHERE b.user_id = %s AND s.subscription_status IN ('paid', 'active')
        """
        guilds = await db_manager.fetch(query, (user_id,))
        if not guilds:
            return web.json_response({"error": "User not in a paid guild or not verified"}, status=403)
        token = fernet.encrypt(user_id.encode()).decode()
        return web.json_response({"token": token})
    except Exception as e:
        logger.error(f"Failed verify user: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def live_scores_handler(request: web.Request) -> web.Response:
    """API endpoint to get live scores (placeholder)."""
    await authenticate(request)
    try:
        scores = [
            {"league": "NBA", "match": "Lakers vs Celtics", "score": "85-90", "status": "Q3"},
            {"league": "NFL", "match": "Chiefs vs Eagles", "score": "14-7", "status": "Half"},
        ]
        return web.json_response(scores)
    except Exception as e:
        logger.error(f"Failed fetch live scores: {e}", exc_info=True)
        return web.json_response({"error": f"Server error: {e}"}, status=500)

async def test_handler(request: web.Request) -> web.Response:
    """Test endpoint to confirm server is running."""
    return web.json_response({"status": "Server is running"})

async def setup_server(bot) -> web.Application:
    """Set up the web server application instance."""
    app = web.Application()
    app["bot"] = bot

    # Routes
    app.router.add_get("/", index)
    app.router.add_get("/live-scores.html", live_scores_page_handler)
    app.router.add_get("/guilds/{guild_id}", guild_page_handler)
    app.router.add_get("/guilds/{guild_id}/{page}", guild_subpage_handler)
    app.router.add_get("/api/guilds", guilds_handler)
    app.router.add_get("/api/guilds/{guild_id}", guild_stats_handler)
    app.router.add_get("/api/guilds/{guild_id}/settings", guild_settings_handler)
    app.router.add_post("/api/guilds/{guild_id}/settings", guild_settings_update_handler)
    app.router.add_get("/api/guilds/{guild_id}/capper-stats", capper_stats_handler)
    app.router.add_get("/api/guilds/{guild_id}/leaderboard", leaderboard_handler)
    app.router.add_get("/api/guilds/{guild_id}/bets", guild_bets_handler)
    app.router.add_get("/api/guilds/{guild_id}/news", news_handler)
    app.router.add_post("/api/guilds/{guild_id}/news", news_post_handler)
    app.router.add_get("/api/guilds/{guild_id}/challenges", challenges_handler)
    app.router.add_post("/api/guilds/{guild_id}/challenges", challenges_post_handler)
    app.router.add_get("/api/guilds/{guild_id}/challenges/{challenge_id}/leaderboard", challenge_leaderboard_handler)
    app.router.add_get("/api/bets", bets_handler)
    app.router.add_post("/api/bets", place_bet_handler)
    app.router.add_get("/api/bet/{bet_serial}", bet_detail_handler)
    app.router.add_get("/api/leagues", leagues_handler)
    app.router.add_post("/api/verify-user", verify_user_handler)
    app.router.add_get("/api/live-scores", live_scores_handler)
    app.router.add_get("/test", test_handler)

    # Favicon
    async def favicon(request: web.Request) -> web.Response:
        return web.FileResponse(STATIC_DIR / "favicon.ico")
    app.router.add_get("/favicon.ico", favicon)

    # Static files
    if not static_path.is_dir():
        logger.warning(f"Static directory not found at: {static_path}. Creating.")
        static_path.mkdir(parents=True, exist_ok=True)
    app.router.add_static("/static", static_path / "static", name="static", show_index=True)
    app.router.add_static("/guilds", static_path / "guilds", name="guilds", show_index=True)

    logger.info("Web application setup complete.")
    return app

async def start_server(app: web.Application, host: str = "0.0.0.0", port: int = 25594) -> None:
    """Start the web server."""
    global _web_runner_instance
    runner = web.AppRunner(app)
    await runner.setup()
    _web_runner_instance = runner
    site = web.TCPSite(runner, host, port)
    try:
        await site.start()
        logger.info(f"Web server started at http://{host}:{port}/")
    except Exception as e:
        logger.error(f"Failed to start web server: {e}", exc_info=True)
        await runner.cleanup()
        _web_runner_instance = None
        raise

async def stop_server() -> None:
    """Stop the web server."""
    global _web_runner_instance
    runner = _web_runner_instance
    if runner:
        await runner.cleanup()
        logger.info("Web server stopped and cleaned up.")
        _web_runner_instance = None
    else:
        logger.info("Web server runner not found, skipping cleanup.")
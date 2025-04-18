"""
Web server for the Discord betting bot.
Provides a RESTful API with admin features and static file serving for the dashboard.
Rearranged function order for debugging syntax error.
"""

import aiohttp
from aiohttp import web
import asyncio
import logging
import os
from pathlib import Path
# Ensure settings are loaded correctly elsewhere before this is imported
from config.settings import BASE_DIR, LOGO_BASE_URL, FERNET_KEY, DEFAULT_AVATAR_URL
# Ensure db_manager is the initialized instance
from data.db_manager import db_manager
from cryptography.fernet import Fernet, InvalidToken
import json
import base64
# Use correct logo function name
from utils.image_utils import get_team_logo_url_from_csv
import discord  # Keep if discord types are needed

logger = logging.getLogger(__name__)

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

if not FERNET_KEY:
    raise ValueError("FERNET_KEY is not configured.")
fernet = Fernet(FERNET_KEY.encode())

# --- Server Setup and Control Functions (Moved to Top) ---

async def setup_server(bot) -> web.Application:
    """Set up the web server application instance."""
    app = web.Application()
    app["bot"] = bot  # Store bot instance in app context

    # Add routes (Handlers defined below)
    app.router.add_get("/", index)
    app.router.add_get("/api/guilds", guilds_handler)
    app.router.add_get("/api/bets", bets_handler)
    app.router.add_get("/api/bet/{bet_serial}", bet_detail_handler)
    app.router.add_post("/api/set_channel", set_channel_handler)
    app.router.add_post("/api/update_bet", update_bet_handler)

    # Add favicon route
    async def favicon(request: web.Request) -> web.Response:
        return web.FileResponse(STATIC_DIR / "favicon.ico")
    app.router.add_get("/favicon.ico", favicon)

    static_path = BASE_DIR / "static"
    if not static_path.is_dir():
        logger.warning(f"Static directory not found at: {static_path}. Creating.")
        static_path.mkdir(parents=True, exist_ok=True)
    app.router.add_static("/static", static_path, name="static", show_index=True)

    logger.info("Web application setup complete.")
    return app

_web_runner_instance = None  # Module-level variable for runner

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

# --- Request Handler Functions ---

async def index(request: web.Request) -> web.Response:
    """Serve the main dashboard HTML."""
    html = """<!DOCTYPE html><html><head><title>Betting Bot Dashboard</title><style>body{font-family:Arial,sans-serif;margin:20px}h1,h2{color:#333}table{border-collapse:collapse;width:100%;margin-bottom:20px}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background-color:#f2f2f2}.form-container{margin-top:20px}input,select,button{margin:5px;padding:5px}pre{white-space:pre-wrap}img{width:24px;height:24px;vertical-align:middle;margin-right:5px}</style></head><body><h1>Betting Bot Dashboard</h1><p>Enter admin token: <input type="text" id="token" placeholder="Token"><button onclick="setToken()">Submit</button></p><h2>Guild Stats</h2><pre id="guild-stats"></pre><h2>Recent Bets</h2><table id="bets-table"><thead><tr><th>Serial</th><th>User</th><th>League</th><th>Bet Details</th><th>Units</th><th>Outcome</th><th>Action</th></tr></thead><tbody></tbody></table><div class="form-container"><h2>Set Total Units Channel</h2><input type="text" id="guild-id" placeholder="Guild ID"><input type="text" id="channel-id" placeholder="Voice Channel ID"><button onclick="setChannel()">Set Channel</button><p id="set-channel-result"></p></div><div class="form-container"><h2>Edit Bet Outcome</h2><input type="text" id="edit-bet-serial" placeholder="Bet Serial"><select id="edit-status"><option value="pending">Pending</option><option value="won">Won</option><option value="lost">Lost</option><option value="void">Void</option></select><button onclick="updateBet()">Update Bet</button><p id="update-bet-result"></p></div><script>let authToken='';function setToken(){authToken=document.getElementById('token').value;fetchData()}async function fetchData(){if(!authToken){console.log("Token not set.");return}const headers={'Authorization':authToken};try{const statsResponse=await fetch('/api/guilds',{headers});if(!statsResponse.ok)throw new Error(`Stats fetch failed: ${statsResponse.status}`);const stats=await statsResponse.json();document.getElementById('guild-stats').textContent=JSON.stringify(stats,null,2);const betsResponse=await fetch('/api/bets',{headers});if(!betsResponse.ok)throw new Error(`Bets fetch failed: ${betsResponse.status}`);const bets=await betsResponse.json();const table=document.getElementById('bets-table');table.querySelector('tbody').innerHTML='';const tbody=table.querySelector('tbody');bets.forEach(bet=>{const row=tbody.insertRow();let teamLogoHtml=bet.team_logo?`<img src="${bet.team_logo}" alt="${bet.team||''} logo">`:'';let oppLogoHtml=bet.opponent_logo?`<img src="${bet.opponent_logo}" alt="${bet.opponent||''} logo">`:'';let betDetails=bet.bet_type==='prop'?`Player ${bet.player_id||'N/A'} (${bet.prop_type||''}): ${bet.opponent||'N/A'}`:`${teamLogoHtml}${bet.team||'N/A'} vs ${oppLogoHtml}${bet.opponent||'N/A'}`;let outcome=bet.bet_won===1?'Won':(bet.bet_loss===1?'Lost':'Pending');row.innerHTML=`<td>${bet.bet_serial||'N/A'}</td><td>${bet.user_id||'N/A'}</td><td>${bet.league||'N/A'}</td><td>${betDetails}</td><td>${bet.units||0}</td><td>${outcome}</td><td><button onclick="loadBet('${bet.bet_serial||''}', '${outcome.toLowerCase()}')">Edit</button></td>`})}catch(error){console.error('Error fetching data:',error);document.getElementById('guild-stats').textContent=`Error: ${error.message}`;document.getElementById('bets-table').querySelector('tbody').innerHTML='<tr><td colspan="7">Error loading data. Check token/console.</td></tr>'}}async function setChannel(){if(!authToken){alert("Submit token first.");return}const guildId=document.getElementById('guild-id').value;const channelId=document.getElementById('channel-id').value;const headers={'Authorization':authToken,'Content-Type':'application/json'};try{const response=await fetch('/api/set_channel',{method:'POST',headers,body:JSON.stringify({guild_id:guildId,voice_channel_id:channelId})});const result=await response.json();document.getElementById('set-channel-result').textContent=JSON.stringify(result,null,2);if(response.ok)fetchData()}catch(error){console.error('Error setting channel:',error);document.getElementById('set-channel-result').textContent=`Error: ${error.message}`}}function loadBet(betSerial,currentStatus){document.getElementById('edit-bet-serial').value=betSerial;document.getElementById('edit-status').value=currentStatus}async function updateBet(){if(!authToken){alert("Submit token first.");return}const betSerial=document.getElementById('edit-bet-serial').value;const status=document.getElementById('edit-status').value;const headers={'Authorization':authToken,'Content-Type':'application/json'};try{const response=await fetch('/api/update_bet',{method:'POST',headers,body:JSON.stringify({bet_serial:betSerial,status:status})});const result=await response.json();document.getElementById('update-bet-result').textContent=JSON.stringify(result,null,2);if(response.ok)fetchData()}catch(error){console.error('Error updating bet:',error);document.getElementById('update-bet-result').textContent=`Error: ${error.message}`}}</script></body></html>"""
    return web.Response(text=html, content_type="text/html")

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

async def guilds_handler(request: web.Request) -> web.Response:
    """API endpoint to list guild stats."""
    await authenticate(request)
    bot_instance = request.app.get("bot")
    if not bot_instance:
        return web.json_response({"error": "Bot not found"}, status=500)
    try:
        guilds_data = []
        unit_records = await db_manager.fetch("SELECT guild_id, units_monthly FROM unit_records")  # Ensure units_monthly exists
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

# --- bets_handler Function (Standard Spaces Indentation) ---
async def bets_handler(request: web.Request) -> web.Response:
    """API endpoint to list recent bets."""
    await authenticate(request)
    try:
        query = """ SELECT bet_serial, user_id, league, team, opponent, units, bet_won, bet_loss, player_id, prop_type, bet_type, game_start FROM bets ORDER BY created_at DESC LIMIT 50 """
        bets = await db_manager.fetch(query)
        bet_list = []
        for bet_row in bets:
            team = bet_row.get('team')
            opponent = bet_row.get('opponent')
            league = bet_row.get('league')
            bet_type = bet_row.get('bet_type')
            # Fetch logo URL from CSV helper
            team_logo_url = await get_team_logo_url_from_csv(league, team) if team and league and bet_type != 'prop' else None
            opp_logo_url = await get_team_logo_url_from_csv(league, opponent) if opponent and league and bet_type == 'standard' else None
            bet_data = {
                "bet_serial": bet_row.get('bet_serial'),
                "user_id": bet_row.get('user_id'),
                "league": league,
                "team": team,
                "opponent": opponent,  # Holds prop target for prop bets
                "units": float(bet_row.get('units', 0.0)),
                "bet_won": bet_row.get('bet_won'),  # Send raw values
                "bet_loss": bet_row.get('bet_loss'),  # Send raw values
                "player_id": bet_row.get('player_id'),
                "prop_type": bet_row.get('prop_type'),  # Prop type (e.g., 'points')
                "bet_type": bet_type,  # 'standard' or 'prop'
                "team_logo": team_logo_url,  # Use URL from CSV helper
                "opponent_logo": opp_logo_url  # Use URL from CSV helper
            }
            bet_list.append(bet_data)
        return web.json_response(bet_list)
    except Exception as e:
        logger.error(f"Failed fetch bets: {e}", exc_info=True)
        return web.json_response({"error": f"Server error fetching bets: {e}"}, status=500)
# --- End bets_handler ---

# --- set_channel_handler Function (Ensure Correct Indentation) ---
async def set_channel_handler(request: web.Request) -> web.Response:
    """API endpoint to set the Total Units voice channel for a guild."""
    await authenticate(request)
    bot_instance = request.app.get("bot")
    if not bot_instance:
        return web.json_response({"error": "Bot instance not found"}, status=500)
    try:
        data = await request.json()
        guild_id = int(data.get("guild_id", 0))
        voice_channel_id = int(data.get("voice_channel_id", 0))

        if not guild_id or not voice_channel_id:
            return web.json_response({"error": "Missing guild_id or voice_channel_id"}, status=400)

        guild = bot_instance.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": f"Guild {guild_id} not found"}, status=404)

        channel = guild.get_channel(voice_channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            ch_type = type(channel).__name__ if channel else 'None'
            return web.json_response({"error": f"Channel {voice_channel_id} is not a voice channel (type: {ch_type})"}, status=400)

        await db_manager.execute(
            """ INSERT INTO server_settings (guild_id, voice_channel_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE voice_channel_id = VALUES(voice_channel_id) """,
            (guild_id, voice_channel_id)
        )
        logger.info(f"Set Total Units channel {voice_channel_id} for guild {guild_id}")
        return web.json_response({"status": "success", "guild_id": guild_id, "voice_channel_id": voice_channel_id})
    except ValueError:
        return web.json_response({"error": "Invalid guild_id or voice_channel_id (must be numbers)"}, status=400)
    except Exception as e:
        logger.error(f"Failed to set channel: {e}", exc_info=True)
        return web.json_response({"error": f"Internal server error setting channel: {e}"}, status=500)
# --- End set_channel_handler ---

# --- bet_detail_handler Function (Corrected Indentation) ---
async def bet_detail_handler(request: web.Request) -> web.Response:
    """API endpoint to get details of a specific bet."""
    await authenticate(request)
    bet_serial_str = request.match_info.get("bet_serial")
    if not bet_serial_str:
        return web.json_response({"error": "Missing bet_serial"}, status=400)

    try:
        bet_serial = int(bet_serial_str)
        query = """ SELECT bet_serial, user_id, league, team, opponent, units, bet_won, bet_loss, game_start, player_id, prop_type, bet_type FROM bets WHERE bet_serial = %s """
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
# --- End bet_detail_handler ---

async def update_bet_handler(request: web.Request) -> web.Response:
    """API endpoint to update a bet's outcome."""
    await authenticate(request)
    try:
        data = await request.json()
        bet_serial = int(data.get("bet_serial", 0))
        new_status_str = data.get("status")
        if not bet_serial or new_status_str not in ["pending", "won", "lost", "void"]:
            return web.json_response({"error": "Missing or invalid bet_serial/status"}, status=400)
        bet = await db_manager.fetch_one("SELECT user_id, guild_id, units, bet_won, bet_loss FROM bets WHERE bet_serial = %s", (bet_serial,))
        if not bet:
            return web.json_response({"error": f"Bet {bet_serial} not found"}, status=404)

        units = float(bet.get('units', 0.0))
        current_won = bet.get('bet_won')
        current_loss = bet.get('bet_loss')
        user_id = bet.get('user_id')
        guild_id = bet.get('guild_id')

        old_status_str = "pending"
        if current_won == 1:
            old_status_str = "won"
        elif current_loss == 1:
            old_status_str = "lost"
        elif current_won == 0 and current_loss == 0:
            old_status_str = "void"

        if old_status_str == new_status_str:
            return web.json_response({"status": "no_change", "bet_serial": bet_serial, "new_status": new_status_str})

        set_won = None
        set_loss = None
        if new_status_str == "won":
            set_won = 1
            set_loss = 0
        elif new_status_str == "lost":
            set_won = 0
            set_loss = 1
        elif new_status_str == "void":
            set_won = 0
            set_loss = 0
        elif new_status_str == "pending":
            set_won = None
            set_loss = None

        rows_affected = await db_manager.execute("UPDATE bets SET bet_won = %s, bet_loss = %s WHERE bet_serial = %s", (set_won, set_loss, bet_serial))
        if rows_affected == 0:
            return web.json_response({"error": f"Bet {bet_serial} update failed (maybe already updated?)"}, status=500)

        adjustment = 0.0
        if old_status_str in ["pending", "void"]:
            if new_status_str == "won":
                adjustment = units
            elif new_status_str == "lost":
                adjustment = -units
        elif old_status_str == "won":
            if new_status_str == "lost":
                adjustment = -units * 2
            elif new_status_str in ["pending", "void"]:
                adjustment = -units
        elif old_status_str == "lost":
            if new_status_str == "won":
                adjustment = units * 2
            elif new_status_str in ["pending", "void"]:
                adjustment = units

        if adjustment != 0.0 and user_id and guild_id:
            try:
                unit_update_query = """
                    INSERT INTO unit_records (guild_id, user_id, units_monthly, units_yearly)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        units_monthly = units_monthly + VALUES(units_monthly),
                        units_yearly = units_yearly + VALUES(units_yearly)
                """
                await db_manager.execute(unit_update_query, (guild_id, user_id, adjustment, adjustment))
                logger.info(f"Web Adjusted units {user_id} in guild {guild_id}: {adjustment:.2f} for bet {bet_serial}")
            except Exception as unit_update_e:
                logger.error(f"Failed to update unit_records for bet {bet_serial} (user {user_id}/guild {guild_id}): {unit_update_e}")
        elif adjustment != 0.0:
            logger.warning(f"Web Cannot adjust units for bet {bet_serial} - missing user_id ({user_id}) or guild_id ({guild_id})")

        logger.info(f"Updated bet {bet_serial} via web: {old_status_str} -> {new_status_str}")
        return web.json_response({"status": "success", "bet_serial": bet_serial, "new_status": new_status_str})
    except ValueError:
        return web.json_response({"error": "Invalid bet_serial (must be a number)"}, status=400)
    except Exception as e:
        logger.error(f"Failed update bet via web: {e}", exc_info=True)
        return web.json_response({"error": f"Server error updating bet: {e}"}, status=500)
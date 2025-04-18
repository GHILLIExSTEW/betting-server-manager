#   bot/services/stats_handler.py

import logging
import discord
from discord import app_commands, Interaction
from discord.ui import View, Select
import io
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
from PIL import Image, ImageDraw, ImageFilter
import aiohttp
from bot.data.db_manager import DatabaseManager
from config.settings import LOGO_BASE_URL, DEFAULT_AVATAR_URL
from typing import Optional, List, Dict, Any # Import Dict, Any, List
import asyncio
import numpy as np
from datetime import datetime

db_manager = DatabaseManager()
logger = logging.getLogger(__name__)

# (fetch_image, apply_circular_mask, add_shadow functions as before)
async def fetch_image(url: str) -> Optional[bytes]:
    if not url: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200 and 'image' in response.headers.get('Content-Type', '').lower(): return await response.read()
                logger.error(f"Failed fetch image status {response.status} for {url}"); return None
    except Exception as e: logger.error(f"Error fetching image from {url}: {e}"); return None

def apply_circular_mask(image: Image.Image) -> Image.Image:
    try:
        mask = Image.new("L", image.size, 0); draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, image.size[0], image.size[1]), fill=255)
        image_copy = image.copy(); image_copy.putalpha(mask); return image_copy
    except Exception as e: logger.error(f"Error applying circular mask: {e}"); return image

def add_shadow(image: Image.Image) -> Image.Image:
     try:
        image = image.convert("RGBA"); shadow_offset = 5; shadow_blur = 5; border = shadow_offset + shadow_blur
        shadow_size = (image.size[0] + 2 * border, image.size[1] + 2 * border)
        composite = Image.new("RGBA", shadow_size, (0, 0, 0, 0)); shadow_layer = Image.new("RGBA", shadow_size, (0,0,0,0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.ellipse((border - shadow_offset, border - shadow_offset, shadow_size[0] - border + shadow_offset, shadow_size[1] - border + shadow_offset), fill=(100, 100, 100, 180))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_blur)); composite.paste(shadow_layer, (0,0), shadow_layer); composite.paste(image, (border, border), image)
        return composite
     except Exception as e: logger.error(f"Error adding shadow: {e}"); return image


class ChannelSelectForStats(Select):
    def __init__(self, capper_id: int, guild: discord.Guild):
        options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in guild.text_channels]
        if not options: options = [discord.SelectOption(label="No text channels found", value="none")]
        super().__init__(placeholder="Select Channel To Send Stats", options=options, min_values=1, max_values=1)
        self.capper_id = capper_id; self.guild = guild

    async def callback(self, interaction: Interaction):
        channel_id_str = self.values[0]
        if channel_id_str == "none": await interaction.response.send_message("No valid channel selected.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            channel_id = int(channel_id_str); channel = self.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel): await interaction.followup.send(f"Channel not found.", ephemeral=True); return

            # Fetch capper info
            capper_query = "SELECT display_name, image_url FROM cappers WHERE user_id = %s AND guild_id = %s" # Assuming cappers are per-guild
            capper_info = await db_manager.fetch_one(capper_query, (self.capper_id, self.guild.id))
            if not capper_info:
                 member = self.guild.get_member(self.capper_id)
                 if member: display_name = member.display_name; image_url = member.display_avatar.url if member.display_avatar else DEFAULT_AVATAR_URL
                 else: display_name = f"User {self.capper_id}"; image_url = DEFAULT_AVATAR_URL
                 logger.warning(f"Capper info not in DB for {self.capper_id}, using Discord profile.")
            else: display_name = capper_info.get('display_name', f"User {self.capper_id}"); image_url = capper_info.get('image_url', DEFAULT_AVATAR_URL)

            # --- Updated Stats Query ---
            stats_query = """
                SELECT
                    SUM(CASE WHEN bet_won = 1 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN bet_loss = 1 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN bet_won IS NULL AND bet_loss IS NULL THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN bet_won = 1 THEN units ELSE 0 END) as units_won,
                    SUM(CASE WHEN bet_loss = 1 THEN units ELSE 0 END) as units_lost,
                    (SELECT league FROM bets WHERE user_id = %s AND guild_id = %s GROUP BY league ORDER BY COUNT(*) DESC LIMIT 1) as top_league
                FROM bets WHERE user_id = %s AND guild_id = %s
            """
            result = await db_manager.fetch_one(stats_query, (self.capper_id, self.guild.id, self.capper_id, self.guild.id))
            # --- End Updated Stats Query ---

            wins = 0; losses = 0; pending = 0; units_won = 0.0; units_lost = 0.0; top_league = "N/A"
            if result:
                 wins = int(result.get('wins', 0) or 0); losses = int(result.get('losses', 0) or 0); pending = int(result.get('pending', 0) or 0)
                 units_won = float(result.get('units_won', 0.0) or 0.0); units_lost = float(result.get('units_lost', 0.0) or 0.0)
                 top_league = result.get('top_league', "N/A")
            total_units = units_won - units_lost

            # --- Updated Timeline Query ---
            timeline_query = """
                SELECT game_start,
                       CASE WHEN bet_won = 1 THEN units WHEN bet_loss = 1 THEN -units ELSE 0 END as net_units
                FROM bets
                WHERE user_id = %s AND guild_id = %s AND (bet_won = 1 OR bet_loss = 1) AND game_start IS NOT NULL
                ORDER BY game_start ASC
            """
            timeline_results = await db_manager.fetch(timeline_query, (self.capper_id, self.guild.id))
            # --- End Updated Timeline Query ---

            profile_data = await fetch_image(image_url)

            # --- Generate Plot (Code largely unchanged) ---
            plt.switch_backend('Agg'); fig = plt.figure(figsize=(12, 10));
            gs = gridspec.GridSpec(3, 2, height_ratios=[1, 1.5, 2], width_ratios=[1, 1], figure=fig, hspace=0.5, wspace=0.3)
            ax_profile = fig.add_subplot(gs[0, 0]); ax_text = fig.add_subplot(gs[1, 0]); ax_pie = fig.add_subplot(gs[1, 1]); ax_trend = fig.add_subplot(gs[2, :])
            # Profile image
            ax_profile.set_title("Capper Image", fontsize=12)
            if profile_data:
                 try: img = Image.open(io.BytesIO(profile_data)).convert("RGBA").resize((120, 120), Image.LANCZOS); img = apply_circular_mask(img); ax_profile.imshow(img)
                 except Exception as img_err: logger.error(f"Img error {self.capper_id}: {img_err}"); ax_profile.text(0.5, 0.5, "Img Error", ha='center', va='center')
                 finally: ax_profile.axis('off')
            else: ax_profile.text(0.5, 0.5, "No Image", ha='center', va='center'); ax_profile.axis('off')
            # Text stats
            ax_text.set_title("Overall Stats", fontsize=12)
            win_rate = f"{wins / (wins + losses) * 100:.1f}%" if (wins + losses) > 0 else "N/A"
            stats_text = (f"Record: {wins} W - {losses} L ({win_rate} WR)\nPending: {pending}\nTop League: {top_league}\n\nUnits Won: {units_won:.2f}\nUnits Lost: {units_lost:.2f}\nTotal Units: {total_units:.2f}")
            ax_text.text(0.05, 0.95, stats_text, fontsize=11, ha='left', va='top', linespacing=1.4); ax_text.axis('off')
            # Pie chart
            ax_pie.set_title("Bet Outcomes (W/L/P)", fontsize=12)
            sizes = [wins, losses, pending]; labels = [f'Wins ({wins})', f'Losses ({losses})', f'Pending ({pending})']; colors = ['#4CAF50', '#F44336', '#FFC107']
            non_zero_sizes = [s for s in sizes if s > 0]; non_zero_labels = [labels[i] for i, s in enumerate(sizes) if s > 0]; non_zero_colors = [colors[i] for i, s in enumerate(sizes) if s > 0]
            if sum(non_zero_sizes) > 0: ax_pie.pie(non_zero_sizes, labels=non_zero_labels, colors=non_zero_colors, autopct='%1.1f%%', startangle=90, pctdistance=0.85); ax_pie.axis('equal')
            else: ax_pie.text(0.5, 0.5, "No Bet Data", ha='center', va='center', fontsize=12); ax_pie.axis('off')
            # Trend line
            ax_trend.set_title("Cumulative Units Over Time", fontsize=12)
            if timeline_results:
                valid_timeline = [(row['game_start'], float(row['net_units'])) for row in timeline_results if isinstance(row.get('game_start'), datetime) and row.get('net_units') is not None]
                if valid_timeline:
                     valid_timeline.sort(key=lambda x: x[0]); dates = mdates.date2num([row[0] for row in valid_timeline]); cumulative_units = np.cumsum([row[1] for row in valid_timeline])
                     ax_trend.plot_date(dates, cumulative_units, linestyle='solid', marker=None); ax_trend.set_xlabel("Time"); ax_trend.set_ylabel("Cumulative Net Units")
                     ax_trend.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d')); fig.autofmt_xdate(); ax_trend.grid(True)
                else: ax_trend.text(0.5, 0.5, "No Valid Timeline Data", ha='center', va='center', fontsize=12); ax_trend.grid(False); ax_trend.set_xticklabels([]); ax_trend.set_yticklabels([])
            else: ax_trend.text(0.5, 0.5, "No Timeline Data Available", ha='center', va='center', fontsize=12); ax_trend.grid(False); ax_trend.set_xticklabels([]); ax_trend.set_yticklabels([])
            ax_trend.tick_params(axis='x', labelsize=8); ax_trend.tick_params(axis='y', labelsize=8)
            # Finalize plot
            fig.suptitle(f"{display_name}'s Betting Stats", fontsize=16, weight='bold'); fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            buf = io.BytesIO(); fig.savefig(buf, format='png', bbox_inches='tight', dpi=100); buf.seek(0); plt.close(fig)

            # --- Send Plot ---
            file = discord.File(fp=buf, filename=f'{display_name}_stats.png')
            try: await channel.send(file=file); await interaction.followup.send("Stats sent successfully.", ephemeral=True)
            except discord.Forbidden: logger.error(f"Cannot send file in {channel.id}."); await interaction.followup.send(f"Error: Cannot send stats to {channel.mention}.", ephemeral=True)
            except Exception as send_err: logger.error(f"Error sending stats: {send_err}"); await interaction.followup.send("Error sending stats.", ephemeral=True)
        except Exception as e: logger.error(f"Error generating stats {self.capper_id}: {e}", exc_info=True); await interaction.followup.send("Internal error generating stats.", ephemeral=True)
        finally: plt.close('all')

# Updated CapperSelect to accept pre-fetched list
class CapperSelect(Select):
    def __init__(self, cappers_list: List[Dict[str, Any]]): # Accept list of dicts
        options = [
            discord.SelectOption(label=capper['display_name'], value=str(capper['user_id']))
            for capper in cappers_list
        ] if cappers_list else [discord.SelectOption(label="No cappers registered", value="none")]
        super().__init__(placeholder="Select Capper", options=options, min_values=1, max_values=1, custom_id="capper_select_stats")

    async def callback(self, interaction: Interaction):
        capper_id_str = self.values[0]
        if capper_id_str == "none": await interaction.response.send_message("No capper selected.", ephemeral=True); return
        if not interaction.guild: await interaction.response.send_message("Guild context lost.", ephemeral=True); return
        view = View(timeout=60); view.add_item(ChannelSelectForStats(int(capper_id_str), interaction.guild))
        # Respond to the Select interaction before sending the new view
        await interaction.response.send_message("Now select a channel to send the stats:", view=view, ephemeral=True)


async def stats_command_handler(interaction: Interaction):
    if not interaction.guild: await interaction.response.send_message("Use in a server.", ephemeral=True); return
    try: # Fetch cappers within the handler
        query = "SELECT user_id, display_name FROM cappers WHERE guild_id = %s ORDER BY display_name"
        cappers = await db_manager.fetch(query, (interaction.guild.id,))
    except Exception as e: logger.error(f"Failed fetch cappers {interaction.guild.id}: {e}"); await interaction.response.send_message("Failed load cappers.", ephemeral=True); return
    if not cappers: await interaction.response.send_message("No cappers registered.", ephemeral=True); return

    view = View(timeout=120); view.add_item(CapperSelect(cappers)) # Pass fetched list
    await interaction.response.send_message("Select a capper:", view=view, ephemeral=True)
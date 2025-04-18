#   bot/services/profile_handler.py

import logging
import discord
from discord import Interaction
from discord.ui import View, Select
import io
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from PIL import Image, ImageDraw, ImageFilter
import aiohttp
from bot.data.db_manager import DatabaseManager
from config.settings import LOGO_BASE_URL, DEFAULT_AVATAR_URL
from typing import Optional
from datetime import datetime # Import datetime

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

class ChannelSelectForProfile(Select):
    def __init__(self, user: discord.User, guild: discord.Guild):
        options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in guild.text_channels]
        if not options: options = [discord.SelectOption(label="No text channels found", value="none")]
        super().__init__(placeholder="Select Channel To Send Profile", options=options, min_values=1, max_values=1)
        self.user = user; self.guild = guild

    async def callback(self, interaction: Interaction):
        channel_id_str = self.values[0]
        if channel_id_str == "none": await interaction.response.send_message("No valid channel selected.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            channel_id = int(channel_id_str); channel = self.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel): await interaction.followup.send(f"Channel not found.", ephemeral=True); return

            # --- Updated Database Query ---
            query = """
                SELECT
                    SUM(CASE WHEN bet_won = 1 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN bet_loss = 1 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN bet_won IS NULL AND bet_loss IS NULL THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN bet_won = 1 THEN units ELSE 0 END) as units_won,
                    SUM(CASE WHEN bet_loss = 1 THEN units ELSE 0 END) as units_lost
                FROM bets WHERE user_id = %s AND guild_id = %s
            """
            result = await db_manager.fetch_one(query, (self.user.id, self.guild.id))
            # --- End Updated Query ---

            wins = 0; losses = 0; pending = 0; units_won = 0.0; units_lost = 0.0
            if result: # Check if result is not None
                 wins = int(result.get('wins', 0) or 0) # Handle None from SUM if no rows match
                 losses = int(result.get('losses', 0) or 0)
                 pending = int(result.get('pending', 0) or 0)
                 units_won = float(result.get('units_won', 0.0) or 0.0)
                 units_lost = float(result.get('units_lost', 0.0) or 0.0)

            total_units = units_won - units_lost
            image_url = self.user.display_avatar.url if self.user.display_avatar else DEFAULT_AVATAR_URL
            profile_data = await fetch_image(image_url)

            # --- Generate Plot (code largely unchanged) ---
            plt.switch_backend('Agg'); fig = plt.figure(figsize=(10, 8))
            gs = gridspec.GridSpec(2, 2, height_ratios=[1, 2], width_ratios=[1, 1], figure=fig, hspace=0.4, wspace=0.3)
            ax_profile = fig.add_subplot(gs[0, 0]); ax_text = fig.add_subplot(gs[0, 1]); ax_pie = fig.add_subplot(gs[1, :])
            # Profile image plot
            ax_profile.set_title("Profile Image", fontsize=14)
            if profile_data:
                 try: img = Image.open(io.BytesIO(profile_data)).convert("RGBA").resize((150, 150), Image.LANCZOS); img = apply_circular_mask(img); ax_profile.imshow(img)
                 except Exception as img_err: logger.error(f"Img error {self.user.id}: {img_err}"); ax_profile.text(0.5, 0.5, "Img Error", ha='center', va='center')
                 finally: ax_profile.axis('off')
            else: ax_profile.text(0.5, 0.5, "No Image", ha='center', va='center'); ax_profile.axis('off')
            # Text stats plot
            ax_text.set_title("Betting Stats", fontsize=14)
            stats_text = (f"Wins: {wins}\nLosses: {losses}\nPending: {pending}\n\nUnits Won: {units_won:.2f}\nUnits Lost: {units_lost:.2f}\nNet Units: {total_units:.2f}")
            ax_text.text(0.05, 0.95, stats_text, fontsize=12, ha='left', va='top', linespacing=1.5); ax_text.axis('off')
            # Pie chart plot
            ax_pie.set_title("Bet Outcomes (W/L/P)", fontsize=14)
            sizes = [wins, losses, pending]; labels = [f'Wins ({wins})', f'Losses ({losses})', f'Pending ({pending})']; colors = ['#4CAF50', '#F44336', '#FFC107']
            non_zero_sizes = [s for s in sizes if s > 0]; non_zero_labels = [labels[i] for i, s in enumerate(sizes) if s > 0]; non_zero_colors = [colors[i] for i, s in enumerate(sizes) if s > 0]
            if sum(non_zero_sizes) > 0: ax_pie.pie(non_zero_sizes, labels=non_zero_labels, colors=non_zero_colors, autopct='%1.1f%%', startangle=90, pctdistance=0.85); ax_pie.axis('equal')
            else: ax_pie.text(0.5, 0.5, "No Bet Data Available", ha='center', va='center', fontsize=16); ax_pie.axis('off')
            # Finalize plot
            fig.suptitle(f"{self.user.display_name}'s Betting Profile", fontsize=18, weight='bold'); fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            buf = io.BytesIO(); fig.savefig(buf, format='png', bbox_inches='tight', dpi=100); buf.seek(0); plt.close(fig)

            # --- Send Plot ---
            file = discord.File(fp=buf, filename=f'{self.user.name}_profile.png')
            try: await channel.send(file=file); await interaction.followup.send("Profile sent successfully.", ephemeral=True)
            except discord.Forbidden: logger.error(f"Cannot send file in {channel.id}."); await interaction.followup.send(f"Error: Cannot send profile to {channel.mention}.", ephemeral=True)
            except Exception as send_err: logger.error(f"Error sending profile: {send_err}"); await interaction.followup.send("Error sending profile.", ephemeral=True)
        except Exception as e: logger.error(f"Error generating profile {self.user.id}: {e}", exc_info=True); await interaction.followup.send("Internal error generating profile.", ephemeral=True)
        finally: plt.close('all')

async def profile_command_handler(interaction: Interaction, user: Optional[discord.User] = None):
    target_user = user or interaction.user
    if not interaction.guild: await interaction.response.send_message("Use in a server.", ephemeral=True); return
    view = View(timeout=60); view.add_item(ChannelSelectForProfile(target_user, interaction.guild))
    await interaction.response.send_message("Select channel for profile:", view=view, ephemeral=True)
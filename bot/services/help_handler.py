#   bot/services/help_handler.py

import discord
from discord import Interaction

async def help_command_handler(interaction: Interaction):
    embed = discord.Embed(title="Available Commands", color=discord.Color.blue())
    commands = [
        ("/add_capper", "Add a user as a capper (Admin)"),
        ("/admin", "Admin controls (e.g., reset units) (Admin)"),
        ("/bet", "Place a standard or prop bet"),
        ("/cancel_bet", "Cancel a pending bet (Admin)"),
        ("/editid", "Edit a bet’s event ID (Admin)"),
        ("/help", "Show this help message"),
        ("/leaderboard", "Show top bettors by units won"),
        ("/load_url", "Load bet data from a URL (placeholder)"),
        ("/profile", "Show a user’s betting profile"),
        ("/setid", "Set a bet’s event ID"),
        ("/show_cappers", "List all cappers"),
        ("/stats", "Show a capper’s betting stats"),
        ("/subscription", "Manage guild subscription status (Admin)"),
    ]
    for name, desc in commands:
        embed.add_field(name=name, value=desc, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)
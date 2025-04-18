#   bot/services/add_capper_handler.py

import logging
import discord
from discord import Interaction, Role # Import Role
from discord.ui import View, Select
from discord.utils import get # Import get utility

# Removed DB/fetch_image imports as they are no longer needed here

logger = logging.getLogger(__name__)

# --- CONFIGURED Capper Role ID ---
# Option 1: By Name (Case-sensitive) - Commented out as ID is preferred
# CAPPER_ROLE_NAME = "Capper"
# Option 2: By ID (More reliable if name changes)
CAPPER_ROLE_ID = 1328142704970043546 # <<< SET TO PROVIDED ID

async def check_admin_permissions(interaction: Interaction) -> bool:
    if not interaction.guild or not interaction.user: return False
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need admin permissions.", ephemeral=True)
        return False
    return True

class UserSelectForCapperRole(Select):
    def __init__(self, guild: discord.Guild, capper_role: Role):
        self.capper_role = capper_role
        options = []
        try:
             for member in guild.members:
                  if member and not member.bot and self.capper_role not in member.roles:
                       options.append(discord.SelectOption(label=member.display_name, value=str(member.id)))
        except Exception as e: logger.error(f"Error iterating members: {e}")

        if not options:
            options = [discord.SelectOption(label="No users found without Capper role", value="none")]

        super().__init__(placeholder="Select User to grant Capper role", options=options[:25], min_values=1, max_values=1)
        self.guild = guild


    async def callback(self, interaction: Interaction):
        if not await check_admin_permissions(interaction): return

        user_id_str = self.values[0]
        if user_id_str == "none":
            await interaction.response.send_message("No valid user selected.", ephemeral=True)
            return

        user_id = int(user_id_str)
        member = self.guild.get_member(user_id)

        if not member:
            await interaction.response.send_message("Could not find that user.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if self.capper_role not in member.roles:
                 await member.add_roles(self.capper_role, reason=f"Added via /add_capper by {interaction.user}")
                 await interaction.followup.send(f"Added '{self.capper_role.name}' role to {member.display_name}.", ephemeral=True)
                 logger.info(f"Added role '{self.capper_role.name}' to user {user_id} by {interaction.user.id}")
            else:
                 await interaction.followup.send(f"{member.display_name} already has the '{self.capper_role.name}' role.", ephemeral=True)

        except discord.Forbidden:
             logger.error(f"Bot lacks permissions to add role '{self.capper_role.name}' in guild {self.guild.id}")
             await interaction.followup.send("Error: Bot lacks permissions to manage roles.", ephemeral=True)
        except discord.HTTPException as e:
             logger.error(f"HTTP error adding role to user {user_id}: {e}")
             await interaction.followup.send("An error occurred while trying to add the role.", ephemeral=True)
        except Exception as e:
            logger.error(f"Unexpected error adding role to user {user_id}: {e}", exc_info=True)
            await interaction.followup.send("An unexpected error occurred.", ephemeral=True)


async def add_capper_command_handler(interaction: Interaction):
    """Handles the /add_capper command logic."""
    if not await check_admin_permissions(interaction): return
    if not interaction.guild: await interaction.response.send_message("Use in a server.", ephemeral=True); return

    # --- Find the Capper Role using the configured ID ---
    capper_role: Optional[Role] = None
    try:
         role_id_to_find = CAPPER_ROLE_ID # Use the configured ID
         capper_role = interaction.guild.get_role(role_id_to_find)
         if not capper_role:
              logger.error(f"CRITICAL: Configured Capper role ID {role_id_to_find} not found in guild {interaction.guild.id}.")
              # Fallback attempt by name if ID failed and name is defined
              # try:
              #     role_name_to_find = CAPPER_ROLE_NAME
              #     capper_role = get(interaction.guild.roles, name=role_name_to_find)
              #     if capper_role: logger.warning(f"Found capper role by name '{role_name_to_find}' after ID failed.")
              # except NameError: pass # Name not defined, stick with ID failure
              # Fallback removed for clarity, rely on ID. Add name back if needed.
    except NameError:
         logger.error("CRITICAL: CAPPER_ROLE_ID is not configured in add_capper_handler.py")
         await interaction.response.send_message("Error: Capper role ID is not configured in the bot code.", ephemeral=True)
         return
    except Exception as e:
        logger.error(f"Error finding capper role by ID: {e}")
        # Don't expose role ID potentially in error message
        await interaction.response.send_message("Error finding the Capper role in this server.", ephemeral=True)
        return

    if not capper_role:
        await interaction.response.send_message("Error: Could not find the configured Capper role ID in this server. Please check bot configuration and role existence.", ephemeral=True)
        return
    # --- End Find Role ---

    view = View(timeout=120)
    view.add_item(UserSelectForCapperRole(interaction.guild, capper_role))
    await interaction.response.send_message(f"Select a user to grant the '{capper_role.name}' role:", view=view, ephemeral=True)
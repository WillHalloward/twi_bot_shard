import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.error_handling import handle_interaction_errors


class SettingsCog(commands.Cog, name="Settings"):
    """Cog for managing server-specific settings"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Called when the cog is loaded."""
        await self._init_db()

    async def _init_db(self):
        """Initialize the database table for server settings"""
        try:
            await self.bot.db.execute(
                """
                CREATE TABLE IF NOT EXISTS server_settings (
                    guild_id BIGINT PRIMARY KEY,
                    admin_role_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            logging.info("Server settings table initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize server settings table: {e}")

    @app_commands.command(
        name="set_admin_role", description="Set the admin role for this server"
    )
    @app_commands.default_permissions(administrator=True)
    @handle_interaction_errors
    async def set_admin_role(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        """Set the admin role for the server"""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        try:
            # Check if a record exists for this guild
            existing = await self.bot.db.fetchval(
                "SELECT admin_role_id FROM server_settings WHERE guild_id = $1",
                interaction.guild.id,
            )

            if existing:
                # Update existing record
                await self.bot.db.execute(
                    """
                    UPDATE server_settings 
                    SET admin_role_id = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = $2
                    """,
                    role.id,
                    interaction.guild.id,
                )
            else:
                # Insert new record
                await self.bot.db.execute(
                    """
                    INSERT INTO server_settings (guild_id, admin_role_id)
                    VALUES ($1, $2)
                    """,
                    interaction.guild.id,
                    role.id,
                )

            await interaction.response.send_message(
                f"Admin role set to {role.mention} for this server.", ephemeral=True
            )
        except Exception as e:
            logging.error(f"Error setting admin role: {e}")
            await interaction.response.send_message(
                "An error occurred while setting the admin role.", ephemeral=True
            )

    @app_commands.command(
        name="get_admin_role", description="Get the current admin role for this server"
    )
    @handle_interaction_errors
    async def get_admin_role(self, interaction: discord.Interaction):
        """Get the current admin role for the server"""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        try:
            admin_role_id = await self.bot.db.fetchval(
                "SELECT admin_role_id FROM server_settings WHERE guild_id = $1",
                interaction.guild.id,
            )

            if admin_role_id:
                role = interaction.guild.get_role(admin_role_id)
                if role:
                    await interaction.response.send_message(
                        f"The admin role for this server is {role.mention}.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        f"The admin role (ID: {admin_role_id}) could not be found. It may have been deleted.",
                        ephemeral=True,
                    )
            else:
                await interaction.response.send_message(
                    "No admin role has been set for this server.", ephemeral=True
                )
        except Exception as e:
            logging.error(f"Error getting admin role: {e}")
            await interaction.response.send_message(
                "An error occurred while getting the admin role.", ephemeral=True
            )

    @staticmethod
    async def is_admin(bot, guild_id: int, user_id: int, user_roles=None) -> bool:
        """
        Check if a user has the admin role or is the bot owner

        Args:
            bot: The bot instance
            guild_id: The guild ID
            user_id: The user ID
            user_roles: Optional list of user role IDs (to avoid additional API calls)

        Returns:
            bool: True if the user is an admin or the bot owner, False otherwise
        """
        # Check if user is the bot owner
        if user_id == config.bot_owner_id:
            return True

        try:
            # Get the admin role ID for this guild
            admin_role_id = await bot.db.fetchval(
                "SELECT admin_role_id FROM server_settings WHERE guild_id = $1",
                guild_id,
            )

            # If no admin role is set, fall back to the configured fallback admin role ID
            if not admin_role_id:
                admin_role_id = config.fallback_admin_role_id

            # If user_roles is provided, check if admin_role_id is in the list
            if user_roles:
                return admin_role_id in user_roles

            # Otherwise, we need to get the guild and check the user's roles
            guild = bot.get_guild(guild_id)
            if not guild:
                return False

            member = guild.get_member(user_id)
            if not member:
                return False

            return any(role.id == admin_role_id for role in member.roles)

        except Exception as e:
            logging.error(f"Error checking admin status: {e}")
            # Fall back to the hardcoded check in case of error
            return False


async def setup(bot):
    await bot.add_cog(SettingsCog(bot))

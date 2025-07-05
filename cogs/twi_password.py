"""
Password management functionality for The Wandering Inn cog.

This module handles Patreon password retrieval and updates for accessing
exclusive content on The Wandering Inn website.
"""

import datetime
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
from cogs.twi_utils import ChapterLinkButton, log_command_usage, log_command_error
from utils.error_handling import handle_interaction_errors
from utils.exceptions import ValidationError, DatabaseError
from utils.permissions import admin_or_me_check_wrapper


class PasswordMixin:
    """Mixin class providing password-related commands for The Wandering Inn cog."""

    def __init__(self):
        """Initialize the password mixin."""
        self.last_run = datetime.datetime.now() - datetime.timedelta(minutes=10)

    @app_commands.command(
        name="password",
        description="Gives the password for the latest chapter for patreons or instructions for non patreons.",
    )
    @handle_interaction_errors
    async def password(self, interaction: discord.Interaction):
        """
        Provide the current Patreon password or instructions on how to get it.

        If used in an allowed channel, this command provides the current password
        for accessing Patreon-exclusive content. If used elsewhere, it provides
        instructions on how to obtain the password through various methods.

        Args:
            interaction: The interaction that triggered the command

        Raises:
            DatabaseError: If database operations fail
            ValidationError: If password data is invalid
        """
        try:
            log_command_usage(
                "PASSWORD",
                interaction.user.id,
                interaction.user.display_name,
                f"requesting password in channel {interaction.channel.id}",
            )

            if interaction.channel.id in config.password_allowed_channel_ids:
                await self._handle_password_request(interaction)
            else:
                await self._handle_password_instructions(interaction)

        except (ValidationError, DatabaseError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Password Command Failed**\nUnexpected error while processing password request: {str(e)}"
            log_command_error("PASSWORD", interaction.user.id, e)
            raise DatabaseError(message=error_msg) from e

    async def _handle_password_request(self, interaction: discord.Interaction):
        """Handle password request in allowed channels."""
        # Fetch password from database with error handling
        try:
            password = await self.bot.db.fetchrow(
                "SELECT password, link "
                "FROM password_link "
                "WHERE password IS NOT NULL "
                "ORDER BY serial_id DESC "
                "LIMIT 1"
            )
        except Exception as e:
            log_command_error(
                "PASSWORD", interaction.user.id, e, "Database query failed"
            )
            raise DatabaseError(
                message="❌ **Database Error**\nFailed to retrieve password from database"
            ) from e

        # Validate password data
        if not password:
            logging.warning(
                f"TWI PASSWORD WARNING: No password found in database for user {interaction.user.id}"
            )
            raise ValidationError(
                message="❌ **No Password Available**\nNo password is currently available. Please contact an admin."
            )

        if not password["password"] or not password["link"]:
            logging.warning(
                f"TWI PASSWORD WARNING: Invalid password data for user {interaction.user.id}"
            )
            raise ValidationError(
                message="❌ **Invalid Password Data**\nPassword data is incomplete. Please contact an admin."
            )

        # Create password embed
        embed = discord.Embed(
            title="🔐 Patreon Password",
            description=f"**Password:** `{password['password']}`",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(),
        )

        embed.add_field(
            name="📖 Chapter Link",
            value=f"[Click here to read the chapter]({password['link']})",
            inline=False,
        )

        embed.add_field(
            name="ℹ️ Important Notes",
            value="• This password is for Patreon supporters only\n"
            "• Please don't share this password publicly\n"
            "• The password changes with each new chapter",
            inline=False,
        )

        embed.set_footer(text="Thank you for supporting The Wandering Inn!")

        # Create view with chapter link button
        view = discord.ui.View()
        view.add_item(ChapterLinkButton(password["link"]))

        # Check if this is a public channel and warn about rate limiting
        if interaction.channel.type != discord.ChannelType.private:
            time_since_last = datetime.datetime.now() - self.last_run
            if time_since_last < datetime.timedelta(minutes=5):
                embed.add_field(
                    name="⚠️ Rate Limit Notice",
                    value="This command was recently used publicly. Consider using DMs for frequent requests.",
                    inline=False,
                )

            self.last_run = datetime.datetime.now()

        await interaction.response.send_message(embed=embed, view=view)
        logging.info(
            f"TWI PASSWORD: Successfully provided password to user {interaction.user.id}"
        )

    async def _handle_password_instructions(self, interaction: discord.Interaction):
        """Handle password instructions for non-allowed channels."""
        embed = discord.Embed(
            title="🔐 How to Get the Patreon Password",
            description="The password for the latest chapter is available through several methods:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(),
        )

        embed.add_field(
            name="💬 Discord Methods",
            value="• Use this command in an allowed bot channel\n"
            "• Send me a direct message with `/password`\n"
            "• Check the pinned messages in Patreon channels",
            inline=False,
        )

        embed.add_field(
            name="🌐 Other Methods",
            value="• Check the Patreon post comments\n"
            "• Visit The Wandering Inn Discord server\n"
            "• Ask other Patreon supporters",
            inline=False,
        )

        embed.add_field(
            name="💝 Support The Wandering Inn",
            value="Consider becoming a Patreon supporter to get early access to chapters and support the author!",
            inline=False,
        )

        embed.set_footer(text="Thank you for reading The Wandering Inn!")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logging.info(
            f"TWI PASSWORD: Provided instructions to user {interaction.user.id} in non-allowed channel"
        )

    @app_commands.command(
        name="update_password",
        description="Updates the password for the latest chapter (Admin only).",
    )
    @app_commands.check(admin_or_me_check_wrapper)
    @handle_interaction_errors
    async def update_password(
        self, interaction: discord.Interaction, password: str, link: str
    ):
        """
        Update the Patreon password and chapter link (Admin only).

        This command allows administrators to update the password and link
        for the latest Patreon chapter. It validates the inputs and stores
        them in the database for use by the password command.

        Args:
            interaction: The interaction that triggered the command
            password: The new password for the chapter
            link: The URL link to the chapter

        Raises:
            ValidationError: If password or link parameters are invalid
            DatabaseError: If database operations fail
        """
        try:
            log_command_usage(
                "UPDATE_PASSWORD",
                interaction.user.id,
                interaction.user.display_name,
                f"updating password: {password[:10]}... link: {link[:50]}...",
            )

            # Input validation
            if not password or not password.strip():
                raise ValidationError(
                    message="❌ **Invalid Password**\nPassword cannot be empty."
                )

            if not link or not link.strip():
                raise ValidationError(
                    message="❌ **Invalid Link**\nLink cannot be empty."
                )

            password = password.strip()
            link = link.strip()

            # Validate link format
            if not (link.startswith("http://") or link.startswith("https://")):
                raise ValidationError(
                    message="❌ **Invalid Link Format**\nLink must start with http:// or https://"
                )

            if len(password) > 100:
                raise ValidationError(
                    message="❌ **Password Too Long**\nPassword must be 100 characters or less."
                )

            if len(link) > 500:
                raise ValidationError(
                    message="❌ **Link Too Long**\nLink must be 500 characters or less."
                )

            # Defer response since database operations might take time
            await interaction.response.defer()

            # Update password in database
            try:
                await self.bot.db.execute(
                    "INSERT INTO password_link (password, link) VALUES ($1, $2)",
                    password,
                    link,
                )
            except Exception as e:
                log_command_error(
                    "UPDATE_PASSWORD", interaction.user.id, e, "Database update failed"
                )
                raise DatabaseError(
                    message="❌ **Database Error**\nFailed to update password in database"
                ) from e

            # Create success embed
            embed = discord.Embed(
                title="✅ Password Updated Successfully",
                description="The Patreon password and chapter link have been updated.",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(),
            )

            embed.add_field(
                name="🔐 New Password",
                value=f"`{password}`",
                inline=False,
            )

            embed.add_field(
                name="📖 Chapter Link",
                value=f"[Click here to view]({link})",
                inline=False,
            )

            embed.add_field(
                name="ℹ️ Next Steps",
                value="• The new password is now available via `/password`\n"
                "• Consider announcing the update in relevant channels\n"
                "• Verify the link works correctly",
                inline=False,
            )

            embed.set_footer(text=f"Updated by {interaction.user.display_name}")

            # Create view with chapter link button
            view = discord.ui.View()
            view.add_item(ChapterLinkButton(link))

            await interaction.followup.send(embed=embed, view=view)
            logging.info(
                f"TWI UPDATE_PASSWORD: Successfully updated password by user {interaction.user.id}"
            )

        except (ValidationError, DatabaseError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Update Failed**\nUnexpected error while updating password: {str(e)}"
            log_command_error("UPDATE_PASSWORD", interaction.user.id, e)
            raise DatabaseError(message=error_msg) from e

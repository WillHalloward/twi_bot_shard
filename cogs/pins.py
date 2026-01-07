"""Pin management cog for the Twi Bot Shard.

This module provides commands for pinning messages in designated channels.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.command_groups import admin
from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    DatabaseError,
    ExternalServiceError,
    PermissionError,
    ValidationError,
)


class Pins(commands.Cog, name="Pins"):
    """Pin management commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.pin_cache = None
        self.pin_context = app_commands.ContextMenu(
            name="Pin",
            callback=self.pin_callback,
        )
        self.bot.tree.add_command(self.pin_context)

    async def cog_load(self) -> None:
        """Load pin cache on cog load."""
        try:
            self.pin_cache = await self.bot.db.fetch(
                "SELECT id FROM channels WHERE allow_pins = TRUE"
            )
        except Exception as e:
            logging.error(f"PINS: Failed to load pin cache: {e}")
            self.pin_cache = []

    async def cog_unload(self) -> None:
        """Clean up context menu on unload."""
        self.bot.tree.remove_command(self.pin_context.name, type=self.pin_context.type)

    @handle_interaction_errors
    async def pin_callback(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """Context menu command to pin a message in allowed channels."""
        try:
            if not message:
                raise ValidationError(message="Message parameter is required")

            if not message.channel:
                raise ValidationError(message="Message channel could not be determined")

            logging.info(
                f"PINS: User {interaction.user.id} attempting to pin message {message.id}"
            )

            if message.channel.id not in [x["id"] for x in self.pin_cache]:
                raise PermissionError(
                    message="You can't pin messages in this channel. An admin needs to enable pins for this channel first."
                )

            if message.pinned:
                raise ValidationError(message="That message is already pinned")

            try:
                await message.pin(
                    reason=f"Pinned by {interaction.user} via context menu"
                )

                embed = discord.Embed(
                    title="📌 Message Pinned Successfully",
                    description=f"Message has been pinned in {message.channel.mention}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow(),
                )

                message_preview = (
                    message.content[:100] + "..."
                    if len(message.content) > 100
                    else message.content
                )
                if message_preview:
                    embed.add_field(
                        name="💬 Message Preview",
                        value=f"*{message_preview}*",
                        inline=False,
                    )

                embed.add_field(
                    name="👤 Original Author", value=message.author.mention, inline=True
                )

                embed.add_field(
                    name="🔗 Jump to Message",
                    value=f"[Click here]({message.jump_url})",
                    inline=True,
                )

                embed.set_footer(text=f"Pinned by {interaction.user.display_name}")

                logging.info(
                    f"PINS: Successfully pinned message {message.id} for user {interaction.user.id}"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            except discord.Forbidden as e:
                logging.error(f"PINS ERROR: Permission denied: {e}")
                raise PermissionError(
                    message="I don't have permission to pin messages in this channel"
                ) from e
            except discord.NotFound as e:
                logging.error(f"PINS ERROR: Message not found: {e}")
                raise ValidationError(
                    message="Could not find that message. It may have been deleted."
                ) from e
            except discord.HTTPException as e:
                if "pins" in str(e).lower():
                    error_msg = (
                        "This channel has reached the maximum number of pins (50)."
                    )
                else:
                    error_msg = f"Failed to pin the message: {e}"
                logging.error(f"PINS ERROR: Discord HTTP error: {e}")
                raise ExternalServiceError(message=error_msg) from e

        except (ValidationError, PermissionError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(f"PINS ERROR: {e}")
            raise ExternalServiceError(
                message=f"Unexpected error while pinning message: {e}"
            ) from e

    @admin.command(
        name="set_pin_channels",
        description="Set which channels the pin command should work in",
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @handle_interaction_errors
    async def set_pin_channels(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        """Toggle whether the pin command can be used in a specific channel."""
        try:
            if not channel:
                raise ValidationError(message="Channel parameter is required")

            if not interaction.guild:
                raise ValidationError(
                    message="This command can only be used in a server"
                )

            if channel.guild.id != interaction.guild.id:
                raise ValidationError(
                    message="You can only configure channels from this server"
                )

            logging.info(
                f"PINS: User {interaction.user.id} toggling pin permissions for channel {channel.id}"
            )

            is_currently_allowed = channel.id in [x["id"] for x in self.pin_cache]
            action = "remove" if is_currently_allowed else "add"

            try:
                if is_currently_allowed:
                    await self.bot.db.execute(
                        "UPDATE channels SET allow_pins = FALSE WHERE id = $1",
                        channel.id,
                    )

                    embed = discord.Embed(
                        title="🚫 Pin Permissions Removed",
                        description=f"Removed pin permissions from {channel.mention}",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow(),
                    )

                    embed.add_field(
                        name="📝 Action",
                        value="Users can no longer pin messages in this channel",
                        inline=False,
                    )

                else:
                    await self.bot.db.execute(
                        "UPDATE channels SET allow_pins = TRUE WHERE id = $1",
                        channel.id,
                    )

                    embed = discord.Embed(
                        title="✅ Pin Permissions Added",
                        description=f"Added pin permissions to {channel.mention}",
                        color=discord.Color.green(),
                        timestamp=discord.utils.utcnow(),
                    )

                    embed.add_field(
                        name="📝 Action",
                        value="Users can now pin messages in this channel using the context menu",
                        inline=False,
                    )

                try:
                    self.pin_cache = await self.bot.db.fetch(
                        "SELECT id FROM channels WHERE allow_pins = TRUE"
                    )
                except Exception as e:
                    logging.warning(f"PINS: Failed to update pin cache: {e}")

                embed.add_field(
                    name="📍 Channel",
                    value=f"{channel.mention}\n**ID:** {channel.id}",
                    inline=True,
                )

                embed.add_field(
                    name="👤 Modified By", value=interaction.user.mention, inline=True
                )

                total_allowed = len(self.pin_cache)
                embed.add_field(
                    name="📊 Total Allowed Channels",
                    value=f"{total_allowed} channel{'s' if total_allowed != 1 else ''}",
                    inline=True,
                )

                embed.set_footer(text="Pin permissions updated successfully")

                logging.info(
                    f"PINS: Successfully {action}ed pin permissions for channel {channel.id}"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as db_error:
                logging.error(f"PINS ERROR: Database error: {db_error}")
                raise DatabaseError(
                    message=f"Failed to update pin permissions: {db_error}"
                ) from db_error

        except (ValidationError, PermissionError, DatabaseError):
            raise
        except Exception as e:
            logging.error(f"PINS ERROR: {e}")
            raise DatabaseError(
                message=f"Unexpected error while configuring pin permissions: {e}"
            ) from e


async def setup(bot: commands.Bot) -> None:
    """Set up the Pins cog."""
    await bot.add_cog(Pins(bot))

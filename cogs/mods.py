import datetime
import logging
import re

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Cog

import config
from utils.error_handling import handle_interaction_errors, log_error
from utils.exceptions import (
    DiscordError,
    ExternalServiceError,
    ResourceNotFoundError,
    ValidationError,
)
from utils.webhook_manager import WebhookManager


class ModCogs(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.webhook_manager = WebhookManager(bot.http_client)

    @app_commands.command(
        name="reset", description="Resets the cooldown of a command for a user"
    )
    @app_commands.default_permissions(ban_members=True)
    @handle_interaction_errors
    async def reset(self, interaction: discord.Interaction, command: str) -> None:
        """Reset the cooldown of a specific command for the user.

        Args:
            interaction: The Discord interaction object
            command: The name of the command to reset cooldown for

        Raises:
            ValidationError: If the command name is invalid
            ResourceNotFoundError: If the command doesn't exist
        """
        # Validate command name
        if not command or len(command.strip()) == 0:
            raise ValidationError(message="Command name cannot be empty")

        command = command.strip().lower()

        # Validate command name format (basic alphanumeric and underscore)
        if not re.match(r"^[a-zA-Z0-9_]+$", command):
            raise ValidationError(
                message="Command name can only contain letters, numbers, and underscores"
            )

        # Get the command object
        cmd = self.bot.get_command(command)
        if cmd is None:
            # Also check app commands
            app_cmd = None
            for app_command in self.bot.tree.get_commands():
                if app_command.name == command:
                    app_cmd = app_command
                    break

            if app_cmd is None:
                raise ResourceNotFoundError(
                    resource_type="command",
                    resource_id=command,
                    message=f"Command **{command}** not found. Please check the command name and try again.",
                )

            # App commands don't have traditional cooldowns that can be reset this way
            raise ValidationError(
                message=f"Command **{command}** is an application command and doesn't support cooldown reset through this method"
            )

        # Check if the command has cooldowns
        if not hasattr(cmd, "_buckets") or cmd._buckets is None:
            raise ValidationError(
                message=f"Command **{command}** does not have any cooldowns to reset"
            )

        # Reset the cooldown
        try:
            cmd.reset_cooldown(interaction)
            await interaction.response.send_message(
                f"✅ Successfully reset the cooldown for command **{command}** for {interaction.user.mention}"
            )
        except Exception as e:
            raise ValidationError(
                message=f"Failed to reset cooldown for command **{command}**: {str(e)}"
            )

    @app_commands.command(
        name="state", description="Post an official moderator message"
    )
    @app_commands.default_permissions(ban_members=True)
    @handle_interaction_errors
    async def state(self, interaction: discord.Interaction, message: str) -> None:
        """Post an official moderator message with proper formatting and attribution.

        Args:
            interaction: The Discord interaction object
            message: The message content to post

        Raises:
            ValidationError: If the message content is invalid
        """
        # Validate message content
        if not message or len(message.strip()) == 0:
            raise ValidationError(message="Message content cannot be empty")

        message = message.strip()

        # Validate message length (Discord embed description limit is 4096 characters)
        if len(message) > 4000:  # Leave some room for formatting
            raise ValidationError(
                message="Message content must be 4000 characters or less"
            )

        # Basic content sanitization - prevent @everyone and @here mentions
        if "@everyone" in message.lower() or "@here" in message.lower():
            raise ValidationError(
                message="Moderator messages cannot contain @everyone or @here mentions"
            )

        # Create the embed
        try:
            embed = discord.Embed(
                title="🛡️ **MODERATOR MESSAGE**",
                color=discord.Color.red(),
                description=message,
                timestamp=datetime.datetime.utcnow(),
            )

            # Add moderator attribution
            embed.set_footer(
                text=f"Posted by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            # Add a field to make it clear this is official
            embed.add_field(
                name="📋 Official Notice",
                value="This message is from the moderation team. Please read carefully.",
                inline=False,
            )

            await interaction.response.send_message(embed=embed)

            # Log the moderator action
            logging.info(
                f"Moderator message posted by {interaction.user.name} ({interaction.user.id}) in {interaction.channel.name if hasattr(interaction, 'channel') else 'unknown channel'}"
            )

        except discord.HTTPException as e:
            raise ValidationError(message=f"Failed to post moderator message: {str(e)}")
        except Exception as e:
            raise ValidationError(
                message=f"Unexpected error posting moderator message: {str(e)}"
            )

    @Cog.listener("on_message")
    async def log_attachment(self, message) -> None:
        if (
            message.attachments
            and not message.author.bot
            and not isinstance(message.channel, discord.channel.DMChannel)
        ):
            for attachment in message.attachments:
                try:
                    async with self.webhook_manager.get_webhook(
                        config.webhook
                    ) as webhook:
                        embed = discord.Embed(
                            title="New attachment",
                            url=message.jump_url,
                            description=f"content: {message.content}",
                        )
                        file = await attachment.to_file(spoiler=attachment.is_spoiler())
                        embed.set_image(url=f"attachment://{attachment.filename}")
                        embed.add_field(
                            name="User", value=message.author.mention, inline=True
                        )
                        embed.add_field(
                            name="Channel", value=message.channel.mention, inline=True
                        )
                        if message.author.avatar is not None:
                            embed.set_thumbnail(url=message.author.display_avatar.url)

                        await webhook.send(
                            file=file,
                            embed=embed,
                            allowed_mentions=discord.AllowedMentions(
                                everyone=False, roles=False, users=False
                            ),
                        )

                except Exception as e:
                    # Use standardized error logging with context
                    error = ExternalServiceError(f"Failed to log attachment: {str(e)}")
                    log_error(
                        error=error,
                        command_name="log_attachment",
                        user_id=message.author.id,
                        log_level=logging.ERROR,
                        additional_context=f"Attachment: {attachment.filename}, Channel: {message.channel.id}",
                        guild_id=message.guild.id if message.guild else None,
                        channel_id=message.channel.id,
                    )

    @Cog.listener("on_message")
    async def dm_watch(self, message) -> None:
        if (
            isinstance(message.channel, discord.channel.DMChannel)
            and not message.author.bot
        ):
            if message.attachments:
                for attachment in message.attachments:
                    try:
                        async with self.webhook_manager.get_webhook(
                            config.webhook_testing_log
                        ) as webhook:
                            embed = discord.Embed(
                                title="New attachment",
                                description=f"content: {message.content}",
                            )
                            file = await attachment.to_file(
                                spoiler=attachment.is_spoiler()
                            )
                            embed.set_image(url=f"attachment://{attachment.filename}")
                            embed.add_field(
                                name="User", value=message.author.mention, inline=True
                            )
                            embed.add_field(
                                name="Username", value=message.author.name, inline=True
                            )
                            await webhook.send(file=file, embed=embed)
                    except Exception as e:
                        error = ExternalServiceError(
                            f"Failed to log DM attachment: {str(e)}"
                        )
                        log_error(
                            error=error,
                            command_name="dm_watch",
                            user_id=message.author.id,
                            log_level=logging.ERROR,
                            additional_context=f"Attachment: {attachment.filename}, DM channel",
                        )
            else:
                try:
                    async with self.webhook_manager.get_webhook(
                        config.webhook_testing_log
                    ) as webhook:
                        embed = discord.Embed(
                            title="New message",
                            description=f"content: {message.content}",
                        )
                        embed.add_field(
                            name="sender", value=message.author.mention, inline=True
                        )
                        embed.add_field(
                            name="Username", value=message.author.name, inline=True
                        )
                        if message.channel.recipient:
                            embed.add_field(
                                name="Recipient",
                                value=message.channel.recipient.mention,
                                inline=True,
                            )
                        await webhook.send(embed=embed)
                except Exception as e:
                    error = ExternalServiceError(f"Failed to log DM message: {str(e)}")
                    log_error(
                        error=error,
                        command_name="dm_watch",
                        user_id=message.author.id,
                        log_level=logging.ERROR,
                        additional_context="DM message without attachments",
                    )

    @Cog.listener("on_message")
    async def find_links(self, message: discord.Message) -> None:
        if (
            not isinstance(message.channel, discord.channel.DMChannel)
            and not message.author.bot
            and message.guild.id == 346842016480755724
        ):
            if re.search(
                "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                message.content,
            ):
                try:
                    async with self.webhook_manager.get_webhook(
                        config.webhook
                    ) as webhook:
                        await webhook.send(
                            f"Link detected: {message.content[0:1600]}\n"
                            f"User: {message.author.name} {message.author.id}\n"
                            f"Channel: {message.channel.mention}\n"
                            f"Jump Url: {message.jump_url}",
                            allowed_mentions=discord.AllowedMentions(
                                everyone=False, roles=False, users=False
                            ),
                        )
                except Exception as e:
                    # Use standardized error logging with context
                    error = ExternalServiceError(
                        f"Failed to log link detection: {str(e)}"
                    )
                    log_error(
                        error=error,
                        command_name="find_links",
                        user_id=message.author.id,
                        log_level=logging.ERROR,
                        additional_context=f"Link in message: {message.id}, Guild: {message.guild.id}",
                        guild_id=message.guild.id,
                        channel_id=message.channel.id,
                    )

    @Cog.listener("on_member_join")
    async def filter_new_users(self, member) -> None:
        try:
            if member.created_at.replace(
                tzinfo=None
            ) < datetime.datetime.now() - datetime.timedelta(hours=72):
                verified = member.guild.get_role(945388135355924571)
                await member.add_roles(verified)
        except Exception as e:
            # Use standardized error logging with context
            error = DiscordError(f"Failed to filter new user: {str(e)}")
            log_error(
                error=error,
                command_name="filter_new_users",
                user_id=member.id,
                log_level=logging.ERROR,
                additional_context=f"Member: {member.id}, Guild: {member.guild.id}",
                guild_id=member.guild.id,
            )


async def setup(bot) -> None:
    await bot.add_cog(ModCogs(bot))

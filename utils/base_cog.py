"""
Base cog class for Twi Bot Shard.

This module provides a base class for cogs with common functionality,
reducing code duplication across cogs.
"""

import logging
from typing import Any, Optional, Type, TypeVar

import discord
from discord.ext import commands

from utils.repository_factory import RepositoryFactory

T = TypeVar("T")


class BaseCog(commands.Cog):
    """Base class for cogs with common functionality.

    This class provides common initialization and utility methods for cogs,
    reducing code duplication across the codebase.

    Attributes:
        bot: The bot instance.
        logger: Logger for this cog.
        repo_factory: Repository factory for database access.
    """

    def __init__(self, bot: commands.Bot, name: Optional[str] = None):
        """Initialize the cog.

        Args:
            bot: The bot instance.
            name: Optional name for the cog. If not provided, the class name will be used.
        """
        self.bot = bot
        self.logger = logging.getLogger(name or self.__class__.__name__)
        self.repo_factory: RepositoryFactory = bot.repo_factory

    def get_repository(self, model_class: Type[T]) -> Any:
        """Get a repository for the given model class.

        Args:
            model_class: The model class to get a repository for.

        Returns:
            A repository instance for the given model class.
        """
        return self.repo_factory.get_repository(model_class)

    async def log_command_usage(
        self, ctx_or_interaction: Any, command_name: str
    ) -> None:
        """Log command usage.

        Args:
            ctx_or_interaction: The command context or interaction.
            command_name: The name of the command being used.
        """
        # Determine if we're dealing with a Context or an Interaction
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

        # Get the user and guild
        user = (
            ctx_or_interaction.user
            if is_interaction
            else ctx_or_interaction.message.author
        )
        guild = ctx_or_interaction.guild

        self.logger.info(
            f"Command '{command_name}' used by {user.name}#{user.discriminator} ({user.id}) "
            f"in guild {guild.name if guild else 'DM'} ({guild.id if guild else 'N/A'})"
        )

    async def handle_error(
        self, ctx_or_interaction: Any, error: Exception, command_name: str
    ) -> None:
        """Handle command errors.

        Args:
            ctx_or_interaction: The command context or interaction.
            error: The error that occurred.
            command_name: The name of the command that caused the error.
        """
        # Determine if we're dealing with a Context or an Interaction
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

        # Log the error
        self.logger.error(f"Error in command '{command_name}': {error}", exc_info=error)

        # Send an error message to the user
        error_message = f"An error occurred while executing the command: {error}"

        if is_interaction:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(error_message, ephemeral=True)
            else:
                await ctx_or_interaction.response.send_message(
                    error_message, ephemeral=True
                )
        else:
            await ctx_or_interaction.send(error_message)

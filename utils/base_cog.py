"""Base cog class for Twi Bot Shard.

This module provides a base class for cogs with common functionality,
reducing code duplication across cogs.
"""

from typing import Any, TypeVar

import discord
import structlog
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

    def __init__(self, bot: commands.Bot, name: str | None = None) -> None:
        """Initialize the cog.

        Args:
            bot: The bot instance.
            name: Optional name for the cog. If not provided, the class name will be used.
        """
        self.bot = bot
        # Use structured logging with hierarchical naming
        cog_name = name or self.__class__.__name__.lower().replace("cog", "").replace(
            "s", ""
        )
        self.logger = structlog.get_logger(f"cogs.{cog_name}")
        self.repo_factory: RepositoryFactory = bot.repo_factory

    def get_repository(self, model_class: type[T]) -> Any:
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
        """Log command usage with structured logging.

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
            "command_used",
            command=command_name,
            user_id=user.id,
            user_name=f"{user.name}#{user.discriminator}",
            guild_id=guild.id if guild else None,
            guild_name=guild.name if guild else "DM",
            interaction_type="slash" if is_interaction else "prefix",
        )

    async def handle_error(
        self, ctx_or_interaction: Any, error: Exception, command_name: str
    ) -> None:
        """Handle command errors with structured logging.

        Args:
            ctx_or_interaction: The command context or interaction.
            error: The error that occurred.
            command_name: The name of the command that caused the error.
        """
        # Determine if we're dealing with a Context or an Interaction
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

        # Get the user and guild for context
        user = (
            ctx_or_interaction.user
            if is_interaction
            else ctx_or_interaction.message.author
        )
        guild = ctx_or_interaction.guild

        # Log the error with structured context
        self.logger.error(
            "command_error",
            command=command_name,
            error_type=error.__class__.__name__,
            error_message=str(error),
            user_id=user.id,
            user_name=f"{user.name}#{user.discriminator}",
            guild_id=guild.id if guild else None,
            guild_name=guild.name if guild else "DM",
            interaction_type="slash" if is_interaction else "prefix",
            exc_info=error,
        )

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

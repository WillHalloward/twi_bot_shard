"""Base cog class for Twi Bot Shard.

This module provides a base class for cogs with common functionality,
reducing code duplication across cogs.
"""

from typing import Any

import discord
import structlog
from discord.ext import commands


class BaseCog(commands.Cog):
    """Base class for cogs with common functionality.

    This class provides common initialization and utility methods for cogs,
    reducing code duplication across the codebase.

    Attributes:
        bot: The bot instance.
        logger: Logger for this cog.
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

    async def log_command_usage(
        self, ctx_or_interaction: Any, command_name: str
    ) -> None:
        """Log command usage with structured logging.

        Args:
            ctx_or_interaction: The command context or interaction.
            command_name: The name of the command being used.
        """
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

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
            user_name=user.name,
            guild_id=guild.id if guild else None,
            guild_name=guild.name if guild else "DM",
            interaction_type="slash" if is_interaction else "prefix",
        )

"""Base cog class for Twi Bot Shard.

This module provides a base class for cogs with common functionality,
reducing code duplication across cogs.
"""

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

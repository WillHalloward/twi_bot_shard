"""Refactored Stats Cog for Discord Bot.

This module provides comprehensive statistics tracking and reporting functionality
for Discord servers. It has been refactored from a monolithic 2639-line file into
smaller, focused modules for better maintainability.

The cog tracks:
- Message statistics and history
- User activity and membership changes
- Reaction data
- Channel and server information
- Voice activity
- And much more...

Architecture:
- StatsCommandsMixin: Owner commands for data management
- StatsListenersMixin: Real-time event listeners
- StatsTasksMixin: Background tasks for reporting
- StatsQueriesMixin: User-facing query commands
- StatsUtils: Utility functions for data processing
"""

from typing import TYPE_CHECKING

import structlog
from discord.ext import commands

import config

from .stats_commands import StatsCommandsMixin
from .stats_listeners import StatsListenersMixin
from .stats_queries import StatsQueriesMixin
from .stats_tasks import StatsTasksMixin

if TYPE_CHECKING:
    from discord.ext.commands import Bot


class StatsCogs(
    StatsCommandsMixin,
    StatsListenersMixin,
    StatsTasksMixin,
    StatsQueriesMixin,
    commands.Cog,
    name="stats",
):
    """Comprehensive statistics tracking cog for Discord servers.

    This cog provides extensive functionality for tracking and analyzing
    Discord server activity, including messages, users, reactions, and more.

    The cog has been refactored from a single large file into multiple
    focused modules to improve maintainability and code organization.

    Features:
    - Real-time message and reaction tracking
    - User activity monitoring
    - Server statistics and reporting
    - Background tasks for daily reports
    - Query commands for retrieving statistics
    - Comprehensive data management commands

    Attributes:
        bot: The Discord bot instance
        logger: Logger instance for this cog
    """

    def __init__(self, bot: "Bot") -> None:
        """Initialize the Stats cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = structlog.get_logger("cogs.stats")

        # Start the background stats loop if not in test mode
        if config.logfile != "test":
            self.stats_loop.start()
            self.logger.info("stats_loop_started")
        else:
            self.logger.info("stats_loop_disabled", reason="test_mode")

    async def cog_unload(self) -> None:
        """Cleanup when the cog is unloaded.

        Stops the background stats loop to prevent resource leaks.
        """
        if hasattr(self, "stats_loop") and self.stats_loop.is_running():
            self.stats_loop.cancel()
            self.logger.info("stats_loop_stopped")

    async def cog_load(self) -> None:
        """Setup when the cog is loaded.

        Performs any necessary initialization after the cog is added to the bot.
        """
        self.logger.info("stats_cog_loaded")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Event listener for when the bot is ready.

        Logs that the stats cog is ready and operational.
        """
        self.logger.info("stats_cog_ready")


async def setup(bot: "Bot") -> None:
    """Setup function to add the cog to the bot.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(StatsCogs(bot))

"""
The Wandering Inn cog for the Twi Bot Shard.

This module provides commands related to The Wandering Inn web serial, including
password retrieval for Patreon supporters, wiki searches, invisible text lookup,
and other TWI-specific functionality.

This cog has been refactored into smaller, focused modules for better maintainability:
- twi_utils.py: Shared utilities and helper functions
- twi_password.py: Password management functionality
- twi_search.py: Wiki and content search functionality
- twi_content.py: Invisible text and colored text functionality
"""

import logging
from discord.ext import commands

from cogs.twi_password import PasswordMixin
from cogs.twi_search import SearchMixin
from cogs.twi_content import ContentMixin


class TwiCog(
    PasswordMixin, SearchMixin, ContentMixin, commands.Cog, name="The Wandering Inn"
):
    """
    Cog providing commands related to The Wandering Inn web serial.

    This cog combines functionality from multiple mixin classes to provide
    a comprehensive set of commands for The Wandering Inn community:

    - Password management for Patreon supporters
    - Wiki search functionality
    - Content search on wanderinginn.com
    - Invisible text retrieval
    - Colored text reference guide
    - Discord/Patreon connection instructions

    The cog has been refactored from a monolithic 1171-line class into
    smaller, focused modules for better maintainability and testing.

    Attributes:
        bot: The bot instance
        invis_text_cache: Cache of invisible text chapter titles for autocomplete
        last_run: Timestamp of the last time the password command was run publicly
    """

    def __init__(self, bot):
        """
        Initialize the TwiCog and all its mixin components.

        Args:
            bot: The bot instance to which this cog is attached
        """
        # Initialize the base cog
        commands.Cog.__init__(self)

        # Initialize all mixin classes
        PasswordMixin.__init__(self)
        SearchMixin.__init__(self)
        ContentMixin.__init__(self)

        # Set the bot instance
        self.bot = bot

        # Set up logging
        self.logger = logging.getLogger("twi_cog")

    async def cog_load(self) -> None:
        """
        Load initial data when the cog is added to the bot.

        This method is called automatically when the cog is loaded.
        It initializes the invisible text cache for autocomplete functionality.
        """
        try:
            # Load the invisible text cache for autocomplete
            await self.load_invis_text_cache()
            self.logger.info("TWI COG: Successfully loaded invisible text cache")
        except Exception as e:
            self.logger.error(f"TWI COG: Failed to load invisible text cache: {e}")
            # Don't fail cog loading if cache loading fails
            self.invis_text_cache = []


async def setup(bot):
    """
    Set up the TwiCog.

    This function is called automatically by the bot when loading the extension.

    Args:
        bot: The bot instance to attach the cog to
    """
    await bot.add_cog(TwiCog(bot))

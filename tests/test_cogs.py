"""
Test script for loading all cogs.

This script attempts to load all cogs and reports any errors that occur.
It's useful for testing after making updates to ensure all changes work.
"""

import asyncio
import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import discord components
import discord
from discord.ext import commands

# Import config (but don't use the token)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test_cogs")


# Define mock classes for testing
class MockScalars:
    """Mock for SQLAlchemy's Result.scalars() method."""

    def __init__(self, items=None) -> None:
        self.items = items or []

    def all(self):
        """Return all items."""
        return self.items

    def first(self):
        """Return the first item or None."""
        return self.items[0] if self.items else None


class MockResult:
    """Mock for SQLAlchemy's Result object."""

    def __init__(self, items=None) -> None:
        self.items = items or []

    def scalars(self):
        """Return a MockScalars object."""
        return MockScalars(self.items)

    def all(self):
        """Return all items."""
        return self.items

    def first(self):
        """Return the first item or None."""
        return self.items[0] if self.items else None


class MockDatabase:
    """Mock Database class for testing."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("mock_database")
        self.pool = None

    async def execute(self, query, *args, **kwargs) -> None:
        """Mock execute method."""
        return None

    async def fetch(self, query, *args, **kwargs):
        """Mock fetch method."""
        return []

    async def fetchrow(self, query, *args, **kwargs) -> None:
        """Mock fetchrow method."""
        return None

    async def fetchval(self, query, *args, **kwargs) -> None:
        """Mock fetchval method."""
        return None

    async def execute_script(self, script_path, **kwargs) -> None:
        """Mock execute_script method."""
        return None

    async def execute_many(self, query, data, **kwargs) -> None:
        """Mock execute_many method."""
        return None

    async def prepare_statement(self, name, query):
        """Mock prepare_statement method."""
        from unittest.mock import AsyncMock

        mock_stmt = AsyncMock()
        mock_stmt.execute = AsyncMock()
        return mock_stmt

    async def transaction(self):
        """Mock transaction method."""
        from unittest.mock import AsyncMock

        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock()
        mock_transaction.__aexit__ = AsyncMock()
        return mock_transaction

    async def refresh_materialized_views(self) -> None:
        """Mock refresh_materialized_views method."""
        return None


class MockAsyncSession:
    """Mock AsyncSession class for testing."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def commit(self) -> None:
        """Mock commit method."""
        pass

    async def rollback(self) -> None:
        """Mock rollback method."""
        pass

    async def close(self) -> None:
        """Mock close method."""
        pass

    async def execute(self, query, *args, **kwargs):
        """Mock execute method that returns a MockResult."""
        return MockResult([])

    async def fetch(self, query, *args, **kwargs):
        """Mock fetch method."""
        return []

    async def fetchrow(self, query, *args, **kwargs) -> None:
        """Mock fetchrow method."""
        return None

    async def fetchval(self, query, *args, **kwargs) -> None:
        """Mock fetchval method."""
        return None


# Define a test bot class that doesn't connect to Discord
class TestBot(commands.Bot):
    __test__ = False  # Tell pytest this is not a test class

    def __init__(self) -> None:
        # Initialize with minimal settings
        intents = discord.Intents.default()
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,  # Disable default help command to avoid conflicts
        )

        # Add mock database
        self.db = MockDatabase()

        # Create a session factory that returns a coroutine that returns a MockAsyncSession
        async def session_factory():
            return MockAsyncSession()

        # Add mock session maker
        self.session_maker = session_factory

        # Initialize service container
        from utils.service_container import ServiceContainer

        self.container = ServiceContainer()

        # Register common services
        self.container.register("bot", self)
        self.container.register("db", self.db)
        self.container.register("web_client", None)  # Mock web client
        self.container.register_factory("db_session", self.session_maker)

        # Add mock http_client
        from unittest.mock import AsyncMock, MagicMock

        self.http_client = MagicMock()
        # Create a proper mock session that can be used with the fetch function
        mock_response = MagicMock()
        mock_response.text = AsyncMock(return_value='{"test": "response"}')
        mock_response.status = 200

        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context_manager)

        self.http_client.get_session = AsyncMock(return_value=mock_session)
        self.http_client.get_session_with_retry = AsyncMock(return_value=mock_session)

        # Mock the latency property to return a valid float instead of NaN
        self._latency = 0.05  # 50ms latency

        # Mock guilds list for testing
        self._guilds = []

        # Add initial_extensions list (needed by sync command)
        self.initial_extensions = []

    async def get_db_session(self):
        """
        Get a new SQLAlchemy database session (mock version).

        Returns:
            MockAsyncSession: A mock async session for testing
        """
        return await self.session_maker()

    @property
    def latency(self) -> float:
        """Override latency property to return a valid float instead of NaN."""
        return self._latency

    @property
    def guilds(self):
        """Mock guilds property."""
        return self._guilds

    @guilds.setter
    def guilds(self, value) -> None:
        """Setter for guilds property."""
        self._guilds = value

    async def setup_hook(self) -> None:
        # Override to do nothing
        pass

    async def on_ready(self) -> None:
        # Override to do nothing
        pass


async def test_load_cogs() -> tuple[list[str], dict[str, Exception]]:
    """
    Test loading all cogs.

    Returns:
        Tuple containing:
        - List of successfully loaded cogs
        - Dict mapping failed cogs to their exceptions
    """
    # Get list of cogs from main.py
    all_cogs = [
        "cogs.gallery",
        "cogs.links_tags",
        "cogs.patreon_poll",
        "cogs.twi",
        "cogs.owner",
        "cogs.utility",
        "cogs.info",
        "cogs.pins",
        "cogs.quotes",
        "cogs.external_services",
        "cogs.roles",
        "cogs.mods",
        "cogs.stats",
        "cogs.creator_links",
        "cogs.report",
        "cogs.summarization",
        "cogs.settings",
        "cogs.interactive_help",
    ]

    # Create a test bot instance
    bot = TestBot()

    # Track results
    successful_cogs = []
    failed_cogs = {}

    # Try to load each cog
    for cog in all_cogs:
        try:
            logger.info(f"Attempting to load {cog}...")
            await bot.load_extension(cog)
            logger.info(f"✅ Successfully loaded {cog}")
            successful_cogs.append(cog)
        except Exception as e:
            logger.error(f"❌ Failed to load {cog}: {type(e).__name__} - {e}")
            failed_cogs[cog] = e

    # Clean up
    await bot.close()

    return successful_cogs, failed_cogs


async def main() -> bool:
    """Run the test."""
    logger.info("Testing cog loading...")

    successful_cogs, failed_cogs = await test_load_cogs()

    # Print summary
    total_cogs = len(successful_cogs) + len(failed_cogs)
    logger.info(
        f"\nSummary: {len(successful_cogs)}/{total_cogs} cogs loaded successfully"
    )

    if failed_cogs:
        logger.error("\nFailed cogs:")
        for cog, error in failed_cogs.items():
            logger.error(f"  {cog}: {type(error).__name__} - {error}")
        logger.error("\nTest failed: Some cogs could not be loaded.")
        return False
    else:
        logger.info("\nTest passed: All cogs loaded successfully!")
        return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)  # Exit with status code based on success

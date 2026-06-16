"""
Test script for loading all cogs.

This script attempts to load all cogs and reports any errors that occur.
It's useful for testing after making updates to ensure all changes work.
"""

import asyncio
import logging
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import discord components
import discord
from discord.ext import commands

from utils.cog_registry import BASE_CRITICAL_COGS, COGS

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

    def all(self) -> list:
        """Return all items."""
        return self.items

    def first(self) -> object | None:
        """Return the first item or None."""
        return self.items[0] if self.items else None


class MockResult:
    """Mock for SQLAlchemy's Result object."""

    def __init__(self, items=None) -> None:
        self.items = items or []

    def scalars(self) -> MockScalars:
        """Return a MockScalars object."""
        return MockScalars(self.items)

    def all(self) -> list:
        """Return all items."""
        return self.items

    def first(self) -> object | None:
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

    async def fetch(self, query, *args, **kwargs) -> list:
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

    async def prepare_statement(self, name, query) -> "AsyncMock":
        """Mock prepare_statement method."""
        from unittest.mock import AsyncMock

        mock_stmt = AsyncMock()
        mock_stmt.execute = AsyncMock()
        return mock_stmt

    async def transaction(self) -> "AsyncMock":
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

    async def __aenter__(self) -> "MockAsyncSession":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
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

    async def execute(self, query, *args, **kwargs) -> MockResult:
        """Mock execute method that returns a MockResult."""
        return MockResult([])

    async def fetch(self, query, *args, **kwargs) -> list:
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
        async def session_factory() -> MockAsyncSession:
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
        self._guilds: list[discord.Guild] = []

        # Add initial_extensions list (needed by sync command)
        self.initial_extensions: list[str] = []

    async def get_db_session(self) -> MockAsyncSession:
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
    def guilds(self) -> list:
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
    # The single source of truth for the cog list (also used by main.py and
    # cogs/owner.py).
    all_cogs = list(COGS)

    # Module-level app-command groups (utils/command_groups.py) accumulate
    # registrations when a cog module is executed. If another test module
    # already imported a cog at collection time (e.g. test_owner_cog.py does
    # ``from cogs.owner import OwnerCog``), ``load_extension`` re-executes the
    # module and the duplicate ``@group.command`` registration raises
    # CommandAlreadyRegistered. Clear the shared groups so every cog can
    # register its commands freshly.
    from utils.command_groups import admin, gallery_admin, mod

    for group in (admin, gallery_admin, mod):
        for registered in list(group.commands):
            group.remove_command(registered.name)

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

    # Fail the test (under pytest) if any cog failed to load. The return value
    # below is kept for the script-mode main() entry point.
    assert not failed_cogs, "cogs failed to load: " + ", ".join(
        f"{cog}: {type(e).__name__} - {e}" for cog, e in failed_cogs.items()
    )

    return successful_cogs, failed_cogs


def test_cog_registry_consistency() -> None:
    """Every registry entry must be a real, loadable extension module.

    This permanently kills the phantom-cog class of bug (e.g. the stale
    ``cogs.other``/``cogs.innktober`` entries that once lived in a hand-copied
    list in cogs/owner.py): each module path in COGS must import and expose a
    module-level ``setup`` entry point, and BASE_CRITICAL_COGS must be a
    subset of COGS.
    """
    import importlib

    assert len(COGS) == len(set(COGS)), "COGS contains duplicate entries"

    for cog in COGS:
        module = importlib.import_module(cog)
        assert hasattr(module, "setup"), (
            f"{cog} has no module-level setup() function and cannot be loaded "
            "as an extension"
        )

    missing = set(BASE_CRITICAL_COGS) - set(COGS)
    assert not missing, f"BASE_CRITICAL_COGS entries not in COGS: {sorted(missing)}"


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

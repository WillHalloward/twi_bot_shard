"""
Test fixtures for Twi Bot Shard.

This module provides reusable fixtures for setting up and tearing down
test environments, particularly for database testing.
"""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Callable
from typing import Any

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import SQLAlchemy components
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

# Import all models to ensure they're registered with Base.metadata
from models import *

# Import models
from models.base import Base
from models.tables.commands import CommandHistory
from models.tables.creator_links import CreatorLink
from models.tables.gallery import GalleryMementos

# Explicitly import all model classes to ensure they're registered
from models.tables.servers import Server

# Import test utilities


class DatabaseFixture:
    """
    Fixture for database testing.

    This class provides methods for setting up and tearing down a test database,
    as well as creating sessions for interacting with the database.
    """

    def __init__(self, database_url: str = "sqlite+aiosqlite:///:memory:") -> None:
        """
        Initialize the database fixture.

        Args:
            database_url: The URL for the test database. Defaults to an in-memory SQLite database.
        """
        self.database_url = database_url
        self.engine: AsyncEngine | None = None
        self.session_maker: Callable[..., AsyncSession] | None = None

    async def setup(self) -> None:
        """
        Set up the test database.

        This method creates the engine and session maker, and creates all tables.
        """
        # Create the engine
        self.engine = create_async_engine(self.database_url, echo=False)

        # Create the session maker
        self.session_maker = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

        # Create all tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def teardown(self) -> None:
        """
        Tear down the test database.

        This method disposes of the engine, which closes all connections.
        """
        if self.engine:
            await self.engine.dispose()

    async def create_session(self) -> AsyncSession:
        """
        Create a new session for interacting with the database.

        Returns:
            An AsyncSession object.
        """
        if not self.session_maker:
            raise RuntimeError("Database fixture not set up. Call setup() first.")

        return self.session_maker()

    async def __aenter__(self) -> "DatabaseFixture":
        """
        Enter the context manager.

        This method sets up the database and returns the fixture.
        """
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit the context manager.

        This method tears down the database.
        """
        await self.teardown()


class TestDataFixture:
    """
    Fixture for loading test data into the database.

    This class provides methods for loading test data into the database
    for testing purposes.
    """

    __test__ = False  # Tell pytest this is not a test class

    def __init__(self, db_fixture: DatabaseFixture) -> None:
        """
        Initialize the test data fixture.

        Args:
            db_fixture: The database fixture to use for loading data.
        """
        self.db_fixture = db_fixture

    async def load_gallery_mementos(self, count: int = 3) -> list[dict[str, Any]]:
        """
        Load test gallery mementos into the database.

        Args:
            count: The number of gallery mementos to create.

        Returns:
            A list of dictionaries containing the created gallery mementos.
        """

        gallery_mementos = []

        session = await self.db_fixture.create_session()
        async with session:
            for i in range(count):
                gallery = GalleryMementos(
                    channel_name=f"test-gallery-{i}",
                    channel_id=1000000 + i,
                    guild_id=2000000 + i,
                )
                session.add(gallery)
                gallery_mementos.append(
                    {
                        "channel_name": gallery.channel_name,
                        "channel_id": gallery.channel_id,
                        "guild_id": gallery.guild_id,
                    }
                )

            await session.commit()

        return gallery_mementos

    async def load_command_history(self, count: int = 3) -> list[dict[str, Any]]:
        """
        Load test command history entries into the database.

        Args:
            count: The number of command history entries to create.

        Returns:
            A list of dictionaries containing the created command history entries.
        """
        from datetime import datetime, timedelta

        command_history = []

        session = await self.db_fixture.create_session()
        async with session:
            # First create a test server if it doesn't exist
            test_server = Server(
                server_id=2000000,
                server_name="Test Server",
                creation_date=datetime.now(),
            )
            session.add(test_server)
            await (
                session.flush()
            )  # Flush to get the server_id available for foreign key

            for i in range(count):
                command = CommandHistory(
                    serial=i + 1,
                    start_date=datetime.now() - timedelta(minutes=i),
                    end_date=datetime.now()
                    - timedelta(minutes=i)
                    + timedelta(seconds=1.5 + i),
                    user_id=3000000 + i,
                    command_name=f"test_command_{i}",
                    guild_id=2000000,  # Reference the test server
                    channel_id=1000000 + i,
                    slash_command=i % 2 == 0,  # Alternate between True and False
                    args={"arg1": f"value1_{i}", "arg2": f"value2_{i}"},
                    started_successfully=True,
                    finished_successfully=True,
                    run_time=timedelta(seconds=1.5 + i),
                )
                session.add(command)
                command_history.append(
                    {
                        "serial": command.serial,
                        "user_id": command.user_id,
                        "command_name": command.command_name,
                        "guild_id": command.guild_id,
                        "channel_id": command.channel_id,
                        "slash_command": command.slash_command,
                        "args": command.args,
                    }
                )

            await session.commit()

        return command_history

    async def load_creator_links(self, count: int = 3) -> list[dict[str, Any]]:
        """
        Load test creator links into the database.

        Args:
            count: The number of creator links to create.

        Returns:
            A list of dictionaries containing the created creator links.
        """
        from datetime import datetime, timedelta

        creator_links = []

        session = await self.db_fixture.create_session()
        async with session:
            for i in range(count):
                link = CreatorLink(
                    serial_id=i + 1,
                    user_id=4000000 + i,
                    title=f"Test Link {i}",
                    link=f"https://example.com/link{i}",
                    nsfw=i % 2 == 0,  # Alternate between True and False
                    last_changed=datetime.now() - timedelta(days=i),
                    weight=i,
                    feature=i % 2 == 0,  # Alternate between True and False
                )
                session.add(link)
                creator_links.append(
                    {
                        "serial_id": link.serial_id,
                        "user_id": link.user_id,
                        "title": link.title,
                        "link": link.link,
                        "nsfw": link.nsfw,
                        "weight": link.weight,
                        "feature": link.feature,
                    }
                )

            await session.commit()

        return creator_links


async def create_db_fixture() -> AsyncGenerator[DatabaseFixture, None]:
    """
    Create a database fixture for testing.

    This function is a coroutine that yields a database fixture,
    and then tears it down when the generator is closed.

    Yields:
        A DatabaseFixture object.
    """
    fixture = DatabaseFixture()
    await fixture.setup()
    try:
        yield fixture
    finally:
        await fixture.teardown()


async def create_test_data_fixture(
    db_fixture: DatabaseFixture,
) -> AsyncGenerator[TestDataFixture, None]:
    """
    Create a test data fixture for loading test data.

    This function is a coroutine that yields a test data fixture.

    Args:
        db_fixture: The database fixture to use for loading data.

    Yields:
        A TestDataFixture object.
    """
    fixture = TestDataFixture(db_fixture)
    yield fixture


# Example usage:
async def example_usage() -> None:
    """Example of how to use the fixtures."""
    async for db_fixture in create_db_fixture():
        async for test_data in create_test_data_fixture(db_fixture):
            # Load test data
            gallery_mementos = await test_data.load_gallery_mementos()
            command_history = await test_data.load_command_history()
            creator_links = await test_data.load_creator_links()

            # Use the test data
            print(f"Created {len(gallery_mementos)} gallery mementos")
            print(f"Created {len(command_history)} command history entries")
            print(f"Created {len(creator_links)} creator links")

            # Create a session and query the data
            async with db_fixture.create_session() as session:
                from models.tables.gallery import GalleryMementos

                result = await session.execute(select(GalleryMementos))
                galleries = result.scalars().all()

                print(f"Found {len(galleries)} galleries in the database")
                for gallery in galleries:
                    print(f"  {gallery.channel_name}: {gallery.channel_id}")


if __name__ == "__main__":
    # Run the example usage
    asyncio.run(example_usage())

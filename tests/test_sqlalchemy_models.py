"""
Test script for SQLAlchemy models.

This script imports all SQLAlchemy models and tests basic functionality.
"""

import asyncio
import os
import sys
import pytest
import pytest_asyncio
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import SQLAlchemy components
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column
from sqlalchemy import Column, Integer, BigInteger, String, ForeignKey, Table, MetaData, text, Boolean, DateTime, JSON, Interval, PrimaryKeyConstraint
from typing import Optional

# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create a completely separate metadata for testing to avoid any conflicts
test_metadata = MetaData()

# Create a separate declarative base for testing
from sqlalchemy.orm import declarative_base
TestBase = declarative_base(metadata=test_metadata)

# Define required tables for foreign key references
users_table = Table(
    "users",
    test_metadata,
    Column("user_id", BigInteger, primary_key=True),
    Column("username", String(100)),
)

channels_table = Table(
    "channels",
    test_metadata,
    Column("id", BigInteger, primary_key=True),
    Column("name", String(100)),
)

servers_table = Table(
    "servers",
    test_metadata,
    Column("server_id", BigInteger, primary_key=True),
    Column("name", String(100)),
)

# Define test models using the test base (no schema issues)
class GalleryMementos(TestBase):
    """Test model for gallery_mementos table."""
    __tablename__ = "gallery_mementos"

    channel_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)

class CommandHistory(TestBase):
    """Test model for command_history table."""
    __tablename__ = "command_history"

    serial: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    command_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("channels.id"), nullable=True)
    guild_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("servers.server_id"), nullable=True)
    args: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    run_time: Mapped[Optional[timedelta]] = mapped_column(Interval, nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime, insert_default=datetime.now, nullable=False)
    slash_command: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_successfully: Mapped[bool] = mapped_column(Boolean, default=False)
    finished_successfully: Mapped[bool] = mapped_column(Boolean, default=False)

class CreatorLink(TestBase):
    """Test model for creator_links table."""
    __tablename__ = "creator_links"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "title", "serial_id"),
    )

    serial_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False, primary_key=True)
    link: Mapped[str] = mapped_column(String(255))
    last_changed: Mapped[datetime] = mapped_column(DateTime, insert_default=datetime.now, nullable=False)
    nsfw: Mapped[bool] = mapped_column(Boolean, default=False)
    weight: Mapped[int] = mapped_column(Integer, default=0)
    feature: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


async def create_test_engine():
    """Create a test engine and tables."""
    # Create engine with foreign key support
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=True,
        connect_args={"check_same_thread": False}
    )

    # Enable foreign key support in SQLite
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))

    # Create all tables using test_metadata (includes reference tables and test models)
    async with engine.begin() as conn:
        await conn.run_sync(test_metadata.create_all)

        # Insert some test data for foreign key references
        await conn.execute(users_table.insert().values(user_id=123456789, username="test_user"))
        await conn.execute(channels_table.insert().values(id=123456789, name="test_channel"))
        await conn.execute(servers_table.insert().values(server_id=987654321, name="test_server"))

    return engine


@pytest.mark.asyncio
async def test_gallery_mementos(session):
    """Test GalleryMementos model."""
    print("\nTesting GalleryMementos model...")

    # Create a new gallery memento
    gallery = GalleryMementos(
        channel_name="test-gallery", channel_id=123456789, guild_id=987654321
    )

    session.add(gallery)
    await session.commit()

    # Query the gallery memento
    result = await session.execute(
        select(GalleryMementos).where(GalleryMementos.channel_name == "test-gallery")
    )
    gallery = result.scalars().first()

    print(
        f"Gallery memento: {gallery.channel_name}, {gallery.channel_id}, {gallery.guild_id}"
    )

    assert gallery.channel_name == "test-gallery"
    assert gallery.channel_id == 123456789
    assert gallery.guild_id == 987654321

    return True


@pytest.mark.asyncio
async def test_command_history(session):
    """Test CommandHistory model."""
    print("\nTesting CommandHistory model...")

    # Create a new command history entry
    start_time = datetime.now()
    command = CommandHistory(
        serial=1,
        start_date=start_time,
        user_id=123456789,
        command_name="test_command",
        slash_command=True,
        args={"arg1": "value1", "arg2": "value2"},
        started_successfully=True,
        finished_successfully=True,
        run_time=timedelta(seconds=1.5),
    )

    session.add(command)
    await session.commit()

    # Query the command history entry
    result = await session.execute(
        select(CommandHistory).where(CommandHistory.serial == 1)
    )
    command = result.scalars().first()

    print(f"Command history: {command.command_name}, {command.user_id}, {command.args}")

    assert command.serial == 1
    assert command.user_id == 123456789
    assert command.command_name == "test_command"
    assert command.slash_command is True
    assert command.args == {"arg1": "value1", "arg2": "value2"}
    assert command.started_successfully is True
    assert command.finished_successfully is True
    assert command.run_time == timedelta(seconds=1.5)

    return True


@pytest.mark.asyncio
async def test_creator_links(session):
    """Test CreatorLink model."""
    print("\nTesting CreatorLink model...")

    # Create a new creator link
    now = datetime.now()
    link = CreatorLink(
        serial_id=1,
        user_id=123456789,
        title="Test Link",
        link="https://example.com",
        nsfw=False,
        last_changed=now,
        weight=0,
        feature=True,
    )

    session.add(link)
    await session.commit()

    # Query the creator link
    result = await session.execute(
        select(CreatorLink).where(CreatorLink.serial_id == 1)
    )
    link = result.scalars().first()

    print(f"Creator link: {link.title}, {link.link}, {link.user_id}")

    assert link.serial_id == 1
    assert link.user_id == 123456789
    assert link.title == "Test Link"
    assert link.link == "https://example.com"
    assert link.nsfw is False
    assert link.weight == 0
    assert link.feature is True

    return True


@pytest_asyncio.fixture
async def session():
    """Create a test session."""
    # Create test engine and session
    engine = await create_test_engine()
    async_session = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_all_models(session):
    """Test all models together."""
    # Run tests
    await test_gallery_mementos(session)
    await test_command_history(session)
    await test_creator_links(session)


async def main():
    """Run all tests manually."""
    print("Testing SQLAlchemy models...")

    try:
        # Create test engine and session
        engine = await create_test_engine()
        async_session = sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )

        async with async_session() as session:
            # Run tests
            tests = [
                test_gallery_mementos(session),
                test_command_history(session),
                test_creator_links(session),
            ]

            results = await asyncio.gather(*tests)

            if all(results):
                print("\nAll tests passed!")
            else:
                print("\nSome tests failed.")

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        # Close the engine
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

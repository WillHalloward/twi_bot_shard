"""
Test script for SQLAlchemy models.

This script imports all SQLAlchemy models and tests basic functionality.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import SQLAlchemy components
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

# Import models
from models.base import Base
from models.tables.gallery import GalleryMementos
from models.tables.commands import CommandHistory
from models.tables.messages import Message
from models.tables.reactions import Reaction
from models.tables.join_leave import JoinLeave
from models.tables.creator_links import CreatorLink

# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

async def create_test_engine():
    """Create a test engine and tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    return engine

async def test_gallery_mementos(session):
    """Test GalleryMementos model."""
    print("\nTesting GalleryMementos model...")
    
    # Create a new gallery memento
    gallery = GalleryMementos(
        channel_name="test-gallery",
        channel_id=123456789,
        guild_id=987654321
    )
    
    session.add(gallery)
    await session.commit()
    
    # Query the gallery memento
    result = await session.execute(select(GalleryMementos).where(GalleryMementos.channel_name == "test-gallery"))
    gallery = result.scalars().first()
    
    print(f"Gallery memento: {gallery.channel_name}, {gallery.channel_id}, {gallery.guild_id}")
    
    return True

async def test_command_history(session):
    """Test CommandHistory model."""
    print("\nTesting CommandHistory model...")
    
    # Create a new command history entry
    command = CommandHistory(
        serial=1,
        start_date=datetime.now(),
        user_id=123456789,
        command_name="test_command",
        slash_command=True,
        args={"arg1": "value1", "arg2": "value2"},
        started_successfully=True,
        finished_successfully=True,
        run_time=timedelta(seconds=1.5)
    )
    
    session.add(command)
    await session.commit()
    
    # Query the command history entry
    result = await session.execute(select(CommandHistory).where(CommandHistory.serial == 1))
    command = result.scalars().first()
    
    print(f"Command history: {command.command_name}, {command.user_id}, {command.args}")
    
    return True

async def test_creator_links(session):
    """Test CreatorLink model."""
    print("\nTesting CreatorLink model...")
    
    # Create a new creator link
    link = CreatorLink(
        serial_id=1,
        user_id=123456789,
        title="Test Link",
        link="https://example.com",
        nsfw=False,
        last_changed=datetime.now(),
        weight=0,
        feature=True
    )
    
    session.add(link)
    await session.commit()
    
    # Query the creator link
    result = await session.execute(select(CreatorLink).where(CreatorLink.serial_id == 1))
    link = result.scalars().first()
    
    print(f"Creator link: {link.title}, {link.link}, {link.user_id}")
    
    return True

async def main():
    """Run all tests."""
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
                test_creator_links(session)
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
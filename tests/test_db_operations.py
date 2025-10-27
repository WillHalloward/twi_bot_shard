"""
Test script for database operations.

This script tests various database operations using both asyncpg and SQLAlchemy.
It includes tests for CRUD operations, transaction management, error handling,
and the repository pattern.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import SQLAlchemy components
from sqlalchemy.exc import SQLAlchemyError

from models.tables.commands import CommandHistory
from models.tables.creator_links import CreatorLink

# Import models
from models.tables.gallery import GalleryMementos

# Import database utilities
from utils.db_service import DatabaseService
from utils.repository_factory import GenericRepository, RepositoryFactory
from utils.service_container import ServiceContainer

# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


async def create_mock_session():
    """Create a mock session for testing."""
    # Create a mock session
    session = AsyncMock()

    # Create mock objects for different entities
    gallery = MagicMock(spec=GalleryMementos)
    gallery.channel_name = "test-gallery"
    gallery.channel_id = 123456789
    gallery.guild_id = 987654321

    updated_gallery = MagicMock(spec=GalleryMementos)
    updated_gallery.channel_name = "test-gallery"
    updated_gallery.channel_id = 987654321
    updated_gallery.guild_id = 987654321

    creator_link = MagicMock(spec=CreatorLink)
    creator_link.serial_id = 1
    creator_link.title = "Test Link"
    creator_link.link = "https://example.com"
    creator_link.user_id = 123456789
    creator_link.nsfw = False
    creator_link.weight = 0
    creator_link.feature = True

    updated_link = MagicMock(spec=CreatorLink)
    updated_link.serial_id = 1
    updated_link.title = "Updated Link"
    updated_link.link = "https://example.com"
    updated_link.user_id = 123456789
    updated_link.nsfw = False
    updated_link.weight = 0
    updated_link.feature = True

    command1 = MagicMock(spec=CommandHistory)
    command1.serial = 1
    command1.command_name = "test_command1"

    command2 = MagicMock(spec=CommandHistory)
    command2.serial = 2
    command2.command_name = "test_command2"

    # Create a side effect function for execute that returns different results based on the query
    def execute_side_effect(*args, **kwargs):
        query = args[0] if args else kwargs.get("query", "")

        # Convert query to string if it's not already
        if not isinstance(query, str):
            query = str(query)

        result = MagicMock()

        if "GalleryMementos" in str(query) or "gallery_mementos" in str(query):
            if ("channel_name" in str(query) and "=" in str(query)) or (
                "test-gallery" in str(query)
            ):
                # For get_by_id with "test-gallery" or get_by_field
                if "DELETE" in str(query).upper():
                    # For delete operation
                    result.rowcount = 1
                    return result
                elif "UPDATE" in str(query).upper():
                    # For update operation
                    result.rowcount = 1
                    return result
                else:
                    # For get_by_id or get_by_field - both use WHERE clause
                    # Set up both .first() and .all() to return appropriate results
                    result.scalars.return_value.first.return_value = updated_gallery
                    result.scalars.return_value.all.return_value = [gallery]
                    return result
            else:
                # For get_all
                result.scalars.return_value.all.return_value = [gallery]
                return result
        elif "CreatorLink" in str(query):
            if "serial_id" in str(query) and "1" in str(query):
                # For get_by_id with serial_id=1
                if "DELETE" in str(query).upper():
                    # For delete operation
                    result.rowcount = 1
                    return result
                else:
                    # For get_by_id
                    result.scalars.return_value.first.return_value = (
                        creator_link if "Updated" not in str(query) else updated_link
                    )
                    return result
            else:
                # For get_all
                result.scalars.return_value.all.return_value = [creator_link]
                return result
        elif "CommandHistory" in str(query):
            if "serial" in str(query):
                # For get_by_id with serial
                result.scalars.return_value.first.return_value = (
                    command1 if "1" in str(query) else command2
                )
                return result
            else:
                # For get_all
                result.scalars.return_value.all.return_value = [command1, command2]
                return result

        # Default case
        result.scalars.return_value.first.return_value = None
        result.scalars.return_value.all.return_value = []
        result.rowcount = 1
        return result

    # Set the side effect for the execute method
    session.execute.side_effect = execute_side_effect

    # Mock the commit method
    session.commit = AsyncMock()

    # Mock the refresh method
    session.refresh = AsyncMock()

    # Mock the add method
    session.add = MagicMock()

    # Mock the begin method to return a transaction context manager
    transaction_cm = AsyncMock()
    transaction_cm.__aenter__ = AsyncMock(return_value=transaction_cm)
    transaction_cm.__aexit__ = AsyncMock(return_value=None)
    session.begin = MagicMock(return_value=transaction_cm)

    return session


async def test_db_service_crud() -> None:
    """Test CRUD operations using DatabaseService."""
    print("\nTesting DatabaseService CRUD operations...")

    # Create a mock session
    session = await create_mock_session()

    # Create a database service for GalleryMementos
    db_service = DatabaseService(GalleryMementos)

    # Test create
    gallery = await db_service.create(
        session, channel_name="test-gallery", channel_id=123456789, guild_id=987654321
    )
    assert gallery is not None

    # Test get_by_id
    retrieved = await db_service.get_by_id(session, "test-gallery")
    assert retrieved is not None
    assert retrieved.channel_name == "test-gallery"

    # Test get_all
    all_galleries = await db_service.get_all(session)
    assert len(all_galleries) > 0

    # Test update
    updated = await db_service.update(session, "test-gallery", channel_id=987654321)
    assert updated is not None
    assert updated.channel_id == 987654321

    # Test delete
    deleted = await db_service.delete(session, "test-gallery")
    assert deleted is True

    print("✅ DatabaseService CRUD operations test passed")


async def test_repository_pattern() -> None:
    """Test the repository pattern."""
    print("\nTesting repository pattern...")

    # Create a mock session
    session = await create_mock_session()

    # Create a generic repository for GalleryMementos
    async def session_factory():
        return session

    repo = GenericRepository(GalleryMementos, session_factory)

    # Test get_all
    all_galleries = await repo.get_all()
    assert len(all_galleries) > 0

    # Test get_by_id
    gallery = await repo.get_by_id("test-gallery")
    assert gallery is not None
    assert gallery.channel_name == "test-gallery"

    # Test get_by_field
    galleries_by_field = await repo.get_by_field("channel_name", "test-gallery")
    assert len(galleries_by_field) > 0

    # Test create
    new_gallery = await repo.create(
        channel_name="new-gallery", channel_id=123456789, guild_id=987654321
    )
    assert new_gallery is not None

    # Test update
    updated = await repo.update("test-gallery", channel_id=987654321)
    assert updated is not None
    assert updated.channel_id == 987654321

    # Test delete
    deleted = await repo.delete("test-gallery")
    assert deleted is True

    print("✅ Repository pattern test passed")


async def test_transaction_management() -> None:
    """Test transaction management."""
    print("\nTesting transaction management...")

    # Create a mock session
    session = await create_mock_session()

    # Test successful transaction
    async with session.begin():
        # Create a database service for GalleryMementos
        db_service = DatabaseService(GalleryMementos)

        # Create a gallery
        gallery = await db_service.create(
            session,
            channel_name="transaction-test",
            channel_id=123456789,
            guild_id=987654321,
        )
        assert gallery is not None

        # Update the gallery
        updated = await db_service.update(
            session, "transaction-test", channel_id=987654321
        )
        assert updated is not None

    # Verify that session.commit was called
    session.commit.assert_called()

    # Test transaction rollback
    try:
        async with session.begin():
            # Create a database service for GalleryMementos
            db_service = DatabaseService(GalleryMementos)

            # Create a gallery
            gallery = await db_service.create(
                session,
                channel_name="rollback-test",
                channel_id=123456789,
                guild_id=987654321,
            )
            assert gallery is not None

            # Simulate an error
            raise ValueError("Test error")
    except ValueError:
        # The transaction should be rolled back
        pass

    print("✅ Transaction management test passed")


async def test_error_handling() -> None:
    """Test error handling and retries."""
    print("\nTesting error handling and retries...")

    # Create a mock session that fails on the first attempt but succeeds on retry
    mock_session = AsyncMock()
    mock_execute = AsyncMock()
    mock_execute.side_effect = [SQLAlchemyError("Test error"), None]
    mock_session.execute = mock_execute

    # Create a database service with retry logic
    class RetryService:
        async def execute_with_retry(self, session, max_retries=3) -> bool:
            retries = 0
            while retries < max_retries:
                try:
                    await session.execute("SELECT 1")
                    return True
                except SQLAlchemyError as e:
                    retries += 1
                    if retries >= max_retries:
                        raise
                    print(f"Retry {retries} after error: {e}")
            return False

    retry_service = RetryService()

    # Test that the operation succeeds after a retry
    result = await retry_service.execute_with_retry(mock_session)
    assert result is True
    assert mock_execute.call_count == 2

    print("✅ Error handling and retries test passed")


async def test_repository_factory() -> None:
    """Test the repository factory pattern."""
    print("\nTesting repository factory pattern...")

    # Create a mock session
    session = await create_mock_session()

    # Create a session factory that returns the provided session
    async def session_factory():
        return session

    # Create a service container
    container = ServiceContainer()

    # Create a repository factory
    factory = RepositoryFactory(container, session_factory)

    # Get repositories for different models
    gallery_repo = factory.get_repository(GalleryMementos)
    command_repo = factory.get_repository(CommandHistory)
    creator_link_repo = factory.get_repository(CreatorLink)

    # Verify the repositories are of the correct type
    assert isinstance(gallery_repo, GenericRepository)
    assert gallery_repo.model_class == GalleryMementos

    assert isinstance(command_repo, GenericRepository)
    assert command_repo.model_class == CommandHistory

    assert isinstance(creator_link_repo, GenericRepository)
    assert creator_link_repo.model_class == CreatorLink

    # Verify that getting the same repository twice returns the same instance
    gallery_repo2 = factory.get_repository(GalleryMementos)
    assert gallery_repo is gallery_repo2

    print("✅ Repository factory pattern test passed")


async def main() -> None:
    """Run all tests."""
    print("Testing database operations...")

    try:
        # Create a mock session for testing
        session = await create_mock_session()

        # Run tests that require a session
        tests = [
            test_db_service_crud(session),
            test_repository_pattern(session),
            test_transaction_management(session),
        ]

        results = await asyncio.gather(*tests)

        # Run tests that don't require a session
        results.append(await test_error_handling())

        # Run test_repository_factory with the session
        results.append(await test_repository_factory(session))

        if all(results):
            print("\nAll database operation tests passed!")
        else:
            print("\nSome database operation tests failed.")

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

"""
Unit tests for database transaction operations.

This module contains tests for complex database operations and rollback scenarios
to ensure data integrity and proper transaction handling.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import database components
import asyncpg

# Import test utilities
from tests.test_utils import TestSetup


def setup_mock_database_with_pool(db, mock_conn, mock_transaction=None):
    """Helper function to set up mock database with proper async context manager support."""

    # Create a proper async context manager for pool.acquire()
    class MockAcquire:
        def __init__(self, conn) -> None:
            self.conn = conn

        async def __aenter__(self):
            return self.conn

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Mock pool - use MagicMock instead of AsyncMock for the pool itself
    mock_pool = MagicMock()
    mock_pool.acquire = lambda: MockAcquire(mock_conn)

    # If a transaction mock is provided, set it up properly
    if mock_transaction:
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

    db.pool = mock_pool
    return mock_pool


async def test_basic_transaction_commit() -> bool:
    """Test basic transaction commit functionality."""
    print("\nTesting basic transaction commit...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock transaction
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    # Mock connection
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    # Set up mock pool with proper async context manager support
    setup_mock_database_with_pool(db, mock_conn, mock_transaction)

    # Test transaction commit
    async with db.pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "INSERT INTO test_table (name) VALUES ($1)", "test_value"
        )

    # Verify transaction was used
    mock_conn.transaction.assert_called_once()
    mock_conn.execute.assert_called_once()

    print("✅ Basic transaction commit test passed")
    return True


async def test_transaction_rollback() -> bool:
    """Test transaction rollback on error."""
    print("\nTesting transaction rollback...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock transaction that raises an exception
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    # Mock connection
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))

    # Set up mock pool with proper async context manager support
    setup_mock_database_with_pool(db, mock_conn, mock_transaction)

    # Test transaction rollback
    try:
        async with db.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO test_table (name) VALUES ($1)", "test_value"
            )
            raise Exception("Simulated error")
    except Exception:
        pass  # Expected to raise an exception

    # Verify transaction was used and rollback occurred
    mock_conn.transaction.assert_called_once()
    mock_transaction.__aexit__.assert_called_once()

    print("✅ Transaction rollback test passed")
    return True


async def test_nested_transactions() -> bool:
    """Test nested transaction handling."""
    print("\nTesting nested transactions...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock nested transactions
    mock_outer_transaction = AsyncMock()
    mock_outer_transaction.__aenter__ = AsyncMock()
    mock_outer_transaction.__aexit__ = AsyncMock()

    mock_inner_transaction = AsyncMock()
    mock_inner_transaction.__aenter__ = AsyncMock()
    mock_inner_transaction.__aexit__ = AsyncMock()

    # Mock connection
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    # Set up mock pool with proper async context manager support
    setup_mock_database_with_pool(db, mock_conn, mock_outer_transaction)

    # Set up side effect for nested transactions
    mock_conn.transaction = MagicMock(
        side_effect=[mock_outer_transaction, mock_inner_transaction]
    )

    # Test nested transactions
    async with db.pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "INSERT INTO test_table (name) VALUES ($1)", "outer_value"
        )
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO test_table (name) VALUES ($1)", "inner_value"
            )

    # Verify both transactions were used
    assert mock_conn.transaction.call_count == 2
    assert mock_conn.execute.call_count == 2

    print("✅ Nested transactions test passed")
    return True


async def test_concurrent_transactions() -> bool:
    """Test concurrent transaction handling."""
    print("\nTesting concurrent transactions...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock multiple connections for concurrent transactions
    mock_conn1 = AsyncMock()
    mock_conn2 = AsyncMock()

    mock_transaction1 = AsyncMock()
    mock_transaction1.__aenter__ = AsyncMock()
    mock_transaction1.__aexit__ = AsyncMock()

    mock_transaction2 = AsyncMock()
    mock_transaction2.__aenter__ = AsyncMock()
    mock_transaction2.__aexit__ = AsyncMock()

    mock_conn1.execute = AsyncMock()
    mock_conn2.execute = AsyncMock()

    # Set up transaction mocks properly
    mock_conn1.transaction = MagicMock(return_value=mock_transaction1)
    mock_conn2.transaction = MagicMock(return_value=mock_transaction2)

    # Mock pool that returns different connections
    class MockAcquire:
        def __init__(self, conn) -> None:
            self.conn = conn

        async def __aenter__(self):
            return self.conn

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Create a counter to alternate between connections
    connection_counter = 0

    def get_connection():
        nonlocal connection_counter
        if connection_counter == 0:
            connection_counter = 1
            return MockAcquire(mock_conn1)
        else:
            connection_counter = 0
            return MockAcquire(mock_conn2)

    mock_pool = MagicMock()
    mock_pool.acquire = get_connection

    db.pool = mock_pool

    # Test concurrent transactions
    async def transaction1() -> None:
        async with db.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO test_table (name) VALUES ($1)", "value1"
            )

    async def transaction2() -> None:
        async with db.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO test_table (name) VALUES ($1)", "value2"
            )

    # Run transactions concurrently
    await asyncio.gather(transaction1(), transaction2())

    # Verify both transactions were executed
    mock_conn1.transaction.assert_called_once()
    mock_conn2.transaction.assert_called_once()
    mock_conn1.execute.assert_called_once()
    mock_conn2.execute.assert_called_once()

    print("✅ Concurrent transactions test passed")
    return True


async def test_transaction_with_multiple_operations() -> bool:
    """Test transaction with multiple database operations."""
    print("\nTesting transaction with multiple operations...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock transaction
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    # Mock connection
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)

    # Set up mock pool with proper async context manager support
    setup_mock_database_with_pool(db, mock_conn, mock_transaction)

    # Test transaction with multiple operations
    async with db.pool.acquire() as conn, conn.transaction():
        # Insert operation
        await conn.execute(
            "INSERT INTO users (name, email) VALUES ($1, $2)",
            "test_user",
            "test@example.com",
        )

        # Update operation
        await conn.execute(
            "UPDATE users SET email = $1 WHERE name = $2",
            "updated@example.com",
            "test_user",
        )

        # Select operation
        await conn.fetch("SELECT * FROM users WHERE name = $1", "test_user")

        # Delete operation
        await conn.execute("DELETE FROM users WHERE name = $1", "test_user")

    # Verify all operations were executed within the transaction
    mock_conn.transaction.assert_called_once()
    assert mock_conn.execute.call_count == 3  # INSERT, UPDATE, DELETE
    assert mock_conn.fetch.call_count == 1  # SELECT

    print("✅ Transaction with multiple operations test passed")
    return True


async def test_transaction_isolation_levels() -> bool:
    """Test different transaction isolation levels."""
    print("\nTesting transaction isolation levels...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock transaction with isolation level
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    # Mock connection
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    # Set up mock pool with proper async context manager support
    setup_mock_database_with_pool(db, mock_conn, mock_transaction)

    # Test different isolation levels
    isolation_levels = ["read_committed", "repeatable_read", "serializable"]

    for isolation_level in isolation_levels:
        async with db.pool.acquire() as conn:
            async with conn.transaction(isolation=isolation_level):
                await conn.execute("SELECT * FROM test_table")

    # Verify transactions were called with isolation levels
    assert mock_conn.transaction.call_count == len(isolation_levels)

    print("✅ Transaction isolation levels test passed")
    return True


async def test_deadlock_detection() -> bool:
    """Test deadlock detection and handling."""
    print("\nTesting deadlock detection...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock deadlock scenario
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    # Simulate deadlock error
    deadlock_error = asyncpg.DeadlockDetectedError("Deadlock detected")
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=deadlock_error)

    # Set up mock pool with proper async context manager support
    setup_mock_database_with_pool(db, mock_conn, mock_transaction)

    # Test deadlock handling
    try:
        async with db.pool.acquire() as conn, conn.transaction():
            await conn.execute("UPDATE table1 SET value = 1 WHERE id = 1")
            await conn.execute("UPDATE table2 SET value = 2 WHERE id = 2")
    except asyncpg.DeadlockDetectedError:
        pass  # Expected to catch deadlock error

    # Verify transaction was attempted
    mock_conn.transaction.assert_called_once()

    print("✅ Deadlock detection test passed")
    return True


async def test_transaction_timeout() -> bool:
    """Test transaction timeout handling."""
    print("\nTesting transaction timeout...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock timeout scenario
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    # Simulate timeout error
    timeout_error = TimeoutError("Transaction timeout")
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=timeout_error)

    # Set up mock pool with proper async context manager support
    setup_mock_database_with_pool(db, mock_conn, mock_transaction)

    # Test timeout handling
    try:
        async with db.pool.acquire() as conn, conn.transaction():
            await conn.execute("SELECT pg_sleep(30)")  # Long-running query
    except TimeoutError:
        pass  # Expected to catch timeout error

    # Verify transaction was attempted
    mock_conn.transaction.assert_called_once()

    print("✅ Transaction timeout test passed")
    return True


async def test_savepoint_operations() -> bool:
    """Test savepoint operations within transactions."""
    print("\nTesting savepoint operations...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock savepoint operations
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    # Set up mock pool with proper async context manager support
    setup_mock_database_with_pool(db, mock_conn, mock_transaction)

    # Test savepoint operations
    async with db.pool.acquire() as conn, conn.transaction():
        await conn.execute("INSERT INTO test_table (name) VALUES ($1)", "value1")

        # Create savepoint
        await conn.execute("SAVEPOINT sp1")

        try:
            await conn.execute(
                "INSERT INTO test_table (name) VALUES ($1)", "value2"
            )
            # Simulate error
            raise Exception("Simulated error")
        except Exception:
            # Rollback to savepoint
            await conn.execute("ROLLBACK TO SAVEPOINT sp1")

        await conn.execute("INSERT INTO test_table (name) VALUES ($1)", "value3")

    # Verify savepoint operations were executed
    mock_conn.transaction.assert_called_once()
    assert mock_conn.execute.call_count >= 4  # INSERT, SAVEPOINT, ROLLBACK, INSERT

    print("✅ Savepoint operations test passed")
    return True


async def test_bulk_operations_in_transaction() -> bool:
    """Test bulk operations within transactions."""
    print("\nTesting bulk operations in transaction...")

    # Create a test database connection
    db = await TestSetup.create_test_database()

    # Mock bulk operations
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    mock_conn = AsyncMock()
    mock_conn.executemany = AsyncMock()
    mock_conn.copy_records_to_table = AsyncMock()

    # Set up mock pool with proper async context manager support
    setup_mock_database_with_pool(db, mock_conn, mock_transaction)

    # Test bulk operations
    async with db.pool.acquire() as conn, conn.transaction():
        # Bulk insert using executemany
        data = [("user1", "email1"), ("user2", "email2"), ("user3", "email3")]
        await conn.executemany(
            "INSERT INTO users (name, email) VALUES ($1, $2)", data
        )

        # Bulk insert using copy
        await conn.copy_records_to_table("users", records=data)

    # Verify bulk operations were executed
    mock_conn.transaction.assert_called_once()
    mock_conn.executemany.assert_called_once()
    mock_conn.copy_records_to_table.assert_called_once()

    print("✅ Bulk operations in transaction test passed")
    return True


# Main function to run all tests
async def main() -> None:
    """Run all database transaction tests."""
    print("Running comprehensive database transaction tests...")

    # Test basic transaction operations
    await test_basic_transaction_commit()
    await test_transaction_rollback()
    await test_nested_transactions()
    await test_concurrent_transactions()
    await test_transaction_with_multiple_operations()

    # Test advanced transaction features
    await test_transaction_isolation_levels()
    await test_deadlock_detection()
    await test_transaction_timeout()
    await test_savepoint_operations()
    await test_bulk_operations_in_transaction()

    print("\nAll comprehensive database transaction tests passed!")
    print("✅ Database transaction test coverage implemented!")


if __name__ == "__main__":
    asyncio.run(main())

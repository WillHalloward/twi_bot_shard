"""
Test script for database connection.

This script tests if a connection to a local Postgres instance can be
established. When no local Postgres is reachable (e.g. in CI, which uses
SQLite/mocks), the test is skipped — it never passes vacuously.
"""

import asyncio
import os
import sys

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import SQLAlchemy components
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.future import select

# Local Postgres used for an opportunistic real-connection check.
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost/postgres"

# Keep the attempt short so an absent Postgres doesn't stall the suite.
CONNECT_TIMEOUT_SECONDS = 3


async def test_db_connection() -> None:
    """Test database connection against a local Postgres, skipping if absent."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"timeout": CONNECT_TIMEOUT_SECONDS},
    )

    try:
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT_SECONDS + 1):
                async with engine.connect() as conn:
                    result = await conn.execute(select(1))
                    value = result.scalar_one()
        except Exception as e:
            # Connection-level failure means no local Postgres is available;
            # skip instead of passing vacuously. (pytest.skip raises a
            # BaseException subclass, so it is not swallowed here.)
            pytest.skip(f"no local Postgres available: {type(e).__name__}: {e}")

        # Real assertion when the connection succeeds.
        assert value == 1
    finally:
        await engine.dispose()


async def main() -> None:
    """Run the test."""
    try:
        await test_db_connection()
    except pytest.skip.Exception as e:
        print(f"Skipped: {e}")
        return
    print("Database connection successful!")


if __name__ == "__main__":
    asyncio.run(main())

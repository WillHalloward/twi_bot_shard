"""
Test script for database connection.

This script tests if the database connection can be established.
"""

import asyncio
import os
import sys
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import SQLAlchemy components
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

# Import models
from models.base import Base

# Use PostgreSQL for testing - this is just for demonstration
# In a real test, you would use a test database or mock
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost/postgres"


async def test_db_connection():
    """Test database connection."""
    print("Testing database connection...")

    engine = None
    try:
        # Create test engine
        engine = create_async_engine(TEST_DATABASE_URL, echo=True)

        # Just test connection without creating tables
        async with engine.connect() as conn:
            result = await conn.execute(select(1))
            value = result.scalar_one()
            assert value == 1

        print("Database connection successful!")
        return True
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return False
    finally:
        # Close the engine if it was created
        if engine:
            await engine.dispose()


async def main():
    """Run the test."""
    result = await test_db_connection()

    if result:
        print("\nTest passed!")
    else:
        print("\nTest failed.")


if __name__ == "__main__":
    asyncio.run(main())

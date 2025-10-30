"""Script to apply additional database optimizations.

This script applies the optimizations defined in database/additional_optimizations.sql
and refreshes the materialized views.
"""

import asyncio
import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/optimizations.log")],
)

# Import required modules
import asyncpg

import config
from utils.db import Database


async def main() -> bool | None:
    """Apply database optimizations and print results."""
    logger = logging.getLogger("optimizations")
    logger.info("Starting database optimization process")

    try:
        # Create SSL context
        import ssl

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.load_verify_locations("ssl-cert/server-ca.pem")
        ssl_context.load_cert_chain(
            "ssl-cert/client-cert.pem", "ssl-cert/client-key.pem"
        )

        # Connect to the database
        logger.info(f"Connecting to database {config.database} on {config.host}")
        pool = await asyncpg.create_pool(
            user=config.DB_user,
            password=config.DB_password,
            database=config.database,
            host=config.host,
            port=config.port,
            ssl=ssl_context,
        )

        # Initialize database utility
        db = Database(pool)

        # Apply optimizations
        logger.info("Applying additional database optimizations")
        await db.apply_additional_optimizations()

        # Get cache statistics
        cache_stats = await db.get_cache_stats()
        logger.info(f"Cache statistics: {cache_stats}")

        # Close the connection pool
        await pool.close()

        logger.info("Database optimization process completed successfully")
        print("Database optimizations applied successfully!")
        return True
    except Exception as e:
        logger.error(f"Error during database optimization: {e}", exc_info=True)
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

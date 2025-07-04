import asyncio
import logging
import ssl
import traceback
import sys

import asyncpg
import config
from utils.db import Database


async def run_optimizations():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="[{asctime}] [{levelname:<8}] {name}: {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
        stream=sys.stdout,
    )

    logger = logging.getLogger("db_optimizations")
    logger.info("Starting database optimization script...")

    # Set up SSL context
    context = ssl.create_default_context()
    context.check_hostname = False
    context.load_verify_locations("ssl-cert/server-ca.pem")
    context.load_cert_chain("ssl-cert/client-cert.pem", "ssl-cert/client-key.pem")

    # Connect to database
    try:
        logger.info("Connecting to database...")
        pool = await asyncpg.create_pool(
            database=config.database,
            user=config.DB_user,
            password=config.DB_password,
            host=config.host,
            ssl=context,
            command_timeout=600,  # 10 minutes timeout
            min_size=1,
            max_size=5,
        )

        if not pool:
            logger.error("Failed to create database connection pool")
            return

        logger.info("Database connection established")

        # Create database utility
        db = Database(pool)

        # Execute optimization script
        try:
            logger.info("Executing database optimization script...")
            await db.execute_script("database/db_optimizations.sql", timeout=600.0)
            logger.info("Database optimizations applied successfully")
        except Exception as e:
            error_details = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            logger.error(
                f"Failed to apply database optimizations: {e}\n{error_details}"
            )

    except Exception as e:
        error_details = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(f"Database connection error: {e}\n{error_details}")
    finally:
        # Close the connection pool
        if "pool" in locals() and pool:
            await pool.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    asyncio.run(run_optimizations())

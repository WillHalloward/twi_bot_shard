#!/usr/bin/env python
"""Database optimization script.

This script applies database optimizations and refreshes materialized views.
Consolidates apply_optimizations.py and apply_additional.py into a single script.

Usage:
    python scripts/database/optimize.py [--base] [--additional] [--all]

Options:
    --base        Apply base optimizations from database/optimizations/base.sql
    --additional  Apply additional optimizations and refresh materialized views
    --all         Apply all optimizations (default if no flags specified)
"""

import argparse
import asyncio
import logging
import ssl
import sys
import traceback
from pathlib import Path

import asyncpg

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import config
from utils.db import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("db_optimize")


def create_ssl_context() -> ssl.SSLContext | None:
    """Create SSL context for database connection if certificates exist."""
    cert_path = Path("ssl-cert")
    if not cert_path.exists():
        logger.warning("SSL certificates not found, connecting without SSL")
        return None

    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.load_verify_locations(cert_path / "server-ca.pem")
        context.load_cert_chain(
            cert_path / "client-cert.pem",
            cert_path / "client-key.pem",
        )
        return context
    except Exception as e:
        logger.warning(f"Failed to load SSL certificates: {e}")
        return None


async def create_pool() -> asyncpg.Pool:
    """Create database connection pool."""
    ssl_context = create_ssl_context()

    pool = await asyncpg.create_pool(
        database=config.database,
        user=config.DB_user,
        password=config.DB_password,
        host=config.host,
        port=config.port,
        ssl=ssl_context,
        command_timeout=600,  # 10 minutes for long-running optimizations
        min_size=1,
        max_size=5,
    )

    if not pool:
        raise RuntimeError("Failed to create database connection pool")

    return pool


async def apply_base_optimizations(db: Database) -> bool:
    """Apply base database optimizations from SQL file."""
    logger.info("Applying base database optimizations...")
    try:
        await db.execute_script("database/optimizations/base.sql", timeout=600.0)
        logger.info("Base optimizations applied successfully")
        return True
    except Exception as e:
        error_details = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(f"Failed to apply base optimizations: {e}\n{error_details}")
        return False


async def apply_additional_optimizations(db: Database) -> bool:
    """Apply additional optimizations and refresh materialized views."""
    logger.info("Applying additional database optimizations...")
    try:
        await db.apply_additional_optimizations()

        # Log cache statistics
        cache_stats = await db.get_cache_stats()
        logger.info(f"Cache statistics: {cache_stats}")

        logger.info("Additional optimizations applied successfully")
        return True
    except Exception as e:
        error_details = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(f"Failed to apply additional optimizations: {e}\n{error_details}")
        return False


async def main(apply_base: bool = True, apply_additional: bool = True) -> bool:
    """Run database optimizations.

    Args:
        apply_base: Whether to apply base optimizations
        apply_additional: Whether to apply additional optimizations

    Returns:
        True if all requested optimizations succeeded, False otherwise
    """
    logger.info("Starting database optimization...")
    logger.info(f"Connecting to {config.database} on {config.host}")

    pool = None
    success = True

    try:
        pool = await create_pool()
        logger.info("Database connection established")

        db = Database(pool)

        if apply_base and not await apply_base_optimizations(db):
            success = False

        if apply_additional and not await apply_additional_optimizations(db):
            success = False

        if success:
            logger.info("Database optimization completed successfully")
        else:
            logger.warning("Some optimizations failed - check logs above")

    except Exception as e:
        error_details = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(f"Database optimization failed: {e}\n{error_details}")
        success = False
    finally:
        if pool:
            await pool.close()
            logger.info("Database connection closed")

    return success


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Apply database optimizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base",
        action="store_true",
        help="Apply base optimizations only",
    )
    parser.add_argument(
        "--additional",
        action="store_true",
        help="Apply additional optimizations only",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Apply all optimizations (default)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Default to all if no specific flag is set
    no_specific_flag = not args.base and not args.additional
    apply_base = no_specific_flag or args.base or args.all
    apply_additional = no_specific_flag or args.additional or args.all

    success = asyncio.run(main(apply_base, apply_additional))
    sys.exit(0 if success else 1)

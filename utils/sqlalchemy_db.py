"""SQLAlchemy database connection and session management."""

import os
import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import config


# Create SSL context
def create_ssl_context():
    """Create SSL context for database connection.

    Returns:
        SSL context for GCP Cloud SQL, False for Railway pgvector, or override value.
    """
    # Check for DB_SSL override (same as main.py)
    db_ssl_override = os.getenv("DB_SSL", "").lower()

    if db_ssl_override in ("disable", "false", "no", "off"):
        # Explicitly disabled (e.g., Railway pgvector template)
        return False

    # Check if we're on Railway (which provides DATABASE_URL)
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Railway environment - default to no SSL for pgvector compatibility
        # Set DB_SSL=require if using standard Railway Postgres with SSL
        return db_ssl_override if db_ssl_override else False
    else:
        # GCP Cloud SQL - use custom SSL certificates
        context = ssl.create_default_context()
        context.check_hostname = False
        context.load_verify_locations("ssl-cert/server-ca.pem")
        context.load_cert_chain("ssl-cert/client-cert.pem", "ssl-cert/client-key.pem")
        return context


# Connection URL
# Use DATABASE_URL if available (Railway), otherwise build from individual components (GCP/local)
database_url_env = os.getenv("DATABASE_URL")
if database_url_env:
    # Railway provides DATABASE_URL in postgres:// format, need to convert to postgresql+asyncpg://
    DATABASE_URL = database_url_env.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    # Build from individual components for GCP/local development
    DATABASE_URL = f"postgresql+asyncpg://{config.DB_user}:{config.DB_password}@{config.host}/{config.database}"

# Create engine with SSL config matching main.py asyncpg pool
ssl_context = create_ssl_context()
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": ssl_context} if ssl_context else {},
    echo=False,  # Set to True for SQL query logging
    poolclass=None,  # Use default pooling
    pool_size=20,  # Maximum number of connections
    max_overflow=0,  # Maximum number of connections that can be created beyond pool_size
    pool_timeout=30,  # Seconds to wait before giving up on getting a connection from the pool
    pool_recycle=300,  # Recycle connections after 5 minutes
    pool_pre_ping=True,  # Check connection validity before using it
)

# Session factory
async_session_maker = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

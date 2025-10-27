"""SQLAlchemy database connection and session management."""

import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import config


# Create SSL context
def create_ssl_context():
    """Create SSL context for database connection."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.load_verify_locations("ssl-cert/server-ca.pem")
    context.load_cert_chain("ssl-cert/client-cert.pem", "ssl-cert/client-key.pem")
    return context


# Connection URL
DATABASE_URL = f"postgresql+asyncpg://{config.DB_user}:{config.DB_password}@{config.host}/{config.database}"

# Create engine with SSL
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": create_ssl_context()},
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

# Database Guide

This document provides comprehensive guidance for database access, best practices, and performance optimizations in the Twi Bot Shard project.

## Overview

The project uses PostgreSQL with a dual database access approach:

1. **Raw asyncpg** (`self.bot.db`): For simple queries, bulk operations, and performance-critical code
2. **SQLAlchemy ORM** (via repositories): For structured data access with type safety and complex operations

Additionally, the project implements several performance optimizations including indexes, materialized views, and query caching.

## Database Access Patterns

### Raw asyncpg via `self.bot.db`

For simple queries, bulk operations, and performance-critical code:

```python
# Fetch multiple rows
results = await self.bot.db.fetch(
    "SELECT * FROM gallery_mementos WHERE guild_id = $1",
    guild_id
)

# Fetch a single row
row = await self.bot.db.fetchrow(
    "SELECT * FROM messages WHERE message_id = $1",
    message_id
)

# Fetch a single value
count = await self.bot.db.fetchval(
    "SELECT COUNT(*) FROM messages WHERE channel_id = $1",
    channel_id
)

# Execute a query (INSERT, UPDATE, DELETE)
await self.bot.db.execute(
    "INSERT INTO gallery_mementos(channel_name, channel_id, guild_id) VALUES($1, $2, $3)",
    channel_name, channel_id, guild_id
)
```

### SQLAlchemy ORM via Repositories

For structured data access with type safety and complex operations:

```python
from utils.repositories import GalleryMigrationRepository

class GalleryCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        # Initialize repository with bot.get_db_session (not called, just passed)
        self.migration_repo = GalleryMigrationRepository(bot.get_db_session)

    async def some_command(self, ctx):
        # Repository handles session management internally
        entry = await self.migration_repo.get_by_message_id(message_id)
        stats = await self.migration_repo.get_statistics()
```

### Choosing the Right Access Method

| Use Case | Recommended Method |
|----------|-------------------|
| Simple SELECT queries | `self.bot.db.fetch()` / `fetchrow()` / `fetchval()` |
| Bulk INSERT/UPDATE | `self.bot.db.execute_many()` or `copy_records_to_table()` |
| Complex business logic | Repository with SQLAlchemy |
| Type-safe structured access | Repository with SQLAlchemy |
| Transactions with multiple models | Repository with SQLAlchemy |
| Raw SQL performance | `self.bot.db.*` methods |

**Use Raw asyncpg When:**
- Performing simple queries with known SQL
- Doing bulk operations (INSERT, UPDATE, DELETE)
- Performance is critical
- Working with raw data that doesn't need ORM mapping
- Running administrative queries

**Use SQLAlchemy Repositories When:**
- Working with complex domain models
- Need type safety and IDE support
- Building reusable data access patterns
- Managing related entities with relationships
- Implementing business logic around data

## Best Practices

### Repository Pattern Implementation

Repositories take a session factory callable and manage their own sessions:

```python
from collections.abc import Awaitable, Callable
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.my_model import MyModel


class MyRepository:
    """Repository for managing MyModel data."""

    def __init__(self, session_factory: Callable[[], Awaitable[AsyncSession]]) -> None:
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)

    async def get_by_id(self, id_value: int) -> MyModel | None:
        """Get a record by ID."""
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(MyModel).where(MyModel.id == id_value)
                )
                return result.scalar_one_or_none()
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting record by ID {id_value}: {e}")
            return None

    async def create(self, **kwargs) -> MyModel | None:
        """Create a new record."""
        try:
            session = await self.session_factory()
            try:
                entry = MyModel(**kwargs)
                session.add(entry)
                await session.commit()
                await session.refresh(entry)
                return entry
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error creating record: {e}")
            return None
```

### Using Repositories in Cogs

```python
from utils.base_cog import BaseCog
from utils.repositories import GalleryMigrationRepository


class MyCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        # Pass bot.get_db_session as the session factory (not called)
        self.migration_repo = GalleryMigrationRepository(bot.get_db_session)

    async def cog_load(self) -> None:
        # Use raw asyncpg for simple queries
        self.cache = await self.bot.db.fetch("SELECT * FROM gallery_mementos")

    async def some_command(self, ctx, message_id: int):
        # Use repository for structured operations
        entry = await self.migration_repo.get_by_message_id(message_id)
        if entry:
            await ctx.send(f"Found entry: {entry.title}")
```

### Transactions

#### Raw asyncpg Transactions

```python
# Using transaction context manager
async with await self.bot.db.transaction():
    await self.bot.db.execute("INSERT INTO table1(...) VALUES(...)", ...)
    await self.bot.db.execute("UPDATE table2 SET ... WHERE ...", ...)

# Using execute_in_transaction for multiple queries
queries = [
    ("INSERT INTO table1(name, value) VALUES($1, $2)", ("example1", 100)),
    ("UPDATE table2 SET value = value + $1 WHERE name = $2", (50, "example1")),
]
await self.bot.db.execute_in_transaction(queries)
```

#### SQLAlchemy Transactions

Within repository methods, transactions are managed per-session:

```python
async def transfer_data(self, from_id: int, to_id: int) -> bool:
    """Transfer data between records atomically."""
    try:
        session = await self.session_factory()
        try:
            async with session.begin():
                # Both operations succeed or fail together
                await session.execute(
                    update(MyModel).where(MyModel.id == from_id).values(active=False)
                )
                await session.execute(
                    update(MyModel).where(MyModel.id == to_id).values(active=True)
                )
            return True
        finally:
            await session.close()
    except Exception as e:
        self.logger.error(f"Error in transfer: {e}")
        return False
```

### Bulk Operations

#### Raw asyncpg (Recommended for Large Datasets)

```python
# Batch insert with execute_many
records = [(user.id, user.name, user.created_at) for user in users]
await self.bot.db.execute_many(
    "INSERT INTO users(id, name, created_at) VALUES($1, $2, $3) ON CONFLICT DO NOTHING",
    records
)

# High-performance COPY for very large datasets
await self.bot.db.copy_records_to_table(
    "messages",
    records=records,
    columns=["message_id", "content", "created_at"]
)
```

#### SQLAlchemy Bulk Operations

```python
async def bulk_create_entries(self, entries: list[dict]) -> int:
    """Bulk create entries, skipping duplicates."""
    created_count = 0
    try:
        session = await self.session_factory()
        try:
            for entry_data in entries:
                entry = MyModel(**entry_data)
                session.add(entry)
                created_count += 1
            await session.commit()
            return created_count
        finally:
            await session.close()
    except Exception as e:
        self.logger.error(f"Error in bulk create: {e}")
        return 0
```

### Error Handling

Always use try-except blocks for database operations:

```python
from utils.exceptions import DatabaseError


async def get_user_data(self, user_id: int):
    try:
        session = await self.session_factory()
        try:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
        finally:
            await session.close()
    except SQLAlchemyError as e:
        self.logger.error(f"Database error when getting user {user_id}: {e}")
        raise DatabaseError(f"Could not retrieve user data: {e}")
```

### SQLAlchemy Model Definition

Use declarative models with type annotations:

```python
from sqlalchemy import BigInteger, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class GalleryMementos(Base):
    """Model for gallery_mementos table."""
    __tablename__ = "gallery_mementos"

    channel_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Composite index for queries that filter by both fields
    __table_args__ = (
        Index('idx_gallery_guild_channel', 'guild_id', 'channel_id'),
    )
```

### Query Building with SQLAlchemy

Use SQLAlchemy's expression language for complex queries:

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Simple query
stmt = select(GalleryMementos).where(GalleryMementos.guild_id == guild_id)

# Query with join
stmt = (
    select(GalleryMementos, Guild.name)
    .join(Guild, GalleryMementos.guild_id == Guild.id)
    .where(GalleryMementos.channel_id == channel_id)
)

# Query with ordering and pagination
stmt = (
    select(GalleryMementos)
    .where(GalleryMementos.guild_id == guild_id)
    .order_by(GalleryMementos.channel_name)
    .limit(page_size)
    .offset((page - 1) * page_size)
)
```

## Performance Optimizations

The database includes several optimization strategies to improve query performance and reduce load.

### Database Indexes

#### Using Indexes in Models

```python
class Messages(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    author_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Composite index for queries filtering by both channel and author
    __table_args__ = (
        Index('idx_channel_author', 'channel_id', 'author_id'),
    )
```

#### Additional Indexes

The following indexes have been added to improve query performance:

**Message-related Indexes:**
- `idx_messages_created_at_range`: Index for message queries by date range, with a partial condition to only include recent messages
- `idx_active_messages`: Partial index for non-deleted messages in active channels

**Thread-related Indexes:**
- `idx_threads_parent_archived`: Index for thread queries by parent and archived status
- `idx_active_threads`: Partial index for active threads (not archived and not deleted)

**Role-related Indexes:**
- `idx_role_membership_by_server`: Index for role membership queries by server

**Reaction-related Indexes:**
- `idx_reactions_recent`: Partial index for recent reactions

**Other Indexes:**
- `idx_updates_date`: Index for the updates table by date
- `idx_updates_table_action`: Index for the updates table by table and action
- `idx_join_leave_server_date`: Index for join_leave table by server and date

### Materialized Views

Pre-computed views for complex queries to reduce computation time:

**User Activity Views:**
- `user_channel_activity`: User activity by channel for the last 30 days
- `weekly_message_stats`: Weekly message statistics for the last 90 days

**Existing Views:**
- `daily_message_stats`: Daily message statistics
- `daily_member_stats`: Daily member join/leave statistics
- `user_activity_stats`: User activity statistics
- `channel_hourly_stats`: Channel activity by hour

**Using Materialized Views:**

```python
# Get user activity by channel
results = await db.fetch("SELECT * FROM user_channel_activity WHERE user_id = $1", user_id)

# Get weekly message statistics
results = await db.fetch("SELECT * FROM weekly_message_stats WHERE server_id = $1", server_id)

# Refresh materialized views
await db.refresh_materialized_views()
```

### Eager Loading for Related Data

```python
from sqlalchemy.orm import selectinload, joinedload

stmt = (
    select(GalleryMementos)
    .options(selectinload(GalleryMementos.guild))
    .where(GalleryMementos.channel_id == channel_id)
)
```

## Query Caching

A query caching mechanism reduces database load for frequently accessed data.

### Cache Configuration

- **Max Size**: 2000 query results
- **Default TTL**: 5 minutes (300 seconds)
- **Cache Invalidation**: Automatic invalidation when tables are modified

### Cached Methods

The following database methods support caching:
- `fetch`: Execute a query and return all results
- `fetchrow`: Execute a query and return the first row
- `fetchval`: Execute a query and return a single value

### Cache Control

Control caching behavior with these parameters:
- `use_cache`: Whether to use cache for a specific query (default: True)
- `invalidate_cache`: Whether to invalidate cache for affected tables when executing a modification query (default: True)

### Usage Examples

```python
# Fetch data with caching (default)
results = await db.fetch("SELECT * FROM messages WHERE channel_id = $1", channel_id)

# Fetch data without caching
results = await db.fetch("SELECT * FROM messages WHERE channel_id = $1", channel_id, use_cache=False)

# Get cache statistics
stats = await db.get_cache_stats()
print(f"Cache hit rate: {stats['hit_rate']}%")
```

### Caching in Cogs

```python
async def get_gallery_channels(self, guild_id: int):
    # Check cache first
    cache_key = f"gallery_channels:{guild_id}"
    cached = self.cache.get(cache_key)
    if cached:
        return cached

    # Query database
    result = await self.bot.db.fetch(
        "SELECT * FROM gallery_mementos WHERE guild_id = $1",
        guild_id
    )

    # Store in cache
    self.cache.set(cache_key, result, ttl=3600)  # 1 hour TTL
    return result
```

### Cache Statistics

Get cache statistics using the `get_cache_stats` method:
- `hits`: Number of cache hits
- `misses`: Number of cache misses
- `hit_rate`: Cache hit rate as a percentage
- `evictions`: Number of cache entries evicted due to size limits or expiration
- `invalidations`: Number of cache entries invalidated due to table modifications
- `total_requests`: Total number of cache requests

## Applying Optimizations

The optimizations can be applied using the scripts in `scripts/database/`:

### Base Optimizations

Apply core database optimizations (indexes, views, functions) defined in `database/optimizations/base.sql`:

```bash
python scripts/database/apply_optimizations.py
```

### Additional Optimizations

Apply additional indexes and materialized views defined in `database/optimizations/additional.sql`:

```bash
python scripts/database/apply_additional.py
```

This script will:
1. Apply the additional indexes and materialized views
2. Refresh the materialized views to ensure they're populated
3. Print the results of the optimization process

### Expected Performance Impact

The implemented optimizations significantly improve performance for:
- Queries that filter by date range
- Queries that join multiple tables
- Frequently repeated queries
- Complex statistical queries

Monitor the slow query logs to identify any remaining performance issues.

## Database Migrations with Alembic

For database schema changes, use Alembic for version-controlled migrations:

### Setup

1. Initialize Alembic:
```bash
alembic init migrations
```

2. Configure `alembic.ini` to use your database URL

3. Update `migrations/env.py` to import your models and use async engine

### Creating Migrations

```bash
# Create initial migration (auto-generates based on model changes)
alembic revision --autogenerate -m "Initial migration"

# Create a manual migration
alembic revision -m "Add new column to messages"
```

### Applying Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Upgrade to a specific revision
alembic upgrade abc123

# Downgrade one revision
alembic downgrade -1

# View current revision
alembic current

# View migration history
alembic history
```

## Advanced Features

### Prepared Statements

For frequently executed queries, use prepared statements to improve performance:

```python
# Prepare a statement once
stmt = await db.prepare_statement("get_user", "SELECT * FROM users WHERE user_id = $1")

# Use it multiple times
user = await stmt.fetchrow(user_id)  # Get a single row
value = await stmt.fetchval(user_id)  # Get a single value
all_users = await stmt.fetch(user_id)  # Get all rows
await stmt.execute(user_id)  # Execute without returning results
```

### Connection Health Checks

The database class provides methods to validate connection health:

```python
# Check if a single connection is healthy
is_healthy = await db.check_connection_health()

# Validate all connections in the pool
await db.validate_connections()
```

### Query Performance Monitoring

The database utility logs slow queries (taking more than 500ms by default) for debugging and optimization:
- Query text is logged with execution time
- Use these logs to identify candidates for optimization

### Autovacuum Settings

Large tables have optimized autovacuum settings to prevent bloat:

```sql
-- For high-churn tables like reactions and role_membership
ALTER TABLE reactions SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_vacuum_cost_delay = 2
);
```

### Database Maintenance

A maintenance function is available for index rebuilding:

```sql
-- Rebuild indexes with high fragmentation
SELECT maintain_indexes();
```

## Connection Pool Configuration

The database connection pool is configured in `main.py`:

```python
asyncpg.create_pool(
    database=config.database,
    user=config.DB_user,
    password=config.DB_password,
    host=config.host,
    ssl=context,
    command_timeout=300,
    min_size=5,           # Minimum number of connections
    max_size=20,          # Maximum number of connections
    max_inactive_connection_lifetime=300.0,  # Close inactive connections after 5 minutes
    timeout=10.0          # Connection timeout
)
```

These settings can be adjusted based on application workload requirements.

## Related Documentation

- `utils/db.py`: Raw asyncpg Database class implementation
- `utils/repositories/`: Repository implementations
- `database/optimizations/`: SQL optimization scripts

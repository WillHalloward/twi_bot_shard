# Database Documentation for Cognita Bot

This document provides comprehensive documentation for the database functionality in the Cognita Discord bot, including the Database Utility Module, SQLAlchemy integration, and database optimizations.

## Table of Contents

1. [Database Utility Module](#database-utility-module)
2. [SQLAlchemy Integration](#sqlalchemy-integration)
3. [Database Optimizations](#database-optimizations)
4. [SQLAlchemy Model Updates](#sqlalchemy-model-updates)

## Database Utility Module

The Database Utility Module provides a robust and efficient way to interact with the PostgreSQL database in the Cognita bot.

### Features

- **Error handling with retries**: Automatically retries failed database operations with exponential backoff
- **Transaction management**: Easily execute multiple queries in a single transaction
- **Connection pooling**: Efficiently manages database connections to prevent leaks and improve performance
- **Parameterized queries**: Prevents SQL injection by using parameterized queries
- **Comprehensive logging**: Detailed logging of database operations and errors

### Usage

#### Basic Queries

```python
# Execute a query that doesn't return rows
await bot.db.execute(
    "INSERT INTO example_table(name, value) VALUES($1, $2)",
    "example", 100
)

# Fetch multiple rows
results = await bot.db.fetch(
    "SELECT * FROM example_table WHERE value > $1",
    50
)

# Fetch a single row
row = await bot.db.fetchrow(
    "SELECT * FROM example_table WHERE name = $1",
    "example"
)

# Fetch a single value
value = await bot.db.fetchval(
    "SELECT value FROM example_table WHERE name = $1",
    "example"
)
```

#### Transactions

```python
# Execute multiple queries in a transaction
queries = [
    ("INSERT INTO example_table(name, value) VALUES($1, $2)", ("example1", 100)),
    ("UPDATE example_table SET value = value + $1 WHERE name = $2", (50, "example1")),
    ("INSERT INTO example_log(action, timestamp) VALUES($1, NOW())", ("example_transaction",))
]

await bot.db.execute_in_transaction(queries)

# Or use a transaction context manager
async with bot.db.pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute("INSERT INTO example_table(name, value) VALUES($1, $2)", "example2", 200)
        await conn.execute("UPDATE example_stats SET count = count + 1")
```

#### Error Handling

The Database class automatically handles retries for transient errors, but you should still wrap your code in try/except blocks to handle other errors:

```python
try:
    await bot.db.execute(
        "INSERT INTO example_table(name, value) VALUES($1, $2)",
        "example", 100
    )
except Exception as e:
    logging.error(f"Error inserting data: {e}")
    # Handle the error appropriately
```

### Best Practices

1. **Use transactions for related operations**: When performing multiple related database operations, use transactions to ensure they are executed atomically.

2. **Handle errors appropriately**: Always wrap database operations in try/except blocks and handle errors appropriately.

3. **Use parameterized queries**: Always use parameterized queries to prevent SQL injection.

4. **Limit result sets**: When fetching data, use LIMIT clauses to prevent fetching too much data.

5. **Use appropriate methods**: Use the appropriate method for your query:
   - `execute` for queries that don't return rows (INSERT, UPDATE, DELETE)
   - `fetch` for queries that return multiple rows
   - `fetchrow` for queries that return a single row
   - `fetchval` for queries that return a single value

6. **Avoid long-running transactions**: Keep transactions as short as possible to avoid locking tables for too long.

7. **Use indexes**: Ensure your database tables have appropriate indexes for your queries.

### Configuration

The database connection pool is configured in `main.py` with the following settings:

```python
asyncpg.create_pool(
    database=secrets.database,
    user=secrets.DB_user,
    password=secrets.DB_password,
    host=secrets.host,
    ssl=context,
    command_timeout=300,
    min_size=5,           # Minimum number of connections
    max_size=20,          # Maximum number of connections
    max_inactive_connection_lifetime=300.0,  # Close inactive connections after 5 minutes
    timeout=10.0          # Connection timeout
)
```

These settings can be adjusted based on the specific needs of your application.

## SQLAlchemy Integration

SQLAlchemy is an Object-Relational Mapping (ORM) library for Python that provides a high-level, Pythonic interface to databases. It allows you to work with database tables as Python classes and records as Python objects, making database operations more intuitive and type-safe.

The integration in this project follows a gradual migration approach, maintaining compatibility with the existing asyncpg-based database utility while introducing SQLAlchemy for new features and refactoring existing ones.

### Directory Structure

```
twi_bot_shard/
├── models/
│   ├── __init__.py
│   ├── base.py
│   └── tables/
│       ├── __init__.py
│       ├── gallery.py
│       ├── commands.py
│       ├── messages.py
│       ├── reactions.py
│       ├── join_leave.py
│       └── creator_links.py
└── utils/
    ├── db.py (existing asyncpg utility)
    ├── sqlalchemy_db.py (SQLAlchemy engine and session setup)
    └── db_service.py (generic database service for CRUD operations)
```

### Key Components

#### 1. Base Model (models/base.py)

The `Base` class serves as the foundation for all SQLAlchemy models. It inherits from `AsyncAttrs`, `MappedAsDataclass`, and `DeclarativeBase` to provide async support and dataclass-like behavior.

```python
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

class Base(AsyncAttrs, MappedAsDataclass, DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    pass
```

#### 2. Table Models (models/tables/)

Each database table has a corresponding model class that defines its structure and relationships. For example:

```python
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

class GalleryMementos(Base):
    __tablename__ = "gallery_mementos"
    
    channel_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, unique=True)
    guild_id: Mapped[int] = mapped_column(Integer)
```

#### 3. Database Connection (utils/sqlalchemy_db.py)

This module sets up the SQLAlchemy engine and session factory with proper SSL configuration:

```python
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
    engine, 
    expire_on_commit=False,
    class_=AsyncSession
)
```

#### 4. Database Service (utils/db_service.py)

A generic service class that provides CRUD operations for any model:

```python
class DatabaseService(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model
    
    async def create(self, session: AsyncSession, **kwargs) -> T:
        # Create a new record
        
    async def get_by_id(self, session: AsyncSession, id_value: Any) -> Optional[T]:
        # Get a record by primary key
        
    async def get_all(self, session: AsyncSession) -> List[T]:
        # Get all records
        
    # ... other methods
```

### Usage in Cogs

#### 1. Initialize Database Services

```python
def __init__(self, bot):
    self.bot = bot
    # Create database services
    self.gallery_service = DatabaseService(GalleryMementos)
    self.creator_links_service = DatabaseService(CreatorLink)
```

#### 2. Query Data

```python
async def cog_load(self) -> None:
    # Use SQLAlchemy to load gallery mementos
    async with self.bot.get_db_session() as session:
        # Query gallery mementos
        stmt = select(GalleryMementos)
        result = await session.execute(stmt)
        self.repost_cache = result.scalars().all()
```

#### 3. Create, Update, or Delete Data

```python
async def set_repost(self, interaction: discord.Interaction, channel: discord.TextChannel):
    async with self.bot.get_db_session() as session:
        # Check if channel exists in database
        stmt = select(GalleryMementos).where(GalleryMementos.channel_id == channel.id)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        
        if existing:
            # Delete existing channel
            await session.delete(existing)
            await session.commit()
        else:
            # Add new channel
            new_channel = GalleryMementos(
                channel_name=channel.name,
                channel_id=channel.id,
                guild_id=channel.guild.id
            )
            session.add(new_channel)
            await session.commit()
```

### Database Migrations with Alembic

For database schema changes, use Alembic:

1. Initialize Alembic:
```bash
alembic init migrations
```

2. Configure `alembic.ini` to use your database URL

3. Update `migrations/env.py` to import your models and use async engine

4. Create initial migration:
```bash
alembic revision --autogenerate -m "Initial migration"
```

5. Apply migrations:
```bash
alembic upgrade head
```

### Gradual Migration Strategy

The project follows a gradual migration strategy:

1. New features are implemented using SQLAlchemy
2. Existing features are refactored to use SQLAlchemy as needed
3. The existing asyncpg-based database utility is maintained for backward compatibility

This approach allows for a smooth transition to SQLAlchemy without disrupting existing functionality.

## Database Optimizations

The following optimizations have been implemented to improve performance, reliability, and efficiency of the Cognita Discord bot's database.

### Recent Optimizations (2023)

#### Schema Improvements

##### Primary Keys
Added missing primary key constraints to ensure data integrity and improve query performance:
- `attachments` table: Added primary key on `id` column
- `foliana_interlude` table: Added primary key on `serial_id` column
- `invisible_text_twi` table: Added primary key on `serial_id` column
- `password_link` table: Added primary key on `serial_id` column
- `quotes` table: Added primary key on `serial_id` column
- `banned_words` table: Added primary key on `serial_id` column

##### Foreign Key Constraints
Added foreign key constraints to ensure referential integrity:
- `attachments.message_id` references `messages.message_id`
- `mentions.message_id` references `messages.message_id`

#### Additional Indexes

##### Composite Indexes
Added composite indexes for common query patterns:
- `idx_messages_channel_created_at` on `messages(channel_id, created_at DESC)` for efficient channel message retrieval
- `idx_messages_user_created_at` on `messages(user_id, created_at DESC)` for user activity queries
- `idx_reactions_message_emoji` on `reactions(message_id, emoji_id)` for reaction queries
- `idx_reactions_message_unicode` on `reactions(message_id, unicode_emoji)` for unicode reaction queries
- `idx_role_membership_role` on `role_membership(role_id)` for role membership queries

##### Foreign Key Indexes
Added indexes for foreign keys to improve join performance:
- `idx_attachments_message_id` on `attachments(message_id)`
- `idx_creator_links_user_id` on `creator_links(user_id)`

##### Partial Indexes
Added partial indexes for specific query patterns:
- `idx_messages_active` on `messages(channel_id, created_at)` where `deleted = FALSE`
- `idx_threads_active` on `threads(guild_id, parent_id)` where `deleted = FALSE`

##### Full-Text Search Indexes
Added GIN indexes for text search:
- `idx_quotes_text_search` on `quotes` using GIN(tokens)
- `idx_poll_option_text_search` on `poll_option` using GIN(tokens)

#### New Materialized Views
Added materialized views for complex statistics:
- `user_activity_stats`: Aggregates message counts and activity metrics per user
- `channel_hourly_stats`: Aggregates message counts by channel and hour

#### Autovacuum Settings
Optimized autovacuum settings for large tables:
- `reactions` table: Set `autovacuum_vacuum_scale_factor = 0.05` and `autovacuum_vacuum_cost_delay = 2`
- `role_membership` table: Set `autovacuum_vacuum_scale_factor = 0.05` and `autovacuum_vacuum_cost_delay = 2`

#### Code Optimizations
- Improved `save_users` method to use `ANY` operator for more efficient queries
- Optimized `save` method to batch query for last messages in all channels and threads
- Implemented prepared statements for frequent message and user operations

#### Maintenance Functions
Added a database maintenance function:
- `maintain_indexes()`: Rebuilds indexes with high fragmentation

### Previous Optimizations

#### Connection Management Improvements

##### Connection Pool Configuration
- The connection pool is configured with appropriate settings for the workload:
  ```python
  min_size=5,           # Minimum number of connections
  max_size=20,          # Maximum number of connections
  max_inactive_connection_lifetime=300.0,  # Close inactive connections after 5 minutes
  timeout=10.0          # Connection timeout
  ```

##### Connection Health Checks
- Added methods to validate connections and ensure they're still valid:
  - `check_connection_health()` - Checks if a single connection is healthy
  - `validate_connections()` - Validates all connections in the pool

#### Query Optimization

##### Prepared Statements
- Implemented a prepared statement cache to improve performance for frequently executed queries:
  ```python
  async def prepare_statement(self, name: str, query: str) -> asyncpg.PreparedStatement:
      if name not in self.prepared_statements:
          async with self.pool.acquire() as conn:
              stmt = await conn.prepare(query)
              self.prepared_statements[name] = stmt
      return self.prepared_statements[name]
  ```

##### Query Performance Monitoring
- Added query timing to all database operations:
  - Logs slow queries (taking more than 500ms by default)
  - Includes query text and execution time for debugging

##### Database Indexes
- Added indexes for frequently queried columns:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
  CREATE INDEX IF NOT EXISTS idx_messages_server_id ON messages(server_id);
  CREATE INDEX IF NOT EXISTS idx_messages_channel_id ON messages(channel_id);
  ```
- Created composite indexes for common query patterns:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_messages_server_created ON messages(server_id, created_at);
  ```

##### Materialized Views
- Created materialized views for complex statistical queries:
  ```sql
  CREATE MATERIALIZED VIEW IF NOT EXISTS daily_message_stats AS
  SELECT 
      COUNT(*) AS total, 
      channel_id,
      channel_name,
      server_id
  FROM messages 
  WHERE created_at >= NOW() - INTERVAL '1 DAY'
  AND server_id = 346842016480755724 
  AND is_bot = FALSE
  GROUP BY channel_id, channel_name, server_id
  ORDER BY total DESC;
  ```
- Added a function to refresh materialized views:
  ```sql
  CREATE OR REPLACE FUNCTION refresh_materialized_views()
  RETURNS void AS $$
  BEGIN
      REFRESH MATERIALIZED VIEW daily_message_stats;
      REFRESH MATERIALIZED VIEW daily_member_stats;
  END;
  $$ LANGUAGE plpgsql;
  ```

#### Batch Operations

##### Bulk Inserts
- Implemented methods for batch operations:
  - `execute_many()` - For executing a query with multiple sets of parameters
  - `copy_records_to_table()` - For efficiently copying records to a table

##### Transaction Management
- Improved transaction usage for related operations:
  ```python
  async with self.bot.db.transaction():
      # Multiple database operations that should be atomic
      await self.bot.db.execute("...")
      await self.bot.db.execute("...")
  ```

#### Error Handling

##### Enhanced Error Classification
- Improved error handling with more granular error classification:
  ```python
  if isinstance(e, asyncpg.DeadlockDetectedError):
      # Handle deadlock errors
  elif isinstance(e, asyncpg.UniqueViolationError):
      # Handle unique constraint violations
  elif isinstance(e, asyncpg.ForeignKeyViolationError):
      # Handle foreign key violations
  ```

#### Usage Examples

##### Using Prepared Statements
```python
# Prepare a statement once
stmt = await db.prepare_statement("get_user", "SELECT * FROM users WHERE user_id = $1")

# Use it multiple times
user = await stmt.fetchrow(user_id)
```

##### Batch Operations
```python
# Batch insert multiple records
records = [(user.id, user.name, user.created_at) for user in users]
await db.execute_many(
    "INSERT INTO users(id, name, created_at) VALUES($1, $2, $3) ON CONFLICT DO NOTHING",
    records
)
```

##### Using Materialized Views
```python
# Refresh the views
await db.refresh_materialized_views()

# Query the materialized view
results = await db.fetch("SELECT * FROM daily_message_stats WHERE server_id = $1", server_id)
```

#### Initialization

The database optimizations are automatically applied when the bot starts up:

```python
# In main.py
async def setup_hook(self) -> None:
    # ...
    try:
        await self.db.execute_script("utils/db_optimizations.sql")
        logging.info("Database optimizations applied successfully")
    except Exception as e:
        logging.error(f"Failed to apply database optimizations: {e}")
```

## SQLAlchemy Model Updates

This section summarizes the updates made to the SQLAlchemy models to match the database schema defined in `cognita_db_tables.sql`.

### Overview

After examining the database schema in `cognita_db_tables.sql`, several discrepancies were identified between the SQLAlchemy models and the actual database schema. The following updates were made to align the models with the database schema:

### Updates by Model

#### GalleryMementos (`models/tables/gallery.py`)

- Changed `channel_id` and `guild_id` from `Integer` to `BigInteger` to match the `bigint` type in the database

#### CommandHistory (`models/tables/commands.py`)

- Changed `user_id`, `channel_id`, and `guild_id` from `Integer` to `BigInteger`
- Changed `args` from `Text` to `JSON`
- Changed `run_time` from `Integer` to `Interval`
- Added foreign key relationships to `users`, `channels`, and `servers` tables
- Added `nullable=False` to required columns
- Added table arguments for schema

#### CreatorLink (`models/tables/creator_links.py`)

- Renamed `id` to `serial_id` to match the database
- Changed primary key to a composite key of `user_id` and `title`
- Added foreign key relationship to `users` table
- Added missing columns: `last_changed` and `feature`
- Added `nullable=False` to required columns

#### JoinLeave (`models/tables/join_leave.py`)

- Changed `join_or_leave` from an Enum to a `String` column
- Added missing columns: `server_name` and `created_at`
- Removed default value for `date` to match the database

#### Message (`models/tables/messages.py`)

- Renamed `id` to `message_id` to match the database
- Renamed `username` to `user_name` to match the database
- Changed `content` from `Text` to `String`
- Added missing columns: `server_name`, `user_nick`, `jump_url`, `deleted`, and `reference`
- Added foreign key relationships to `servers` and `users` tables
- Added `nullable=False` to required columns

#### Reaction (`models/tables/reactions.py`)

- Removed `emoji` column and added separate columns for different types of emojis:
  - `unicode_emoji`
  - `emoji_name`
  - `animated`
  - `emoji_id`
  - `url`
  - `is_custom_emoji`
- Added missing `removed` column
- Removed default value for `date`
- Added unique constraints for combinations of `message_id`, `user_id`, and emoji identifiers

### Next Steps

These updates ensure that the SQLAlchemy models accurately reflect the database schema. However, there are still many tables in the database that haven't been modeled yet. As the SQLAlchemy implementation follows a gradual migration approach, additional models can be created as needed.

When creating new models or updating existing ones, it's important to:

1. Check the database schema in `cognita_db_tables.sql` to ensure the model matches the table definition
2. Include all columns with the correct types
3. Add foreign key relationships where appropriate
4. Add indexes and constraints as defined in the database

### Testing

After making these updates, it's important to test the models to ensure they work correctly with the existing codebase. This can be done by:

1. Running the bot and checking for any errors related to the SQLAlchemy models
2. Testing specific functionality that uses the updated models
3. Verifying that database operations (queries, inserts, updates, deletes) work as expected
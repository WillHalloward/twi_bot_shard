# Database Access Standardization Plan

## Overview

This document outlines the plan for standardizing database access patterns in the Twi Bot Shard project. According to the improvement plan, SQLAlchemy ORM has been chosen as the primary database access method.

## Current State

The project currently uses multiple database access methods:

1. **Raw SQL with asyncpg** (`bot.db`):
   ```python
   await self.bot.db.fetch("SELECT * FROM gallery_mementos")
   ```

2. **SQLAlchemy ORM** (`bot.get_db_session()`):
   ```python
   async with self.bot.get_db_session() as session:
       stmt = select(GalleryMementos)
       result = await session.execute(stmt)
       items = result.scalars().all()
   ```

3. **DatabaseService** for model-specific operations:
   ```python
   self.gallery_service = DatabaseService(GalleryMementos)
   # Later usage:
   await self.gallery_service.get_all(session)
   ```

## Migration Plan

### Phase 1: Preparation (1-2 weeks)

1. **Complete SQLAlchemy Models**:
   - Ensure all database tables have corresponding SQLAlchemy models
   - Add relationships between models where appropriate
   - Add indexes for frequently queried fields

2. **Enhance DatabaseService**:
   - Add additional methods for common query patterns
   - Implement pagination support
   - Add transaction support

3. **Create Repository Classes**:
   - Create repository classes for each entity that extend DatabaseService
   - Add domain-specific query methods to repository classes

### Phase 2: Migration (2-4 weeks)

1. **Identify Raw SQL Usage**:
   - Use code search to identify all instances of raw SQL
   - Categorize queries by complexity and frequency

2. **Migrate Simple Queries First**:
   - Replace simple SELECT, INSERT, UPDATE, DELETE queries with SQLAlchemy equivalents
   - Use DatabaseService where possible

3. **Migrate Complex Queries**:
   - Create custom methods in repository classes for complex queries
   - Use SQLAlchemy's expression language for advanced queries

4. **Update Cogs**:
   - Inject repository classes into cogs instead of using `bot.db` directly
   - Update command handlers to use repository methods

### Phase 3: Cleanup and Optimization (1-2 weeks)

1. **Remove Deprecated Code**:
   - Remove fallback to raw SQL once migration is complete
   - Update error handling for SQLAlchemy-specific exceptions

2. **Optimize Performance**:
   - Add query result caching for frequently accessed data
   - Implement eager loading for related entities
   - Add database query monitoring

3. **Update Documentation**:
   - Update code comments and docstrings
   - Create examples for common database operations

## Best Practices for Database Access

### General Guidelines

1. **Use Repository Pattern**:
   - Create repository classes for each entity
   - Inject repositories into cogs instead of using database directly
   - Keep database access code separate from business logic

2. **Use Transactions**:
   - Use transactions for multiple related operations
   - Ensure proper error handling within transactions

3. **Handle Errors Properly**:
   - Use try-except blocks for database operations
   - Log database errors with context information
   - Return appropriate error messages to users

### SQLAlchemy Specific Guidelines

1. **Model Definition**:
   - Use declarative models with type annotations
   - Define relationships between models
   - Add indexes for frequently queried fields

2. **Query Building**:
   - Use SQLAlchemy's expression language for complex queries
   - Use select() instead of deprecated query() method
   - Use joins for related data instead of multiple queries

3. **Session Management**:
   - Use async context managers for session management
   - Close sessions after use
   - Don't keep sessions open across multiple operations

### Example Patterns

#### Repository Pattern

```python
# Define repository
class GalleryRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.service = DatabaseService(GalleryMementos)
    
    async def get_by_guild(self, guild_id: int):
        async with self.session_factory() as session:
            return await self.service.get_by_field(session, "guild_id", guild_id)
    
    async def add_channel(self, channel_name: str, channel_id: int, guild_id: int):
        async with self.session_factory() as session:
            return await self.service.create(
                session,
                channel_name=channel_name,
                channel_id=channel_id,
                guild_id=guild_id
            )

# Use in cog
class GalleryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gallery_repo = GalleryRepository(bot.get_db_session)
    
    async def cog_load(self):
        self.repost_cache = await self.gallery_repo.get_all()
```

#### Transaction Example

```python
async def transfer_points(self, from_user_id: int, to_user_id: int, amount: int):
    async with self.session_factory() as session:
        async with session.begin():
            # Both operations succeed or fail together
            await self.update_points(session, from_user_id, -amount)
            await self.update_points(session, to_user_id, amount)
```

#### Error Handling

```python
async def get_user_data(self, user_id: int):
    try:
        async with self.session_factory() as session:
            result = await self.service.get_by_id(session, user_id)
            if not result:
                return None
            return result
    except SQLAlchemyError as e:
        self.logger.error(f"Database error when getting user {user_id}: {str(e)}")
        raise DatabaseOperationError(f"Could not retrieve user data: {str(e)}")
```

## Migration Examples

### Before (Raw SQL):

```python
async def get_gallery_channels(self, guild_id: int):
    return await self.bot.db.fetch(
        "SELECT * FROM gallery_mementos WHERE guild_id = $1",
        guild_id
    )
```

### After (SQLAlchemy):

```python
async def get_gallery_channels(self, guild_id: int):
    async with self.bot.get_db_session() as session:
        stmt = select(GalleryMementos).where(GalleryMementos.guild_id == guild_id)
        result = await session.execute(stmt)
        return result.scalars().all()
```

### After (Repository Pattern):

```python
async def get_gallery_channels(self, guild_id: int):
    return await self.gallery_repo.get_by_guild(guild_id)
```

## Conclusion

By following this migration plan and adhering to the best practices outlined in this document, we will standardize database access patterns across the Twi Bot Shard project, making the codebase more maintainable, testable, and performant.
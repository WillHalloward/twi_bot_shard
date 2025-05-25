# Database Access Best Practices

This document provides guidelines and best practices for database access in the Twi Bot Shard project. SQLAlchemy ORM has been chosen as the primary database access method.

## General Guidelines

### 1. Use Repository Pattern

- Create repository classes for each entity that extend `DatabaseService`
- Inject repositories into cogs instead of using database directly
- Keep database access code separate from business logic

```python
# Define repository
class GalleryRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.service = DatabaseService(GalleryMementos)
    
    async def get_by_guild(self, guild_id: int):
        async with self.session_factory() as session:
            return await self.service.get_by_field(session, "guild_id", guild_id)

# Use in cog
class GalleryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gallery_repo = GalleryRepository(bot.get_db_session)
```

### 2. Use Transactions for Multiple Operations

- Wrap related operations in transactions to ensure atomicity
- Use `session.begin()` context manager for automatic commit/rollback

```python
async def transfer_points(self, from_user_id: int, to_user_id: int, amount: int):
    async with self.session_factory() as session:
        async with session.begin():
            # Both operations succeed or fail together
            await self.update_points(session, from_user_id, -amount)
            await self.update_points(session, to_user_id, amount)
```

### 3. Handle Errors Properly

- Use try-except blocks for database operations
- Log database errors with context information
- Return appropriate error messages to users

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

## SQLAlchemy Specific Guidelines

### 1. Model Definition

- Use declarative models with type annotations
- Define relationships between models
- Add indexes for frequently queried fields

```python
class GalleryMementos(Base):
    """Model for gallery_mementos table."""
    __tablename__ = "gallery_mementos"

    channel_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    
    # Define relationship if applicable
    guild: Mapped["Guild"] = relationship("Guild", back_populates="gallery_channels")
```

### 2. Query Building

- Use SQLAlchemy's expression language for complex queries
- Use `select()` instead of deprecated `query()` method
- Use joins for related data instead of multiple queries

```python
# Simple query
stmt = select(GalleryMementos).where(GalleryMementos.guild_id == guild_id)

# Query with join
stmt = (
    select(GalleryMementos, Guild.name)
    .join(Guild, GalleryMementos.guild_id == Guild.id)
    .where(GalleryMementos.channel_id == channel_id)
)

# Query with ordering
stmt = (
    select(GalleryMementos)
    .where(GalleryMementos.guild_id == guild_id)
    .order_by(GalleryMementos.channel_name)
)
```

### 3. Session Management

- Use async context managers for session management
- Close sessions after use
- Don't keep sessions open across multiple operations

```python
# Good practice
async def get_data(self):
    async with self.session_factory() as session:
        result = await session.execute(select(Model))
        return result.scalars().all()

# Avoid this pattern
async def bad_practice(self):
    session = self.session_factory()
    try:
        result = await session.execute(select(Model))
        return result.scalars().all()
    finally:
        await session.close()
```

### 4. Bulk Operations

- Use bulk operations for inserting/updating multiple records
- Use `execute_many` for better performance

```python
# Insert multiple records
async def add_many_items(self, items):
    async with self.session_factory() as session:
        session.add_all([Model(**item) for item in items])
        await session.commit()
```

### 5. Pagination

- Implement pagination for queries that return large result sets
- Use limit and offset or keyset pagination

```python
async def get_paginated(self, page=1, page_size=20):
    async with self.session_factory() as session:
        stmt = (
            select(Model)
            .order_by(Model.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await session.execute(stmt)
        return result.scalars().all()
```

## Performance Considerations

### 1. Use Eager Loading for Related Data

- Use `selectinload()` or `joinedload()` to load related data in a single query
- Avoid N+1 query problems

```python
stmt = (
    select(GalleryMementos)
    .options(selectinload(GalleryMementos.guild))
    .where(GalleryMementos.channel_id == channel_id)
)
```

### 2. Use Caching for Frequently Accessed Data

- Implement caching for data that doesn't change frequently
- Use in-memory cache or Redis for distributed caching

```python
async def get_gallery_channels(self, guild_id: int):
    # Check cache first
    cache_key = f"gallery_channels:{guild_id}"
    cached = self.cache.get(cache_key)
    if cached:
        return cached
    
    # If not in cache, query database
    async with self.session_factory() as session:
        stmt = select(GalleryMementos).where(GalleryMementos.guild_id == guild_id)
        result = await session.execute(stmt)
        channels = result.scalars().all()
        
        # Store in cache
        self.cache.set(cache_key, channels, ttl=3600)  # 1 hour TTL
        return channels
```

### 3. Use Database Indexes

- Add indexes for columns used in WHERE clauses
- Add composite indexes for columns used together
- Be careful not to over-index (indexes slow down writes)

```python
class Messages(Base):
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    author_id: Mapped[int] = mapped_column(BigInteger, index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    
    # Composite index for queries that filter by both channel and author
    __table_args__ = (
        Index('idx_channel_author', 'channel_id', 'author_id'),
    )
```

## Migration from Raw SQL

When migrating from raw SQL to SQLAlchemy, follow these patterns:

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

Following these best practices will ensure consistent, maintainable, and performant database access across the Twi Bot Shard project. For more detailed information, refer to the [Database Migration Plan](database_migration_plan.md) and the [SQLAlchemy documentation](https://docs.sqlalchemy.org/en/20/).
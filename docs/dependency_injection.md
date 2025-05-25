# Dependency Injection Pattern

## Overview

This document explains the dependency injection pattern implemented in the Twi Bot Shard project. Dependency injection is a design pattern that allows for loose coupling between components, making the code more maintainable, testable, and flexible.

## Components

The dependency injection system in Twi Bot Shard consists of the following components:

1. **Service Container**: A central registry for all services and dependencies
2. **Repository Factory**: A factory for creating repository instances for database access
3. **Generic Repository**: A base repository implementation for common database operations
4. **Cogs with Injected Dependencies**: Components that receive their dependencies through constructor injection

## Service Container

The service container (`utils/service_container.py`) is responsible for managing all services and dependencies in the application. It provides methods for registering and retrieving services.

### Key Features

- **Service Registration**: Register services as instances, factories, or classes
- **Singleton Support**: Optionally register services as singletons
- **Type Safety**: Get services with type checking

### Usage Examples

```python
# Register a service instance
container.register("db", database)

# Register a factory function
container.register_factory("db_session", get_db_session)

# Register a class (will be instantiated when requested)
container.register_class("logger", Logger, singleton=True)

# Get a service
db = container.get("db")

# Get a service with type checking
session = container.get_typed("db_session", AsyncSession)
```

## Repository Factory

The repository factory (`utils/repository_factory.py`) is responsible for creating repository instances for database access. It uses the service container to manage repository dependencies.

### Key Features

- **Repository Registration**: Register custom repository classes for specific models
- **Generic Repository Fallback**: Automatically create generic repositories for models without custom repositories
- **Singleton Repositories**: Repositories are registered as singletons in the service container

### Usage Examples

```python
# Register a custom repository
repo_factory.register_repository(User, UserRepository)

# Get a repository (will create a generic one if none is registered)
user_repo = repo_factory.get_repository(User)
```

## Generic Repository

The generic repository (`utils/repository_factory.py`) provides a base implementation for common database operations. It uses the `DatabaseService` class for actual database access.

### Key Features

- **CRUD Operations**: Methods for create, read, update, and delete operations
- **Session Management**: Automatically manages database sessions
- **Model Agnostic**: Works with any SQLAlchemy model

### Usage Examples

```python
# Get a generic repository
user_repo = repo_factory.get_repository(User)

# Use the repository
users = await user_repo.get_all()
user = await user_repo.get_by_id(1)
await user_repo.create(name="John", email="john@example.com")
await user_repo.update(1, name="Jane")
await user_repo.delete(1)
```

## Cogs with Injected Dependencies

Cogs receive their dependencies through constructor injection. This makes them more testable and loosely coupled.

### Example

```python
class GalleryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Get repositories from the repository factory
        self.gallery_repo = bot.repo_factory.get_repository(GalleryMementos)
        self.creator_links_repo = bot.repo_factory.get_repository(CreatorLink)
    
    async def cog_load(self):
        # Use repository to load data
        self.repost_cache = await self.gallery_repo.get_all()
```

## Best Practices

### 1. Use Constructor Injection

Inject dependencies through the constructor rather than creating them inside the class:

```python
# Good
def __init__(self, bot):
    self.bot = bot
    self.repo = bot.repo_factory.get_repository(Model)

# Avoid
def __init__(self, bot):
    self.bot = bot
    self.repo = DatabaseService(Model)
```

### 2. Register Services in the Container

Register all services in the service container to make them available for injection:

```python
# In bot initialization
container.register("config", config)
container.register("web_client", web_client)
```

### 3. Create Custom Repositories for Complex Logic

For models with complex business logic, create custom repository classes:

```python
class UserRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.service = DatabaseService(User)
    
    async def get_by_username(self, username):
        async with self.session_factory() as session:
            return await self.service.get_by_field(session, "username", username)
    
    async def get_active_users(self):
        async with self.session_factory() as session:
            stmt = select(User).where(User.is_active == True)
            result = await session.execute(stmt)
            return result.scalars().all()
```

### 4. Use Typed Service Retrieval

When getting services from the container, use typed retrieval for better type safety:

```python
# Good
session = container.get_typed("db_session", AsyncSession)

# Avoid
session = container.get("db_session")
```

## Migration Guide

### Migrating Existing Cogs

To migrate an existing cog to use dependency injection:

1. Update the constructor to get repositories from the repository factory:

```python
def __init__(self, bot):
    self.bot = bot
    self.repo = bot.repo_factory.get_repository(Model)
```

2. Replace direct database access with repository methods:

```python
# Before
async with self.bot.get_db_session() as session:
    stmt = select(Model).where(Model.id == id)
    result = await session.execute(stmt)
    item = result.scalars().first()

# After
item = await self.repo.get_by_id(id)
```

3. Replace raw SQL with repository methods:

```python
# Before
items = await self.bot.db.fetch("SELECT * FROM table WHERE field = $1", value)

# After
items = await self.repo.get_by_field("field", value)
```

## Conclusion

By following the dependency injection pattern, the Twi Bot Shard project achieves:

1. **Loose Coupling**: Components depend on abstractions, not concrete implementations
2. **Testability**: Dependencies can be easily mocked for testing
3. **Flexibility**: Implementations can be changed without modifying dependent components
4. **Maintainability**: Code is more modular and easier to understand

For more information on the repository pattern and database access, see [Database Best Practices](database_best_practices.md).
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Twi Bot Shard (Cognita) is a Discord bot for "The Wandering Inn" community, built with discord.py and PostgreSQL. The bot uses a modular cog architecture with SQLAlchemy ORM, dependency injection via a service container, and the repository pattern for database access.

## Common Development Commands

### Running the bot
```bash
python main.py
```

### Linting and formatting
```bash
# Run linter (ruff) to check code style
python lint.py
# Or: python scripts/development/lint.py

# Format code using Black
python format.py
# Or: python scripts/development/format.py

# Run both ruff and black directly
ruff check .
ruff format .
black .
```

### Testing
```bash
# Run all tests using pytest
pytest tests/
# Or with verbose output: pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=xml

# Run specific test categories
python tests/test_dependencies.py       # Verify dependencies
python tests/test_db_connection.py      # Test database connection
python tests/test_sqlalchemy_models.py  # Test ORM models
python tests/test_cogs.py               # Test all cog loading
python tests/test_chaos_engineering.py  # Test resilience
```

### Type checking
```bash
mypy .
```

### Dependency management (using uv)
```bash
# Install dependencies
uv pip install -e .

# Add new dependency
uv pip install <package>
# Then update requirements.txt manually
```

### Database Operations
```bash
# Apply base database optimizations
psql -U username -d database -f database/optimizations/base.sql

# Run optimization scripts
python scripts/database/apply_optimizations.py
python scripts/database/apply_additional.py
```

### Schema Operations
```bash
# Build FAISS index for schema search
python scripts/schema/build_faiss_index.py

# Query schema with natural language
python scripts/schema/query_faiss_schema.py
```

### Git Hooks
```bash
# Setup pre-commit hooks
python scripts/development/setup_hooks.py
```

## Architecture

### Core Components

1. **main.py**: Bot entry point and lifecycle management
   - `Cognita` class extends `commands.Bot` with dependency injection
   - Manages cog loading (critical vs lazy-loaded)
   - Sets up database connections with SSL and connection pooling
   - Implements startup performance tracking and resource monitoring
   - Handles command history tracking in database

2. **Cog System**: Modular feature organization in `cogs/`
   - All cogs inherit from `BaseCog` in `utils/base_cog.py`
   - Cogs access repositories via `self.repo_factory.get_repository(ModelClass)`
   - Critical cogs loaded at startup; non-critical cogs loaded lazily
   - Critical cogs: `stats` (event tracking), `mods` (moderation), `gallery` (content management)
   - Stats functionality is split into modular components (commands, listeners, queries, tasks, utils)

3. **Service Container** (`utils/service_container.py`)
   - Centralized dependency injection
   - Services registered: bot, db, http_client, resource_monitor
   - Factory pattern for database sessions
   - Access via `bot.container.get("service_name")`

4. **Repository Pattern** (`utils/repository.py`)
   - Base repository provides CRUD operations
   - Specialized repositories in `utils/repositories/`
   - Access via `bot.repo_factory.get_repository(ModelClass)`
   - Encapsulates database logic and enforces business rules

5. **Database Layer**: Three-tier database access
   - **Raw SQL**: Direct asyncpg queries via `utils.db.Database`
   - **SQLAlchemy ORM**: Models in `models/tables/` with async session management
   - **Repository Pattern**: Abstraction layer in `utils/repositories/` for common operations
   - Transaction support via `async with await bot.db.transaction():`

### Error Handling Architecture

The bot implements a comprehensive error handling strategy:

- **Custom Exception Hierarchy** (`utils/exceptions.py`): Specific exception types for different error categories (UserInputError, DatabaseError, ExternalServiceError, etc.)
- **Decorators**: `@handle_command_errors` for regular commands, `@handle_interaction_errors` for slash commands
- **Global Handlers**: Set up via `setup_global_exception_handler()` in main.py
- **Error Telemetry**: Tracks error patterns in database for proactive resolution

### Key Design Patterns

1. **Repository Pattern**: Database access abstraction with CRUD operations, bulk operations, error handling and retries, timezone-naive datetime handling (all times stored as UTC)
2. **Dependency Injection**: Service container for loose coupling
3. **Lazy Loading**: Non-critical cogs loaded on-demand in development
4. **Command Pattern**: Discord.py's built-in command system
5. **Async Context Managers**: Used for database transactions, HTTP sessions, resource cleanup
6. **Type Safety**: Modern Python type hints using `|` union operator, type aliases, SQLAlchemy 2.0-style queries

## Important Implementation Notes

### Adding New Features

1. **New Cog Creation**:
   - Inherit from `BaseCog` in `utils/base_cog.py`
   - Include `async def setup(bot)` function at module level (required for cog loading)
   - Use `self.logger` for structured logging
   - Access repositories via `self.get_repository(ModelClass)`
   - Use `@commands.Cog.listener()` decorator for event handlers
   - Use `@commands.command()` for prefix commands or `@app_commands.command()` for slash commands
   - Follow patterns in `cogs/example_cog.py`
   - Add cog to the `cogs` list in main.py (line ~918)
   - Add to `critical_cogs` only if required at startup

2. **New Database Model**:
   - Create model in `models/tables/` inheriting from `Base`
   - Use modern type hints: `Mapped[str]`, `Mapped[int | None]`
   - Create repository in `utils/repositories/` if custom queries needed
   - Register repository in `utils/repositories/__init__.py`
   - Run migrations or update schema in database

3. **Database Operations**:
   - Always use parameterized queries to prevent SQL injection
   - Use transactions for multiple related operations
   - Prefer repositories over raw queries for model operations
   - Use `bot.db` for complex queries or bulk operations
   - Connection pooling is automatic; don't create new connections

### Database Timestamps

All datetime values must be stored as timezone-naive UTC:
```python
# Correct
timestamp = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

# Incorrect
timestamp = datetime.datetime.now()  # Uses local timezone
```

### Bulk Operations

When inserting multiple records, always use bulk operations:
```python
# Use repository bulk_create instead of individual inserts
await repository.bulk_create(entities)
```

### Error Recovery

The bot implements automatic recovery for:
- Database connection failures (with exponential backoff)
- External API failures (with circuit breakers)
- Discord API rate limits

### Code Style Requirements

- **Python 3.12** features: Use `|` for unions, `match/case`, modern type hints
- **Type Hints**: Required for all functions (configured in pyproject.toml)
- **Async/Await**: All Discord and database operations must be async
- **Docstrings**: Google-style docstrings for all public functions/classes
- **Formatting**: Black (line length 88) and Ruff configured in pyproject.toml

### Testing Practices

- Property-based testing with Hypothesis for validation functions
- Mock factories with Faker for realistic test data (tests/mock_factories.py)
- Use pytest fixtures from tests/conftest.py
- Chaos engineering tests for resilience (tests/test_chaos_engineering.py)
- Integration tests verify database interactions work correctly
- All async tests use `@pytest.mark.asyncio` decorator
- Always run tests before committing

### Resource Management

- **HTTP Client**: Shared `HTTPClient` instance with connection pooling
- **Database Connections**: Pooled connections (min 5, max 20)
- **Resource Monitoring**: Automatic via `ResourceMonitor` with thresholds
- **Periodic Cleanup**: Background task runs every 30 minutes
- **Startup Optimization**: Parallel initialization of independent services

### Configuration

- Environment variables loaded from `.env` file
- Configuration in `config.py` with proper types
- Supports different environments: PRODUCTION, DEVELOPMENT, TESTING
- SSL certificates required for database connection (ssl-cert/)
- Secret management via `SecretManager` with encryption

### Statistics System

The stats module is split into specialized components:
- `stats_commands.py`: Owner commands for data management
- `stats_listeners.py`: Real-time event listeners for message tracking
- `stats_queries.py`: User-facing query commands
- `stats_tasks.py`: Background tasks for reporting
- `stats_utils.py`: Shared utility functions
- Stats listeners are unsubscribed in main.py to prevent duplicate handling

### Performance Considerations

- Startup times tracked per component for optimization analysis
- Lazy loading of non-critical cogs in development/testing
- Connection pooling for database and HTTP
- Query caching for frequently accessed data
- Materialized views for complex statistics
- Batch operations for bulk data processing

### Security Notes

- Never commit `.env` file or SSL certificates
- Use `SecretManager` for sensitive credentials
- All database queries use parameterized statements
- Error messages sanitized before showing to users
- Permission system enforces role-based access control
- Setup git hooks via `setup_hooks.py` for pre-commit checks

## Database Schema

The bot uses PostgreSQL with optimized schemas including:
- Composite indexes for common query patterns
- Partial indexes for filtered queries
- Materialized views for statistics
- Full-text search indexes
- Proper foreign key constraints

Key tables:
- `messages`: Discord message tracking
- `users`, `servers`, `channels`: Discord entity tracking
- `gallery_mementos`: Gallery content management
- `creator_links`: Creator link management
- `command_history`: Command usage tracking

## External Service Integrations

The bot integrates with:
- Discord API (via discord.py)
- Google Custom Search API
- Twitter/X API
- DeviantArt
- AO3 (Archive of Our Own)
- OpenAI API for summarization

All external calls use the shared HTTP client with proper timeout handling.

## Discord.py Specific Patterns

### Cog Structure with Setup Function

```python
from discord.ext import commands
from utils.base_cog import BaseCog

class MyCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        # Additional initialization

    @commands.Cog.listener()
    async def on_message(self, message):
        # Event listener
        pass

async def setup(bot):
    """Required entry point for cog loading."""
    await bot.add_cog(MyCog(bot))
```

### Command Types - Prefix vs Slash

```python
# Prefix command (traditional): !commandname
@commands.command()
async def my_command(self, ctx):
    await ctx.send("Response")

# Slash command (application command): /commandname
@app_commands.command()
async def my_slash(self, interaction: discord.Interaction):
    await interaction.response.send_message("Response")
```

### Context vs Interaction

- **Context** (`ctx`): Used with prefix commands, has `.send()`, `.author`, `.guild`
- **Interaction** (`interaction`): Used with slash commands, requires `.response.send_message()` or `.followup.send()`
- Interactions must respond within 3 seconds or be deferred with `await interaction.response.defer()`

### Event Listeners in Cogs

```python
@commands.Cog.listener()
async def on_member_join(self, member):
    # Handle member join event
    self.logger.info("member_joined", member_id=member.id)
```

### UI Components (Views, Modals, Buttons)

```python
class MyView(discord.ui.View):
    @discord.ui.button(label="Click Me", style=discord.ButtonStyle.primary)
    async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Button clicked!")

class MyModal(discord.ui.Modal, title="Input Form"):
    name = discord.ui.TextInput(label="Name", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Hello {self.name.value}!")
```

### Intents Configuration

The bot requires `message_content` intent (configured in main.py line 963-965):
```python
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
```

### Command Converters and Type Hints

Discord.py automatically converts arguments based on type hints:
```python
# Automatic conversion to Discord objects
@commands.command()
async def ban(self, ctx, member: discord.Member, reason: str = "No reason"):
    await member.ban(reason=reason)

# Supports: Member, User, TextChannel, Role, Guild, Message, etc.
# Union types allow multiple options: discord.Member | discord.User
```

## Common Patterns

### Accessing Database via Repository

```python
class MyCog(BaseCog):
    async def some_command(self, ctx):
        repo = self.get_repository(GalleryMementos)
        items = await repo.find_by(guild_id=ctx.guild.id)
```

### Using Database Transactions

```python
async with await self.bot.db.transaction():
    await self.bot.db.execute("INSERT INTO ...")
    await self.bot.db.execute("UPDATE ...")
```

### Structured Logging

```python
self.logger.info("event_name", user_id=user.id, guild_id=guild.id)
```

### Error Handling

```python
from utils.exceptions import ValidationError
from utils.error_handling import handle_command_errors

@commands.command()
@handle_command_errors
async def my_command(self, ctx, arg: str):
    if not validate(arg):
        raise ValidationError(field="arg", message="Invalid argument")
```

## Critical Files

- `main.py`: Bot initialization and lifecycle (lines 64-826)
- `config/__init__.py`: Environment configuration with Pydantic validation
- `utils/base_cog.py`: Base class for all cogs
- `utils/repository.py`: Base repository implementation
- `utils/error_handling.py`: Global error handling setup
- `utils/service_container.py`: Dependency injection
- `models/base.py`: SQLAlchemy base configuration
- `pyproject.toml`: Dependencies and tool configuration

## Directory Structure

```
twi_bot_shard/
├── cogs/                       # Bot cogs (features)
├── config/                     # Configuration module
├── database/                   # Database files
│   ├── schema/                 # SQL schema definitions
│   ├── optimizations/          # Performance SQL
│   └── utilities/              # Utility SQL scripts
├── docs/                       # Documentation
│   ├── user/                   # User-facing docs
│   ├── developer/              # Developer docs
│   │   ├── setup/              # Setup guides
│   │   ├── architecture/       # Architecture docs
│   │   ├── guides/             # How-to guides
│   │   ├── reference/          # Reference docs
│   │   └── advanced/           # Advanced topics
│   ├── operations/             # Operations/deployment
│   ├── meta/                   # Meta documentation
│   └── project/                # Project management
├── models/                     # SQLAlchemy models
├── scripts/                    # Utility scripts
│   ├── database/               # DB scripts
│   ├── schema/                 # Schema scripts
│   └── development/            # Dev tools
├── tests/                      # Test suite
└── utils/                      # Utilities and helpers
```

## Documentation Navigation

- **For Users**: See `docs/user/` for commands and features
- **For Developers**: See `docs/developer/getting-started.md` to begin
- **For Operations**: See `docs/operations/` for deployment
- **For Contributors**: See `docs/meta/contributing.md`

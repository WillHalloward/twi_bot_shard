# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Twi Bot Shard (Cognita) is a Discord bot built for "The Wandering Inn" server using discord.py and PostgreSQL. The bot follows a modular Cog-based architecture with comprehensive database integration, error handling, and service patterns.

## Common Development Commands

### Running the bot
```bash
python main.py
```

### Linting and formatting
```bash
# Run linter (ruff) to check code style
python lint.py

# Format code using Black
python format.py

# Run both ruff and black directly
ruff check .
ruff format .
black .
```

### Testing
```bash
# Run all tests using pytest
pytest tests/

# Run with coverage
pytest tests/ --cov=. --cov-report=xml

# Run specific test categories
python tests/test_dependencies.py     # Verify dependencies
python tests/test_db_connection.py    # Test database connection
python tests/test_cogs.py             # Test all cog loading
python tests/test_chaos_engineering.py # Test resilience
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

## High-Level Architecture

### Core Components

1. **Bot Core (main.py)**: The Cognita class extends discord.ext.commands.Bot with:
   - Database connection pooling (asyncpg)
   - SQLAlchemy ORM session management
   - Service container for dependency injection
   - Repository factory pattern for database operations
   - HTTP client with connection pooling
   - Resource monitoring and error telemetry

2. **Cog System**: Modular feature implementation in `cogs/`:
   - Each cog is a self-contained module handling specific bot features
   - Cogs inherit from `utils.base_cog.BaseCog` which provides common functionality
   - Critical cogs: `stats` (event tracking), `mods` (moderation), `gallery` (content management)

3. **Database Layer**: Three-tier database access:
   - **Raw SQL**: Direct asyncpg queries via `utils.db.Database`
   - **SQLAlchemy ORM**: Models in `models/tables/` with async session management
   - **Repository Pattern**: Abstraction layer in `utils/repositories/` for common operations

4. **Service Architecture**:
   - **ServiceContainer**: Central dependency injection container
   - **RepositoryFactory**: Creates repositories with proper session management
   - **DatabaseService**: Transaction management and connection pooling
   - All services are initialized at bot startup and accessible via `bot.container`

### Key Design Patterns

1. **Repository Pattern**: All database operations go through repositories which handle:
   - CRUD operations with proper transaction management
   - Bulk operations for performance
   - Error handling and retries
   - Timezone-naive datetime handling (all times stored as UTC)

2. **Error Handling**:
   - Global exception handlers for both regular and application commands
   - Error telemetry system tracking errors to database
   - Standardized error decorators (`@handle_db_errors`, `@handle_command_errors`)
   - User-friendly error messages with graceful degradation

3. **Async Context Managers**: Used extensively for:
   - Database transactions (`DatabaseTransaction`)
   - HTTP sessions
   - Resource cleanup

4. **Type Safety**:
   - Modern Python type hints using `|` union operator
   - Type aliases for complex types
   - SQLAlchemy 2.0-style queries

## Important Implementation Notes

1. **Database Timestamps**: All datetime values must be stored as timezone-naive UTC
   ```python
   # Correct
   timestamp = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
   
   # Incorrect
   timestamp = datetime.datetime.now()  # Uses local timezone
   ```

2. **Bulk Operations**: When inserting multiple records, always use bulk operations:
   ```python
   # Use repository bulk_create instead of individual inserts
   await repository.bulk_create(entities)
   ```

3. **Error Recovery**: The bot implements automatic recovery for:
   - Database connection failures (with exponential backoff)
   - External API failures (with circuit breakers)
   - Discord API rate limits

4. **Testing**: Always run tests before committing:
   - Unit tests for individual functions
   - Integration tests for cog commands
   - Chaos engineering tests for resilience

5. **Cog Development**: When creating new cogs:
   - Inherit from `BaseCog`
   - Use `@commands.command()` for text commands
   - Use `@app_commands.command()` for slash commands
   - Implement proper error handling
   - Add to `initial_extensions` in main.py

6. **Environment Variables**: Required in `.env`:
   - `BOT_TOKEN`: Discord bot token
   - `DATABASE`, `DB_USER`, `DB_PASSWORD`, `HOST`: PostgreSQL connection
   - SSL certificates in `ssl-cert/` for secure database connections

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
# Twi Bot Shard (Cognita)

A Discord bot designed for "The Wandering Inn" server. The bot works via Discord.py and PostgreSQL.

## Overview

Cognita is a feature-rich Discord bot that provides various utilities for "The Wandering Inn" community, including:

- Image gallery management
- Link and tag management
- Patreon poll integration
- Wiki search functionality
- Moderation tools
- Statistics tracking
- Creator links management
- Reporting functionality
- Innktober event features
- Text summarization

## Quick Start

For a quick overview of the installation process:

1. Clone the repository:
```bash
git clone https://github.com/WillHalloward/twi_bot_shard.git
cd twi_bot_shard
```

2. Install uv (if not already installed):
```bash
# Using pip
pip install uv

# Or using the official installer script (for Unix-based systems)
curl -sSf https://astral.sh/uv/install.sh | sh

# Or using the official installer script (for Windows PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

3. Install dependencies using uv:
```bash
uv pip install -e .
```

4. Verify dependencies installation:
```bash
uv run test_dependencies.py
```

5. Set up PostgreSQL database

6. Configure the `.env` file with your credentials

7. Run the bot:
```bash
python main.py
```

For detailed setup instructions, see the [Getting Started Guide](docs/developer/getting-started.md).

## Requirements

- Python 3.12.9
- PostgreSQL database
- Discord Bot Token
- Various API keys (see [Environment Variables](docs/developer/environment-variables.md))
- uv package manager

## Environment Variables

The bot uses environment variables for configuration. These can be set in a `.env` file in the project root. Key variables include:

- `BOT_TOKEN`: Discord bot token
- `DATABASE`, `DB_USER`, `DB_PASSWORD`, `HOST`: Database connection details
- `KILL_AFTER`: Time in seconds after which the bot will automatically exit (set to 0 to disable this feature)

## Features

### Gallery & Mementos
- **Repost Context Menu**: Right-click on any message to repost it to a designated channel
- **Content Support**: Handles images, text, AO3 links, Twitter links, Instagram links, and Discord files
- **Channel Configuration**: Use `/set_repost` to configure destination channels

### Links
- `/link get`: Retrieves and posts a link with the given name
- `/link add`: Adds a link with the given name to the given URL and tag
- `/link delete`: Deletes a link with the given name
- `/link list`: View all links
- `/tag`: View all links that have a certain tag

### Moderation
- `/mod reset`: Resets the cooldown of a command

### Utility
- `/avatar`: Posts the full version of an avatar
- `/info user`: Gives the account information of a user
- `/ping`: Gives the latency of the bot
- `/say`: Makes Cognita repeat whatever was said (Owner only)

### Poll
- `/findpoll`: Searches poll questions for a given query
- `/getpoll`: Fetches the latest poll from Patreon
- `/poll`: Posts the latest poll or a specific poll

### The Wandering Inn
- `/coloredtext`: List of all the different colored texts in TWI
- `/connectdiscord`: Information for Patreons on how to connect their Patreon account
- `/invistext`: Gives a list of all the invisible text in TWI
- `/password`: Information for Patreons on how to get the chapter password
- `/wiki`: Searches The Wandering Inn wiki for a matching article

## Project Structure

- `main.py`: Entry point for the bot
- `cogs/`: Directory containing modular components of the bot
- `emblems/`: Directory containing image assets
- `ssl-cert/`: SSL certificates for database connection
- `config.py`: Configuration file that loads settings from environment variables
- `pyproject.toml`: Project configuration and dependencies for uv
- `.uvrc`: uv-specific configuration file
- `.env`: Environment variables with sensitive information (not tracked in git)
- `requirements.txt`: Project dependencies

## Contributing

If you'd like to contribute to the project, please see the [Contributing Guide](docs/contributing.md).

## Database Optimizations

The bot includes several database optimizations to improve performance, reliability, and efficiency:

### Schema Optimizations
- Primary key constraints for data integrity
- Foreign key constraints for referential integrity
- Composite indexes for common query patterns
- Partial indexes for specific query patterns
- Full-text search indexes for text search

### Performance Optimizations
- Materialized views for complex statistics
- Batch operations for efficient data processing
- Prepared statements for frequent queries
- Optimized autovacuum settings for large tables

### Applying the Optimizations

To apply the database schema changes:

1. Connect to your PostgreSQL database:
   ```bash
   psql -U your_username -d your_database
   ```

2. Run the optimization script:
   ```sql
   \i database/db_optimizations.sql
   ```

For detailed information about the optimizations, see:
- [Database Documentation](docs/developer/database.md): Comprehensive documentation of database functionality
- `database/optimizations/`: SQL scripts containing schema optimizations

## Code Style Guidelines

- Follow standard Python PEP 8 style guidelines
- Use async/await for asynchronous operations
- Organize new features as cogs for modularity
- Document functions and classes with docstrings
- Use type hints for function parameters and return values

## Working with the Codebase

When making changes:
1. Ensure all new features are implemented as cogs when appropriate
2. Update requirements.txt if adding new dependencies
3. Maintain the existing error handling patterns
4. Follow the existing database interaction patterns for consistency
5. Test commands thoroughly before submitting changes

## Testing

The project includes several test scripts to verify different aspects of the system:

### Available Tests

1. **Dependency Test**: Verify that all dependencies are installed correctly
   ```bash
   uv run test_dependencies.py
   ```

2. **Database Connection Test**: Test the database connection
   ```bash
   uv run test_db_connection.py
   ```

3. **SQLAlchemy Models Test**: Test the SQLAlchemy models
   ```bash
   uv run test_sqlalchemy_models.py
   ```

4. **Cog Loading Test**: Test loading all cogs to ensure they can be loaded without errors
   ```bash
   uv run test_cogs.py
   ```
   This is particularly useful after making updates to verify that all changes work correctly.

For more details about the test scripts, see the [Tests README](tests/README.md).

When implementing changes, also:
- Manually test new features and commands
- Ensure database interactions work correctly
- Verify that commands respond appropriately to invalid inputs
- Check for potential conflicts with existing commands

## Code Modernization

The codebase has been modernized with several improvements to enhance maintainability, performance, and reliability:

### Type Hinting Improvements
- Updated type hints to use `collections.abc` instead of `typing` containers (Python 3.9+)
- Added `|` union operator for cleaner type annotations (Python 3.10+)
- Defined `TypeAlias` for complex types to improve code readability
- Added proper return type annotations throughout the codebase

### Async Features and Pattern Improvements
- Implemented `DatabaseTransaction` async context manager for cleaner transaction handling
- Added `asyncio.timeout` for more readable timeout handling in database operations
- Implemented async generators for pagination of large result sets
- Improved error handling in async operations

### Pattern Matching
- Used Python 3.10+ pattern matching for cleaner type-based logic
- Replaced complex if/elif chains with more readable match/case statements
- Enhanced code readability and maintainability

### SQLAlchemy Integration Improvements
- Implemented repository pattern for database operations
- Created a generic `BaseRepository` class for common CRUD operations
- Added specialized repositories for specific entity types
- Used SQLAlchemy 2.0-style queries for better type safety

### Error Handling and Logging Improvements
- Created a custom exception hierarchy for better error classification
- Implemented standardized error handling decorators for command handlers
- Added global error handlers for both regular and application commands
- Implemented error telemetry system for tracking and analyzing errors
- Enhanced user feedback with more specific error messages
- Added graceful degradation patterns for critical features
- Improved logging with consistent context information

## Documentation

- [Getting Started](docs/developer/getting-started.md): Setup and development guide
- [Features](docs/features.md): Comprehensive list of bot features and commands
- [Environment Variables](docs/developer/environment-variables.md): Configuration reference
- [Database Documentation](docs/developer/database.md): Database functionality and best practices
- [Error Handling Guidelines](docs/developer/error-handling.md): Standardized error handling patterns
- [Deployment Guide](docs/operations/deployment.md): Production deployment instructions
- [Contributing](docs/contributing.md): How to contribute to the project

## License

[License information]

## Author

WillHalloward

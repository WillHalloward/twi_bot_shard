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

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/twi_bot_shard.git
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
python test_dependencies.py
```

5. Set up PostgreSQL database

6. Configure the `.env` file with your credentials (see [Setup Guide](docs/SETUP.md) for details)

7. Run the bot:
```bash
python main.py
```

## Requirements

- Python 3.12+
- PostgreSQL database
- Discord Bot Token
- Various API keys (see [Setup Guide](docs/SETUP.md))
- uv package manager

## Environment Variables

The bot uses environment variables for configuration. These can be set in a `.env` file in the project root. Key variables include:

- `BOT_TOKEN`: Discord bot token
- `DATABASE`, `DB_USER`, `DB_PASSWORD`, `HOST`: Database connection details
- `KILL_AFTER`: Time in seconds after which the bot will automatically exit (set to 0 to disable this feature)

## Features

### Gallery & Mementos
- `Gallery`: Adds an image to #gallery
- `Mementos`: Adds an image to #mementos
- `SetMementos`: Set what channel !mementos posts to
- `setGallery`: Set what channel !gallery posts to

### Links
- `AddLink`: Adds a link with the given name to the given url and tag
- `Delink`: Deletes a link with the given name
- `Link`: Posts the link with the given name
- `Links`: View all links
- `Tag`: View all links that got a certain tag
- `Tags`: See all available tags

### ModCogs
- `reset`: Resets the cooldown of a command

### Other
- `Avatar`: Posts the full version of an avatar
- `Info`: Gives the account information of a user
- `Ping`: Gives the latency of the bot
- `Say`: Makes Cognita repeat whatever was said
- `SayChannel`: Makes Cognita repeat whatever was said in a specific channel
- `backup`: Backups the channel

### Poll
- `FindPoll`: Searches poll questions for a given query
- `GetPoll`: Fetches the latest poll from patreon
- `Poll`: Posts the latest poll or a specific poll

### The Wandering Inn
- `ColoredText`: List of all the different colored texts in TWI
- `ConnectDiscord`: Information for patreons on how to connect their patreon account
- `Invistext`: Gives a list of all the invisible text in TWI
- `Password`: Information for patreons on how to get the chapter password
- `Wiki`: Searches the The Wandering Inn wiki for a matching article

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

For more detailed information about the project structure, see [Project Structure](docs/PROJECT_STRUCTURE.md).

## Contributing

If you'd like to contribute to the project, please see the [Contributing Guide](CONTRIBUTING.md).

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
   ```
   psql -U your_username -d your_database
   ```

2. Run the optimization script:
   ```sql
   \i database/db_optimizations.sql
   ```

For detailed information about the optimizations, see:
- `utils/DATABASE.md`: Comprehensive documentation of database functionality, including optimizations
- `database/db_optimizations.sql`: SQL script containing the schema changes

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

There is no formal testing framework in place. When implementing changes:
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

- [Setup Guide](docs/SETUP.md): Detailed instructions for setting up the bot
- [Features](docs/FEATURES.md): Comprehensive list of bot features and commands
- [Project Structure](docs/PROJECT_STRUCTURE.md): Detailed explanation of the codebase
- [Database Documentation](utils/DATABASE.md): Comprehensive documentation of database functionality, including the Database Utility Module, SQLAlchemy integration, and database optimizations
- [Error Handling Guidelines](docs/ERROR_HANDLING.md): Standardized error handling patterns and best practices

## License

[License information]

## Author

WIllHallwoard

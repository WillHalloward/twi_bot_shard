# Project Structure - Twi Bot Shard (Cognita)

This document provides a detailed explanation of the project's codebase structure, helping contributors understand how different components interact.

## Directory Structure

```
twi_bot_shard/
├── cogs/                  # Bot command modules
│   ├── creator_links.py   # Creator link management
│   ├── example_cog.py     # Example cog with best practices
│   ├── gallery.py         # Image gallery management
│   ├── innktober.py       # Innktober event features
│   ├── links_tags.py      # Link management system
│   ├── mods.py            # Moderation tools
│   ├── other.py           # Miscellaneous utility commands
│   ├── owner.py           # Bot owner commands
│   ├── patreon_poll.py    # Patreon poll integration
│   ├── report.py          # Reporting functionality
│   ├── stats.py           # Statistics tracking
│   ├── summarization.py   # Text summarization features
│   └── twi.py             # The Wandering Inn specific features
├── emblems/               # Image assets for the bot
├── ssl-cert/              # SSL certificates for database connection
├── utils/                 # Utility modules
│   └── db.py              # Database utility class
├── main.py                # Entry point and bot initialization
├── requirements.txt       # Project dependencies
├── secrets.py             # Configuration and sensitive information
└── setup.py               # Installation script
```

## Core Components

### main.py

The entry point for the bot. It contains:

1. The `Cognita` class that extends `commands.Bot`
2. Bot initialization and configuration
3. Event handlers for interactions and commands
4. Database connection setup with SSL
5. Logging configuration
6. Status rotation functionality

Key features:
- Command history tracking in the database
- Cog loading system
- Status message rotation
- Database connection pooling

### Cogs

Cogs are modular components that add specific functionality to the bot. Each cog is a Python class that inherits from `commands.Cog`.

#### Common Cog Structure

```python
from discord.ext import commands

class MyCog(commands.Cog, name="Display Name"):
    def __init__(self, bot):
        self.bot = bot
        
    # Commands and listeners
    
async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

#### Key Cogs

- **gallery.py**: Manages image galleries with commands for adding images and setting gallery channels
- **links_tags.py**: Provides a link management system with tagging functionality
- **patreon_poll.py**: Integrates with Patreon to fetch and display polls
- **twi.py**: Contains commands specific to The Wandering Inn, including wiki search and colored text information
- **mods.py**: Provides moderation tools for server administrators
- **stats.py**: Tracks and reports on server statistics
- **creator_links.py**: Manages links to creator content
- **report.py**: Handles user reporting functionality
- **innktober.py**: Features for the Innktober event
- **summarization.py**: Text summarization capabilities

### Database Structure

The bot uses PostgreSQL for data storage. Database operations are handled through the `Database` utility class in `utils/db.py`.

Key database tables:
- Command history
- Links and tags
- Gallery entries
- User statistics
- Poll data

### Utility Modules

#### utils/db.py

Provides a wrapper around asyncpg for database operations with:
- Connection pooling
- Error handling and retries
- Transaction management
- Simplified query methods

## Command Types

The bot supports two types of commands:

1. **Prefix Commands**: Traditional commands that start with a prefix (default: `!`)
   ```python
   @commands.command(name="command_name")
   async def command_name(self, ctx):
       # Command implementation
   ```

2. **Slash Commands**: Discord's newer application commands
   ```python
   @app_commands.command(name="command_name")
   async def command_name(self, interaction: discord.Interaction):
       # Command implementation
   ```

## Event Handling

The bot uses Discord.py's event system to respond to various events:

```python
@commands.Cog.listener("on_message")
async def message_handler(self, message):
    # Handle message event
```

Common events used:
- `on_message`: Triggered when a message is sent
- `on_interaction`: Triggered for slash commands and other interactions
- `on_ready`: Triggered when the bot connects to Discord
- `on_raw_reaction_add`/`on_raw_reaction_remove`: Triggered for reactions

## Error Handling

Error handling is implemented at multiple levels:

1. **Command-level error handling**:
   ```python
   @command_name.error
   async def command_name_error(self, ctx, error):
       # Handle errors for this specific command
   ```

2. **Global error handling** in the main bot class

3. **Database operation error handling** in the Database utility class

## Configuration

Configuration is stored in `secrets.py` and includes:
- Discord bot token
- Database credentials
- API keys for various services
- Webhook URLs
- Logging configuration

## Dependencies

Key dependencies include:
- discord.py: Discord API wrapper
- asyncpg: PostgreSQL async client
- aiohttp: Async HTTP client
- pillow: Image processing
- google-api-python-client: Google API integration
- openai: OpenAI API integration

## Development Workflow

1. Create or modify a cog to add new functionality
2. Update the bot to load the new cog in `main.py`
3. Test the functionality
4. Update documentation as needed

## Best Practices

1. Use the Database utility for all database operations
2. Implement proper error handling for commands
3. Use transactions for operations that require multiple database queries
4. Document all commands with helpful docstrings
5. Follow the patterns in `example_cog.py` for new features
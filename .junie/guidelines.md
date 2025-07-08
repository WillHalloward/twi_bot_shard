# Development Guidelines for Twi Bot Shard

This document provides essential information for developers working on the Twi Bot Shard project. It includes build/configuration instructions, testing information, and development guidelines.

## Build/Configuration Instructions

### Environment Setup

1. **Python Version**: This project requires Python 3.12 or higher.

2. **Dependencies**: Install dependencies using uv (recommended) or pip:
   ```bash
   # Using uv (recommended)
   uv pip install -e .

   # Using pip
   pip install -e .
   ```

3. **Environment Variables**: Create a `.env` file in the project root with the following variables:
   ```
   BOT_TOKEN=your_discord_bot_token
   GOOGLE_API_KEY=your_google_api_key
   GOOGLE_CSE_ID=your_google_cse_id
   HOST=your_database_host
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DATABASE=your_database_name
   PORT=5432
   KILL_AFTER=0  # Time in seconds to run before exiting, 0 disables
   CLIENT_ID=your_client_id
   CLIENT_SECRET=your_client_secret
   USER_AGENT=your_user_agent
   USERNAME=your_username
   PASSWORD=your_password
   LOGFILE=test
   WEBHOOK_TESTING_LOG=your_webhook_testing_log
   WEBHOOK=your_webhook
   TWITTER_API_KEY=your_twitter_api_key
   TWITTER_API_KEY_SECRET=your_twitter_api_key_secret
   TWITTER_BEARER_TOKEN=your_twitter_bearer_token
   TWITTER_ACCESS_TOKEN=your_twitter_access_token
   TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
   AO3_USERNAME=your_ao3_username
   AO3_PASSWORD=your_ao3_password
   OPENAI_API_KEY=your_openai_api_key
   ```

4. **SSL Certificates**: Place your SSL certificates in the `ssl-cert` directory:
   - `server-ca.pem`
   - `client-cert.pem`
   - `client-key.pem`

### Database Setup

1. The project uses PostgreSQL with asyncpg for database operations.
2. The database schema can be found in `cognita_db_tables.sql`.
3. Database optimizations are available in `db_optimizations.sql`.

## Testing Information

### Running Tests

1. **Dependency Test**: Verify that all dependencies are installed correctly:
   ```bash
   uv run test_dependencies.py
   ```

2. **SQLAlchemy Models Test**: Test the SQLAlchemy models:
   ```bash
   uv run test_sqlalchemy_models.py
   ```

3. **Database Connection Test**: Test the database connection:
   ```bash
   uv run test_db_connection.py
   ```
4. **Cog loading Test**: Test that all cogs can be loaded without error:
   ```bash
   uv run test_cogs.py
   ```


### Creating New Tests

1. **Temporary Test Files**: For temporary test scripts, verification scripts, and example usage files, create them in the `temp_tests/` directory. This folder is git-ignored to keep the root directory clean. Examples of files that belong here:
   - `example_timer_usage.py`
   - `test_final_imports.py`
   - `test_save_function.py`

2. **Test Structure**: Follow the existing test structure in `test_sqlalchemy_models.py` for new tests.
3. **Async Tests**: Use `asyncio.run()` to run async tests.
4. **In-Memory Database**: For model tests, use an in-memory SQLite database:
   ```python
   TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
   ```
5. **Test Example**:
   ```python
   import asyncio
   import os
   import sys

   # Add the project root to the Python path
   sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

   # Import SQLAlchemy components
   from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
   from sqlalchemy.future import select
   from sqlalchemy.orm import sessionmaker

   # Import models
   from models.base import Base

   async def test_function():
       # Test code here
       pass

   async def main():
       result = await test_function()
       if result:
           print("Test passed!")
       else:
           print("Test failed.")

   if __name__ == "__main__":
       asyncio.run(main())
   ```

## Development Guidelines

### Code Style

1. **Docstrings**: Use triple-quoted docstrings for all modules, classes, and functions.
2. **Type Hints**: Use type hints for function parameters and return values.
3. **Error Handling**: Use try-except blocks for error handling, especially for database operations.
4. **Logging**: Use the logging module for logging, not print statements.

### Database Operations

1. **Transactions**: Use transactions for multiple related database operations:
   ```python
   async with self.bot.db.pool.acquire() as conn:
       async with conn.transaction():
           # Multiple related operations
           await conn.execute(...)
           await conn.execute(...)
   ```

2. **Query Parameters**: Always use parameterized queries to prevent SQL injection:
   ```python
   await self.bot.db.execute(
       "INSERT INTO example_table(name, value) VALUES($1, $2)",
       name, value
   )
   ```

### Cog Structure

1. **Initialization**: Initialize cogs with a reference to the bot:
   ```python
   def __init__(self, bot):
       self.bot = bot
       self.logger = logging.getLogger('cog_name')
   ```

2. **Setup Function**: Include a setup function at the end of each cog file:
   ```python
   async def setup(bot):
       await bot.add_cog(CogName(bot))
   ```

3. **Command Types**: Use both traditional commands and app commands:
   ```python
   # Traditional command
   @commands.command(name="command_name")
   async def command_name(self, ctx):
       # Command code

   # App command (slash command)
   @app_commands.command(name="command_name")
   async def command_name(self, interaction: discord.Interaction):
       # Command code
   ```

4. **Event Listeners**: Use event listeners for handling events:
   ```python
   @commands.Cog.listener("on_message")
   async def listener_name(self, message):
       # Listener code
   ```

### Error Handling

1. **Global Error Handler**: The project uses a global error handler in `utils/error_handling.py`.
2. **Command-Specific Error Handling**: Use command-specific error handlers when needed:
   ```python
   @command_name.error
   async def command_name_error(self, ctx, error):
       # Error handling code
   ```

### Adding New Features

1. **Create a New Cog**: For new features, create a new cog in the `cogs` directory.
2. **Register the Cog**: Add the cog to the `cogs` list in `main.py`.
3. **Database Models**: Add new database models in the `models/tables` directory.
4. **Alembic Migrations**: Use Alembic for database migrations when changing the schema.

# Developer Getting Started Guide

Welcome to Twi Bot Shard (Cognita) development! This guide will help you set up your local development environment.

> **Note:** This guide covers local development setup. For production deployment on Railway, see the [Deployment Guide](../operations/deployment.md).

## Prerequisites

Before you begin, ensure you have:

- **Python 3.12.9** (exact version required - see `pyproject.toml`)
- **PostgreSQL 12+** database server
- **Git** for version control
- **uv** package manager (recommended) or pip
- A **Discord Developer Account** for bot creation
- Basic command line knowledge

## Quick Setup

### 1. Clone the Repository

```bash
git clone https://github.com/WillHalloward/twi_bot_shard.git
cd twi_bot_shard
```

### 2. Create Virtual Environment

```bash
# Using venv
python3.12 -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### 4. Verify Dependencies

```bash
# Run dependency test
ENVIRONMENT=testing python tests/test_dependencies.py
```

## Discord Bot Setup

### Create Bot Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and name your bot
3. Navigate to the "Bot" tab and click "Add Bot"

### Configure Bot Intents

Enable the following **Privileged Gateway Intents**:
- ✅ Presence Intent
- ✅ Server Members Intent
- ✅ **Message Content Intent** (required for commands)

### Get Bot Token

1. In the Bot tab, click "Reset Token"
2. Copy the token (you'll need this for `.env`)
3. **Never commit your token to git!**

### Generate Invite URL

1. Navigate to OAuth2 → URL Generator
2. Select scopes:
   - `bot`
   - `applications.commands`
3. Select bot permissions:
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Add Reactions
   - Use External Emojis
   - Manage Messages (for moderation features)
4. Copy the generated URL and invite bot to your test server

## Database Setup

### Create PostgreSQL Database

```sql
-- Create database
CREATE DATABASE cognita_db;

-- Create user
CREATE USER botuser WITH PASSWORD 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE cognita_db TO botuser;
```

### Set Up SSL Certificates (Local Development)

For local development with SSL, place certificates in the `ssl-cert/` directory:
- `server-ca.pem` - Server certificate authority
- `client-cert.pem` - Client certificate
- `client-key.pem` - Client key

> **Railway Note:** For Railway deployment, SSL is handled automatically via the `DB_SSL` environment variable. Set `DB_SSL=disable` for Railway's pgvector template or `DB_SSL=require` for standard PostgreSQL. See [Deployment Guide](../operations/deployment.md).

### Apply Database Schema

```bash
# Apply main schema
psql -U botuser -d cognita_db -f database/init.sql

# Apply optimizations (optional for development)
psql -U botuser -d cognita_db -f database/optimizations/base.sql
psql -U botuser -d cognita_db -f database/optimizations/additional.sql
```

### Test Database Connection

```bash
ENVIRONMENT=testing python tests/test_db_connection.py
```

## Environment Configuration

### Create .env File

Create a `.env` file in the project root:

```bash
# Copy example file
cp .env.example .env

# Edit with your actual values
nano .env  # or your preferred editor
```

### Required Environment Variables

See [Environment Variables Guide](environment-variables.md) for complete reference.

**Minimum required:**

```env
# Discord
BOT_TOKEN=your_discord_bot_token

# Database (Option 1: Individual variables for local dev)
HOST=localhost
DB_USER=botuser
DB_PASSWORD=your_secure_password
DATABASE=cognita_db
PORT=5432

# Database (Option 2: Connection URL - Railway provides this automatically)
# DATABASE_URL=postgresql://user:password@host:port/database

# Development Settings
ENVIRONMENT=development
LOG_FORMAT=console
LOGFILE=dev
KILL_AFTER=0
```

> **Railway Note:** Railway automatically provides `DATABASE_URL` which takes precedence over individual variables.

### Verify Configuration

```bash
# Check environment variables are loaded
python -c "from config import *; print('Config loaded successfully')"
```

## Running the Bot

### Start Development Server

```bash
python main.py
```

The bot will:
1. Load configuration from `.env`
2. Connect to PostgreSQL database
3. Load all cogs (extensions)
4. Connect to Discord
5. Start responding to commands

### Expected Output

```
[2025-10-27 12:34:56] [INFO] bot: Logged in as YourBot (ID: 123456789)
[2025-10-27 12:34:56] [INFO] bot: Bot startup completed in 2.34s
```

## Development Workflow

### Code Formatting

```bash
# Format code with Black
python scripts/development/format.py

# Lint code with Ruff
python scripts/development/lint.py
```

### Type Checking

```bash
# Run mypy
mypy .
```

### Running Tests

```bash
# Run all tests
ENVIRONMENT=testing pytest tests/ -v

# Run specific test categories
ENVIRONMENT=testing python tests/test_dependencies.py
ENVIRONMENT=testing python tests/test_db_connection.py
ENVIRONMENT=testing python tests/test_sqlalchemy_models.py
ENVIRONMENT=testing python tests/test_cogs.py

# Run with coverage
ENVIRONMENT=testing pytest tests/ --cov=. --cov-report=xml
```

### Working with Cogs

See the [Features Documentation](../features.md) for detailed information on existing cogs.

**Quick example:**

```python
from discord.ext import commands
from utils.base_cog import BaseCog

class MyCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command()
    async def mycommand(self, ctx):
        await ctx.send("Hello from my cog!")

async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

### Database Operations

See [Database Guide](database.md) for details.

**Quick example:**

```python
# Using raw asyncpg (most common)
await self.bot.db.execute(
    "INSERT INTO example(name) VALUES($1)",
    "test"
)

# Fetching data
rows = await self.bot.db.fetch(
    "SELECT * FROM messages WHERE guild_id = $1",
    guild_id
)
```

## Troubleshooting

### Common Issues

**Bot not responding to commands:**
- Verify Message Content Intent is enabled
- Check bot has necessary permissions in Discord server
- Verify bot token in `.env` is correct

**Database connection errors:**
- Check PostgreSQL is running: `pg_isready`
- Verify credentials in `.env`
- Check SSL certificates are in `ssl-cert/`

**Import errors:**
- Reinstall dependencies: `uv pip install -e .`
- Verify virtual environment is activated
- Check Python version: `python --version` (should be 3.12.9)

**SSL certificate errors:**
- Verify certificate files exist and have correct permissions
- Check file paths in `main.py` match your setup

### Getting Help

- Check the [project documentation](../../CLAUDE.md) for detailed guides
- Check existing [GitHub issues](https://github.com/WillHalloward/twi_bot_shard/issues)

## Next Steps

Now that you have the bot running:

1. **Understand the Features** - Read [Features Documentation](../features.md)
2. **Learn Database Patterns** - Read [Database Guide](database.md)
3. **Review Error Handling** - See [Error Handling Guide](error-handling.md)
4. **Review Code Style** - See [Contributing Guide](../contributing.md)

## Development Tips

### Hot Reloading

Use the owner-only `reload` command to reload cogs without restarting:

```
!reload cogs.my_cog
```

### Debug Mode

Set `ENVIRONMENT=development` in `.env` for:
- More verbose logging
- Lazy loading of non-critical cogs
- Faster startup times

### Git Hooks

Set up pre-commit hooks:

```bash
python scripts/development/setup_hooks.py
```

This will run formatting and linting before each commit.

## Resources

- [Discord.py Documentation](https://discordpy.readthedocs.io/en/stable/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Project Documentation](../../CLAUDE.md)
- [Features Overview](../features.md)

---

**Ready to contribute?** Check out the [Contributing Guide](../contributing.md)!

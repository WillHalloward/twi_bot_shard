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
# Run linter to check code style
ruff check .

# Format code
ruff format .

# Run type checking
mypy .
```

### Testing
```bash
# Run all tests using pytest
ENVIRONMENT=testing pytest tests/
# Or with verbose output: pytest tests/ -v

# Run a single test file
ENVIRONMENT=testing pytest tests/test_cogs.py -v

# Run a specific test function
ENVIRONMENT=testing pytest tests/test_cogs.py::test_cog_loading -v

# Run with coverage
ENVIRONMENT=testing pytest tests/ --cov=. --cov-report=xml

# Run specific test categories
ENVIRONMENT=testing python tests/test_dependencies.py       # Verify dependencies
ENVIRONMENT=testing python tests/test_db_connection.py      # Test database connection
ENVIRONMENT=testing python tests/test_sqlalchemy_models.py  # Test ORM models
ENVIRONMENT=testing python tests/test_cogs.py               # Test all cog loading
ENVIRONMENT=testing python tests/test_chaos_engineering.py  # Test resilience
```

Note: The `ENVIRONMENT=testing` prefix ensures lazy cog loading and proper test configuration.

### Type checking
```bash
mypy .
```

### Dependency management (using uv)
```bash
# Install production dependencies only
uv pip install -e .

# Install with development tools (ruff, pytest, mypy, etc.)
uv pip install -e ".[dev]"

# Install with ML dependencies (faiss-cpu)
uv pip install -e ".[ml]"

# Add new dependency - update pyproject.toml then sync
uv pip install -e .
```

### Database Operations
```bash
# Apply all database optimizations
python scripts/database/optimize.py

# Apply only base optimizations
python scripts/database/optimize.py --base

# Apply only additional optimizations
python scripts/database/optimize.py --additional
```

### Git Hooks
```bash
# Setup pre-commit hooks (one-time)
pre-commit install

# Run all hooks manually
pre-commit run --all-files
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
   - Cogs that need a repository instantiate it in `__init__`, passing the bot's session factory, e.g. `self.link_repo = LinkRepository(bot.get_db_session)`
   - In **development/testing**: only `base_critical_cogs` load at startup; all others load lazily on-demand
   - In **production**: all 19 registered cogs load at startup (the lazy-loading behaviour is bypassed)
   - `base_critical_cogs`: `owner`, `mods`, `stats`, `settings`, `interactive_help`
   - Stats functionality uses a mixin architecture — see [Statistics System](#statistics-system) below

3. **Service Container** (`utils/service_container.py`)
   - Centralized dependency injection
   - Services registered: bot, db, http_client, resource_monitor
   - Factory pattern for database sessions
   - Access via `bot.container.get("service_name")`

4. **Repository Pattern** (`utils/repositories/`)
   - Each model has its own concrete repository class (e.g. `LinkRepository`, `ReportRepository`) — there is no shared base class or factory
   - Each repository takes a session factory (`Callable[[], Awaitable[AsyncSession]]`) and acquires/closes a session per method
   - Instantiate directly with `bot.get_db_session`; repositories are exported from `utils/repositories/__init__.py`
   - Encapsulates database logic and enforces business rules

5. **Database Layer**: Three-tier database access
   - **Raw SQL**: Direct asyncpg queries via `utils.db.Database`
   - **SQLAlchemy ORM**: Models in `models/tables/` with async session management
   - **Repository Pattern**: Concrete per-model repositories in `utils/repositories/`
   - Transaction support via `async with await bot.db.transaction():`

### Error Handling Architecture

The bot implements a comprehensive error handling strategy:

- **Custom Exception Hierarchy** (`utils/exceptions.py`): Specific exception types for different error categories (UserInputError, DatabaseError, ExternalServiceError, etc.)
- **Decorators**: `@handle_command_errors` for regular commands, `@handle_interaction_errors` for slash commands
- **Global Handlers**: Set up via `setup_global_exception_handler()` in main.py
- **Error Telemetry**: Tracks error patterns in database for proactive resolution
- **Sentry Reporting**: Unexpected errors are forwarded to Sentry from `log_error()` and the uncaught-exception hook (see [Observability & Monitoring](#observability--monitoring-sentry))

### Key Design Patterns

1. **Repository Pattern**: Database access abstraction with CRUD operations, bulk operations, error handling and retries, timezone-naive datetime handling (all times stored as UTC)
2. **Dependency Injection**: Service container for loose coupling
3. **Lazy Loading**: Non-critical cogs loaded on-demand in development/testing; all cogs load at startup in production
4. **Command Pattern**: Discord.py's built-in command system
5. **Async Context Managers**: Used for database transactions, HTTP sessions, resource cleanup
6. **Type Safety**: Modern Python type hints using `|` union operator, type aliases, SQLAlchemy 2.0-style queries

## Important Implementation Notes

### Adding New Features

1. **New Cog Creation**:
   - Inherit from `BaseCog` in `utils/base_cog.py`
   - Include `async def setup(bot)` function at module level (required for cog loading)
   - Use `self.logger` for structured logging
   - If the cog needs a repository, instantiate it in `__init__`, e.g. `self.link_repo = LinkRepository(bot.get_db_session)`
   - Use `@commands.Cog.listener()` decorator for event handlers
   - Use `@commands.command()` for prefix commands or `@app_commands.command()` for slash commands
   - Follow patterns in `cogs/example_cog.py`
   - Add cog to the `cogs` list in main.py (line ~1089)
   - Add to `base_critical_cogs` (line ~1107) only if required at startup

2. **New Database Model**:
   - Create model in `models/tables/` inheriting from `Base`
   - Use modern type hints: `Mapped[str]`, `Mapped[int | None]`
   - Create a concrete repository class in `utils/repositories/` accepting a session factory (`Callable[[], Awaitable[AsyncSession]]`)
   - Export the repository from `utils/repositories/__init__.py`
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

When inserting multiple records, always use bulk operations instead of
individual inserts:
```python
# Batch parameterized inserts
await bot.db.execute_many(query, list_of_param_tuples)

# Or bulk-copy rows into a table (fastest for large batches)
await bot.db.copy_records_to_table("table_name", records=rows, columns=cols)
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
- **Formatting**: Ruff (line length 88) configured in pyproject.toml

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

### Deployment & Branching Strategy

The project uses a two-branch deployment strategy with Railway:

- **`staging` branch**: Development branch, deploys to staging environment on Railway
- **`production` branch**: Protected branch, deploys to production environment on Railway

**Workflow:**
1. All development work happens on `staging` (or feature branches merged into `staging`)
2. Test changes in the staging environment
3. Create a PR from `staging` → `production` when ready to release
4. After PR approval and merge, production deployment happens automatically

**Branch Protection:**
- The `production` branch is protected and requires PR reviews before merging
- Direct pushes to `production` are not allowed
- This ensures all production changes are reviewed and tested in staging first

### Statistics System

The stats module uses a mixin architecture — `stats.py` is the only loadable cog; the other files are mixins it inherits from:
- `stats_commands.py`: Defines `StatsCommandsMixin` — owner commands for data management and comprehensive save operations
- `stats_listeners.py`: Defines `StatsListenersMixin` — real-time event listeners for message tracking, plus utility functions (`save_message`, `perform_comprehensive_save`)
- Only `stats.py` has a `setup()` function and is registered in main.py as `cogs.stats`
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
- Permission system leverages Discord's native permissions with bot owner override
- Setup git hooks via `pre-commit install` for automated checks

### Security Scanning (CI)

`.github/workflows/security-scan.yml` runs on push/PR to `staging` and
`production`, plus a weekly schedule. It has three jobs:

- **Dependency Vulnerability Scan** (`pip-audit`) — **advisory**. Uploads
  `pip-audit-report.json`; the step uses `continue-on-error: true` so known
  advisories (including un-patchable transitive ones) don't block merges.
- **Static Security Analysis** (`bandit`) — **advisory**. Scans the repo
  (excluding `tests` and `.venv`), uploads `bandit-report.json`, and likewise
  uses step-level `continue-on-error: true` so findings don't block merges.
- **Secret Scanning** (`gitleaks`) — **hard gate**. This one *should* fail the
  build if a secret is detected. It checks out with `fetch-depth: 0` so
  gitleaks can scan full history (a shallow clone makes it error with
  "stderr is not empty").

Advisory means the check reports green and the finding lives in the uploaded
artifact for triage. To promote a scanner to a blocking gate once its findings
are at zero, remove the `continue-on-error: true` from that job's run step.
Note: job-level `continue-on-error` alone is **not** enough — it spares the
overall run but the named check still reports red, so the flag must be on the
step.

### Observability & Monitoring (Sentry)

Runtime error reporting and liveness monitoring run through
[Sentry](https://sentry.io). The integration lives in
`utils/sentry_setup.py` and is **a no-op unless `SENTRY_DSN` is set**, so local
development and the test suite are unaffected.

**Initialisation** — `init_sentry()` is called early in `main.py` (right after
logging is configured). It is gated on `SENTRY_DSN` and tags every event with
the deployment `environment` and the git SHA as the `release`. Defaults are
privacy-conservative: `send_default_pii=False` and performance tracing off
(`traces_sample_rate=0.0`, tunable via `SENTRY_TRACES_SAMPLE_RATE`).

**Error reporting** — `capture_exception()` is fired from the existing
`log_error()` choke point (so it rides on the same filter that excludes
expected errors like cooldowns/check-failures/`CognitaError`) and from the
uncaught-exception hook in `setup_global_exception_handler()`. A `before_send`
hook runs the event's exception value and log message through
`redact_sensitive_info()`, so secrets are scrubbed before leaving the process.
Note: `before_send` does **not** scrub stack-frame local variables — rely on
Sentry's server-side data-scrubbing for those, or set
`include_local_variables=False` if needed.

**Liveness heartbeat** (`cogs/heartbeat.py`) — a dead-man's-switch for the
"unreachable but not throwing errors" failure mode (hang, OOM-kill, silent
gateway disconnect). While connected, the bot sends a Sentry cron check-in
every 5 minutes (`send_heartbeat()`, monitor slug `twi-bot-heartbeat`, created
automatically on first check-in). Sentry — externally — raises a missed
check-in issue after ~15 min (interval 5 + margin 10) when they stop. Because
the alert is driven by Sentry reacting to the *absence* of a signal, it fires
even when the bot itself is dead. The cog loads in staging/production (not in
test mode, where the loop is skipped).

**Configuration & alerting** — `SENTRY_DSN` is set as a Railway env var on both
the `staging` and `production` environments (same DSN; the `environment` tag
differentiates them). Issues route to Discord via Sentry **issue-alert rules**
("a new issue is created", filtered per environment) configured in the Sentry
UI — the MCP/API does not create alert rules.

**Gotcha** — running code locally with `SENTRY_DSN` set will report uncaught
exceptions to the shared project via Sentry's default excepthook integration.
Normal local dev tags them `development` (ignored by the staging/production
alert rules), but manual test scripts that force `environment='staging'`/
`'production'` will trip the real Discord alerts. Tag throwaway test events with
a distinct environment (e.g. `local-test`).

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

The bot requires `message_content` intent (configured in main.py):
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
    def __init__(self, bot):
        super().__init__(bot)
        self.gallery_repo = GalleryMementosRepository(bot.get_db_session)

    async def some_command(self, ctx):
        items = await self.gallery_repo.get_all()
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

- `main.py`: Bot initialization and lifecycle
- `config/__init__.py`: Environment configuration with Pydantic validation
- `utils/base_cog.py`: Base class for all cogs
- `utils/repositories/`: Concrete per-model repository classes
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

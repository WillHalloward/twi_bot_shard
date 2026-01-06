# Contributing to Twi Bot Shard

Thank you for your interest in contributing to the Twi Bot Shard (Cognita) project! This document provides guidelines for contributing to the project.

For detailed technical specifications and implementation patterns, refer to `CLAUDE.md` in the repository root, which serves as the authoritative technical reference.

## Getting Started

1. **Fork the repository** and clone it locally
2. **Set up your development environment** following the [Getting Started Guide](developer/getting-started.md)
3. **Install dependencies** using uv:
   ```bash
   uv pip install -e .
   ```
4. **Run tests** to ensure everything is working:
   ```bash
   # Run all tests using pytest
   ENVIRONMENT=testing pytest tests/

   # Run specific test categories
   ENVIRONMENT=testing python tests/test_dependencies.py       # Verify dependencies
   ENVIRONMENT=testing python tests/test_db_connection.py      # Test database connection
   ENVIRONMENT=testing python tests/test_sqlalchemy_models.py  # Test ORM models
   ENVIRONMENT=testing python tests/test_cogs.py               # Test all cog loading
   ```

   Note: The `ENVIRONMENT=testing` prefix ensures lazy cog loading and proper test configuration.

## Development Guidelines

### Code Style

- Follow standard Python PEP 8 style guidelines
- **Python 3.12** features: Use `|` for unions, `match/case`, modern type hints
- Use async/await for all Discord and database operations
- Organize new features as cogs for modularity
- Document functions and classes with Google-style docstrings
- Use type hints for all function parameters and return values

### Linting and Formatting

Before submitting changes, ensure your code passes linting and formatting checks:

```bash
# Run linter (ruff) to check code style
python scripts/development/lint.py
# Or directly: ruff check .

# Format code using Black
python scripts/development/format.py
# Or directly: black .

# Setup pre-commit hooks (recommended)
python scripts/development/setup_hooks.py
```

### Project Structure

- **New features** should be implemented as cogs in the `cogs/` directory
- **Database models** should be added to the `models/tables/` directory
- **Utility functions** should be placed in the `utils/` directory
- **Tests** should be added to the `tests/` directory

### Creating New Cogs

All cogs must follow these requirements:

1. **Inherit from `BaseCog`** in `utils/base_cog.py`
2. **Include an `async def setup(bot)` function** at module level (required for cog loading)
3. Use `self.logger` for structured logging
4. Access repositories via `self.get_repository(ModelClass)`

Example cog structure:

```python
from discord.ext import commands
from utils.base_cog import BaseCog

class MyCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        # Additional initialization

    @commands.command()
    async def my_command(self, ctx):
        await ctx.send("Response")

async def setup(bot):
    """Required entry point for cog loading."""
    await bot.add_cog(MyCog(bot))
```

After creating a cog, add it to the `cogs` list in `main.py`.

### Database Operations

- Use the Database utility class for all database operations
- Always use parameterized queries to prevent SQL injection
- Use transactions for multiple related database operations
- Prefer repositories over raw queries for model operations
- Follow the existing database interaction patterns for consistency

#### Datetime Handling

All datetime values must be stored as timezone-naive UTC:

```python
import datetime

# Correct - timezone-naive UTC
timestamp = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

# Incorrect - uses local timezone
timestamp = datetime.datetime.now()
```

### Error Handling

- Use the custom exception hierarchy from `utils/exceptions.py`
- Use `@handle_command_errors` decorator for prefix commands
- Use `@handle_interaction_errors` decorator for slash commands
- Provide helpful error messages to users (sanitized for security)

### Testing

- Test new features thoroughly before submitting changes
- Ensure database interactions work correctly
- Verify that commands respond appropriately to invalid inputs
- Check for potential conflicts with existing commands
- Run all existing tests to ensure no regressions
- All async tests should use `@pytest.mark.asyncio` decorator

```bash
# Run all tests
ENVIRONMENT=testing pytest tests/

# Run with verbose output
ENVIRONMENT=testing pytest tests/ -v

# Run with coverage
ENVIRONMENT=testing pytest tests/ --cov=. --cov-report=xml
```

## Branching Strategy

The project uses a two-branch deployment strategy with Railway:

- **`staging` branch**: Development branch, deploys to staging environment
- **`production` branch**: Protected branch, deploys to production environment

### Workflow

1. **All development work happens on `staging`** (or feature branches merged into `staging`)
2. Test changes in the staging environment
3. Create a PR from `staging` to `production` when ready to release
4. After PR approval and merge, production deployment happens automatically

### Branch Protection

- The `production` branch is protected and requires PR reviews before merging
- Direct pushes to `production` are not allowed
- This ensures all production changes are reviewed and tested in staging first

## Submitting Changes

### Pull Request Process

1. **Create a feature branch** from `staging` (or work directly on `staging` for small changes)
2. **Make your changes** following the development guidelines
3. **Run linting and formatting** to ensure code quality
4. **Test your changes** thoroughly
5. **Update documentation** if necessary
6. **Submit a pull request** to `staging` with a clear description of your changes

### Pull Request Guidelines

- **Clear title and description**: Explain what your changes do and why
- **Reference issues**: If your PR addresses an issue, reference it in the description
- **Keep changes focused**: Each PR should address a single feature or bug fix
- **Update documentation**: Include documentation updates for new features
- **Test coverage**: Ensure your changes are properly tested

## Code Review Process

- All submissions require review before merging
- Reviewers may request changes or improvements
- Address feedback promptly and professionally
- Be open to suggestions and alternative approaches

## Reporting Issues

### Bug Reports

When reporting bugs, please include:
- **Clear description** of the issue
- **Steps to reproduce** the problem
- **Expected behavior** vs actual behavior
- **Environment details** (Python version, OS, etc.)
- **Error messages** or logs if applicable

### Feature Requests

When requesting features, please include:
- **Clear description** of the desired functionality
- **Use case** explaining why this feature would be valuable
- **Proposed implementation** if you have ideas

## Development Environment

### Required Tools

- Python 3.12.9
- uv package manager
- PostgreSQL database
- Git for version control

### Environment Setup

Follow the detailed setup instructions in the [Developer Getting Started Guide](developer/getting-started.md).

## Documentation

- Update relevant documentation when making changes
- Follow the existing documentation style and format
- Include code examples where appropriate
- Keep documentation up to date with code changes
- Refer to `CLAUDE.md` for technical implementation details

## Community Guidelines

- Be respectful and professional in all interactions
- Help others learn and grow
- Provide constructive feedback
- Follow the project's code of conduct

## Questions and Support

If you have questions about contributing:
- Check the existing documentation first (including `CLAUDE.md`)
- Look through existing issues and pull requests
- Contact the project maintainers

Thank you for contributing to Twi Bot Shard!

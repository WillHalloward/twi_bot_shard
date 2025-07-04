# Developer Onboarding Guide

Welcome to the Twi Bot Shard development team! This guide will help you get set up with the project, understand its structure, and learn how to contribute effectively.

## Table of Contents

1. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Setting Up Your Development Environment](#setting-up-your-development-environment)
   - [Running the Bot Locally](#running-the-bot-locally)
2. [Project Structure](#project-structure)
   - [Key Directories and Files](#key-directories-and-files)
   - [Architecture Overview](#architecture-overview)
3. [Development Workflow](#development-workflow)
   - [Branching Strategy](#branching-strategy)
   - [Coding Standards](#coding-standards)
   - [Testing](#testing)
   - [Code Review Process](#code-review-process)
4. [Adding New Features](#adding-new-features)
   - [Creating a New Cog](#creating-a-new-cog)
   - [Adding Commands](#adding-commands)
   - [Working with the Database](#working-with-the-database)
   - [Error Handling](#error-handling)
5. [Common Tasks](#common-tasks)
   - [Adding a New Command](#adding-a-new-command)
   - [Modifying the Database Schema](#modifying-the-database-schema)
   - [Adding a New External Service Integration](#adding-a-new-external-service-integration)
   - [Debugging Tips](#debugging-tips)
6. [Resources](#resources)
   - [Documentation](#documentation)
   - [Tools](#tools)
   - [Community](#community)

## Getting Started

### Prerequisites

Before you begin, make sure you have the following installed:

- **Python 3.12+**: The project requires Python 3.12 or higher.
- **PostgreSQL 14+**: The database backend for the bot.
- **Git**: For version control.
- **uv**: Recommended for dependency management (alternative to pip).

### Setting Up Your Development Environment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/twi_bot_shard.git
   cd twi_bot_shard
   ```

2. **Create a virtual environment**:
   ```bash
   # Using venv
   python -m venv venv
   
   # Activate the virtual environment
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   # Using uv (recommended)
   uv pip install -e .
   
   # Using pip
   pip install -e .
   ```

4. **Set up environment variables**:
   Create a `.env` file in the project root with the necessary environment variables. See the `.env.example` file for required variables.

5. **Set up the database**:
   ```bash
   # Create a PostgreSQL database
   createdb twi_bot_shard
   
   # Run the database setup script
   python -m scripts.setup_database
   ```

6. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

### Running the Bot Locally

1. **Start the bot**:
   ```bash
   python main.py
   ```

2. **Testing the bot**:
   The bot should now be running and connected to Discord. You can test it by using commands in a Discord server where the bot is present.

## Project Structure

### Key Directories and Files

- **`main.py`**: The entry point of the application.
- **`cogs/`**: Contains command modules (cogs) for different features.
- **`utils/`**: Utility functions and classes used throughout the project.
- **`models/`**: SQLAlchemy models for database entities.
- **`config.py`**: Configuration management.
- **`tests/`**: Test cases for the project.
- **`docs/`**: Project documentation.

### Architecture Overview

Twi Bot Shard follows a modular architecture with the following key components:

1. **Bot Core**: Handles Discord events and command registration.
2. **Cogs**: Implement specific bot features and commands.
3. **Service Container**: Manages dependencies and services.
4. **Database Layer**: Handles data persistence using SQLAlchemy.
5. **Utility Services**: Provides shared functionality.

For a more detailed overview, see the [Architecture Documentation](architecture.md).

## Development Workflow

### Branching Strategy

We follow a feature branch workflow:

1. **Main Branch**: The `main` branch contains the production-ready code.
2. **Feature Branches**: Create a new branch for each feature or bugfix.
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Pull Requests**: Submit a pull request to merge your changes into the main branch.

### Coding Standards

We follow these coding standards:

1. **PEP 8**: Follow the Python style guide.
2. **Type Hints**: Use type hints for all function parameters and return values.
3. **Docstrings**: Add docstrings to all modules, classes, and functions.
4. **Linting**: Code is linted using ruff and formatted with black.

Run the linting tools before committing:
```bash
# Format code with black
black .

# Lint code with ruff
ruff check .
```

### Testing

We use pytest for testing:

1. **Running Tests**:
   ```bash
   pytest
   ```

2. **Test Coverage**:
   ```bash
   pytest --cov=.
   ```

3. **Writing Tests**:
   - Place tests in the `tests/` directory.
   - Name test files with the `test_` prefix.
   - Use fixtures for common setup.

### Code Review Process

All code changes go through a code review process:

1. **Create a Pull Request**: Submit your changes as a pull request.
2. **CI Checks**: Automated checks will run on your PR.
3. **Code Review**: At least one team member must review and approve your changes.
4. **Merge**: Once approved and all checks pass, your changes will be merged.

## Adding New Features

### Creating a New Cog

To add a new feature, create a new cog:

1. **Create a new file** in the `cogs/` directory:
   ```python
   # cogs/your_feature.py
   import discord
   from discord.ext import commands
   
   class YourFeature(commands.Cog):
       def __init__(self, bot):
           self.bot = bot
           self.logger = logging.getLogger('your_feature')
       
       @commands.command(name="your_command")
       async def your_command(self, ctx):
           """Your command description."""
           await ctx.send("Your command response")
   
   async def setup(bot):
       await bot.add_cog(YourFeature(bot))
   ```

2. **Register the cog** in `main.py`:
   ```python
   # Add to the INITIAL_EXTENSIONS list
   INITIAL_EXTENSIONS = [
       # ...
       'cogs.your_feature',
   ]
   ```

### Adding Commands

You can add commands to your cog in two ways:

1. **Traditional Commands**:
   ```python
   @commands.command(name="command_name")
   async def command_name(self, ctx, arg1: str, arg2: int = 10):
       """Command description.
       
       Args:
           arg1: Description of arg1
           arg2: Description of arg2, defaults to 10
       """
       # Command implementation
       await ctx.send(f"You provided {arg1} and {arg2}")
   ```

2. **Slash Commands**:
   ```python
   @app_commands.command(name="command_name")
   @app_commands.describe(
       arg1="Description of arg1",
       arg2="Description of arg2, defaults to 10"
   )
   async def command_name(self, interaction: discord.Interaction, arg1: str, arg2: int = 10):
       """Command description."""
       # Command implementation
       await interaction.response.send_message(f"You provided {arg1} and {arg2}")
   ```

### Working with the Database

Use SQLAlchemy models and repositories for database operations:

1. **Define a model** in `models/tables/`:
   ```python
   # models/tables/your_model.py
   from sqlalchemy import Column, Integer, String, ForeignKey
   from sqlalchemy.orm import relationship
   
   from models.base import Base
   
   class YourModel(Base):
       __tablename__ = "your_table"
       
       id = Column(Integer, primary_key=True)
       name = Column(String, nullable=False)
       description = Column(String)
       
       # Define relationships if needed
       user_id = Column(Integer, ForeignKey("users.id"))
       user = relationship("User", back_populates="your_models")
   ```

2. **Create a repository** in `utils/repositories/`:
   ```python
   # utils/repositories/your_repository.py
   from typing import List, Optional
   
   from sqlalchemy import select
   from sqlalchemy.ext.asyncio import AsyncSession
   
   from models.tables.your_model import YourModel
   from utils.repository import BaseRepository
   
   class YourRepository(BaseRepository[YourModel]):
       def __init__(self, session: AsyncSession):
           super().__init__(YourModel, session)
       
       async def get_by_name(self, name: str) -> Optional[YourModel]:
           query = select(YourModel).where(YourModel.name == name)
           result = await self.session.execute(query)
           return result.scalars().first()
       
       async def get_all(self) -> List[YourModel]:
           query = select(YourModel)
           result = await self.session.execute(query)
           return result.scalars().all()
   ```

3. **Use the repository** in your cog:
   ```python
   from utils.repositories.your_repository import YourRepository
   
   class YourFeature(commands.Cog):
       # ...
       
       @commands.command(name="list_items")
       async def list_items(self, ctx):
           """List all items."""
           async with self.bot.db.session() as session:
               repository = YourRepository(session)
               items = await repository.get_all()
               
               if not items:
                   await ctx.send("No items found.")
                   return
               
               items_list = "\n".join(f"{item.id}: {item.name}" for item in items)
               await ctx.send(f"Items:\n{items_list}")
   ```

### Error Handling

Use the error handling decorators for consistent error handling:

```python
from utils.error_handling import handle_command_errors, handle_interaction_errors

class YourFeature(commands.Cog):
    # ...
    
    @commands.command(name="risky_command")
    @handle_command_errors
    async def risky_command(self, ctx):
        """A command that might raise exceptions."""
        # This will be handled by the decorator
        result = 1 / 0  # Will raise ZeroDivisionError
        await ctx.send(f"Result: {result}")
    
    @app_commands.command(name="risky_slash")
    @handle_interaction_errors
    async def risky_slash(self, interaction: discord.Interaction):
        """A slash command that might raise exceptions."""
        # This will be handled by the decorator
        result = 1 / 0  # Will raise ZeroDivisionError
        await interaction.response.send_message(f"Result: {result}")
```

## Common Tasks

### Adding a New Command

1. **Identify the appropriate cog** for your command, or create a new one.
2. **Add the command method** to the cog.
3. **Add error handling** using the error handling decorators.
4. **Add tests** for the command in the `tests/` directory.
5. **Update documentation** to include the new command.

### Modifying the Database Schema

1. **Update the model** in `models/tables/`.
2. **Create a migration script** using Alembic:
   ```bash
   alembic revision --autogenerate -m "Description of changes"
   ```
3. **Review the migration script** to ensure it's correct.
4. **Apply the migration**:
   ```bash
   alembic upgrade head
   ```
5. **Update repositories** to use the new schema.
6. **Add tests** for the new database functionality.

### Adding a New External Service Integration

1. **Create a service class** in `utils/`:
   ```python
   # utils/your_service.py
   import logging
   from typing import Dict, Any
   
   class YourService:
       def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
           self.api_key = api_key
           self.base_url = base_url
           self.logger = logging.getLogger("your_service")
       
       async def get_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
           """Get data from the service API.
           
           Args:
               endpoint: The API endpoint to call
               params: Optional query parameters
               
           Returns:
               The API response data
           """
           # Implementation
           pass
   ```

2. **Register the service** in the service container:
   ```python
   # utils/service_container.py
   from utils.your_service import YourService
   
   class ServiceContainer:
       # ...
       
       def _init_services(self):
           # ...
           self._your_service = YourService(
               api_key=self.config.YOUR_API_KEY,
               base_url=self.config.YOUR_API_BASE_URL
           )
       
       @property
       def your_service(self) -> YourService:
           return self._your_service
   ```

3. **Use the service** in your cog:
   ```python
   class YourFeature(commands.Cog):
       # ...
       
       @commands.command(name="get_external_data")
       async def get_external_data(self, ctx, query: str):
           """Get data from the external service."""
           try:
               data = await self.bot.services.your_service.get_data("search", {"q": query})
               await ctx.send(f"Results: {data}")
           except Exception as e:
               await ctx.send(f"Error fetching data: {e}")
   ```

### Debugging Tips

1. **Enable Debug Logging**:
   ```python
   # Set logging level to DEBUG in main.py
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Use Print Statements** (for quick debugging):
   ```python
   print(f"Variable value: {variable}")
   ```

3. **Use the Discord.py Debug Mode**:
   ```python
   # In main.py
   bot = commands.Bot(command_prefix="!", debug=True)
   ```

4. **Check the Logs**:
   - Look at the console output
   - Check the log files in the `logs/` directory

5. **Test in Isolation**:
   - Create a test script that reproduces the issue
   - Use pytest to create a test case

## Resources

### Documentation

- [Project Documentation](../docs/)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Python Documentation](https://docs.python.org/)

### Tools

- [Visual Studio Code](https://code.visualstudio.com/) - Recommended IDE
- [PyCharm](https://www.jetbrains.com/pycharm/) - Alternative IDE
- [Discord Developer Portal](https://discord.com/developers/applications) - For managing your bot application
- [PostgreSQL](https://www.postgresql.org/) - Database system

### Community

- [Discord.py Discord Server](https://discord.gg/r3sSKJJ) - For discord.py help
- [Python Discord Server](https://discord.gg/python) - For general Python help
- [SQLAlchemy Community](https://sqlalchemy.org/support.html) - For SQLAlchemy help
# Contributing to Twi Bot Shard

Thank you for your interest in contributing to the Twi Bot Shard (Cognita) project! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** and clone it locally
2. **Set up your development environment** following the [Setup Guide](docs/SETUP.md)
3. **Install dependencies** using uv:
   ```bash
   uv pip install -e .
   ```
4. **Run tests** to ensure everything is working:
   ```bash
   uv run test_dependencies.py
   uv run test_db_connection.py
   uv run test_sqlalchemy_models.py
   uv run test_cogs.py
   ```

## Development Guidelines

### Code Style

- Follow standard Python PEP 8 style guidelines
- Use async/await for asynchronous operations
- Organize new features as cogs for modularity
- Document functions and classes with docstrings
- Use type hints for function parameters and return values

### Project Structure

- **New features** should be implemented as cogs in the `cogs/` directory
- **Database models** should be added to the `models/tables/` directory
- **Utility functions** should be placed in the `utils/` directory
- **Tests** should be added to the `tests/` directory

### Database Operations

- Use the Database utility class for all database operations
- Always use parameterized queries to prevent SQL injection
- Use transactions for multiple related database operations
- Follow the existing database interaction patterns for consistency

### Error Handling

- Use try-except blocks for error handling, especially for database operations
- Follow the existing error handling patterns in the codebase
- Provide helpful error messages to users

### Testing

- Test new features thoroughly before submitting changes
- Ensure database interactions work correctly
- Verify that commands respond appropriately to invalid inputs
- Check for potential conflicts with existing commands
- Run all existing tests to ensure no regressions

## Submitting Changes

### Pull Request Process

1. **Create a feature branch** from the main branch
2. **Make your changes** following the development guidelines
3. **Test your changes** thoroughly
4. **Update documentation** if necessary
5. **Submit a pull request** with a clear description of your changes

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

Follow the detailed setup instructions in the [Setup Guide](docs/SETUP.md) and [Development Guidelines](.junie/guidelines.md).

## Documentation

- Update relevant documentation when making changes
- Follow the existing documentation style and format
- Include code examples where appropriate
- Keep documentation up to date with code changes

## Community Guidelines

- Be respectful and professional in all interactions
- Help others learn and grow
- Provide constructive feedback
- Follow the project's code of conduct

## Questions and Support

If you have questions about contributing:
- Check the existing documentation first
- Look through existing issues and pull requests
- Contact the project maintainers

Thank you for contributing to Twi Bot Shard!
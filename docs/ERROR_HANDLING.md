# Error Handling Guidelines for Cognita Bot

This document outlines the standardized error handling patterns implemented in the Cognita bot codebase. Following these guidelines will ensure consistent error handling, better user feedback, and improved error tracking.

## Table of Contents

1. [Exception Hierarchy](#exception-hierarchy)
2. [Error Handling Decorators](#error-handling-decorators)
3. [Global Error Handlers](#global-error-handlers)
4. [Error Telemetry](#error-telemetry)
5. [Best Practices](#best-practices)

## Exception Hierarchy

The bot uses a custom exception hierarchy defined in `utils/exceptions.py`:

```python
CognitaError                  # Base exception for all bot errors
├── UserInputError            # Errors caused by invalid user input
├── ExternalServiceError      # Errors from external services (Twitter, AO3, etc.)
├── PermissionError           # Errors related to permissions
├── ResourceNotFoundError     # Errors when a requested resource is not found
├── ConfigurationError        # Errors related to bot configuration
├── RateLimitError            # Errors related to rate limiting
└── DatabaseError             # Errors related to database operations
```

### Using Custom Exceptions

When raising exceptions in your code, use the appropriate exception type from the hierarchy:

```python
# Instead of:
if not valid_input:
    raise Exception("Invalid input")

# Use:
if not valid_input:
    raise UserInputError("Please provide a valid image URL")
```

## Error Handling Decorators

Two decorators are provided in `utils/error_handling.py` to standardize error handling:

### For Regular Commands

```python
from utils.error_handling import handle_command_errors

class MyCog(commands.Cog):
    @commands.command()
    @handle_command_errors
    async def my_command(self, ctx):
        # Your code here
        pass
```

### For Application Commands (Slash Commands)

```python
from utils.error_handling import handle_interaction_errors

class MyCog(commands.Cog):
    @app_commands.command()
    @handle_interaction_errors
    async def my_slash_command(self, interaction):
        # Your code here
        pass
```

## Global Error Handlers

The bot has global error handlers for both regular commands and application commands:

- `on_command_error` - Handles errors from regular commands
- `on_app_command_error` - Handles errors from application commands

These handlers:
1. Log the error with appropriate context
2. Provide user feedback
3. Record error telemetry

## Error Telemetry

Errors are recorded in the `error_telemetry` table for analysis. The table includes:

- Error type
- Command name
- User ID
- Error message
- Guild ID
- Channel ID
- Timestamp
- Resolution status

### Querying Error Telemetry

Two SQL functions are provided for analyzing errors:

```sql
-- Get error statistics by type and command
SELECT * FROM get_error_statistics(
    start_date := '2023-01-01',
    end_date := '2023-12-31'
);

-- Get most common errors
SELECT * FROM get_most_common_errors(
    limit_count := 10,
    start_date := '2023-01-01',
    end_date := '2023-12-31'
);
```

## Best Practices

### 1. Use Specific Exceptions

Catch and raise specific exceptions rather than generic ones:

```python
# Instead of:
try:
    # Some operation
except Exception as e:
    logging.error(f"Error: {e}")

# Use:
try:
    # Some operation
except ExternalServiceError as e:
    logging.error(f"Service error: {e}")
except UserInputError as e:
    logging.error(f"Input error: {e}")
```

### 2. Provide Helpful Error Messages

Error messages should be clear and actionable:

```python
# Instead of:
raise UserInputError("Invalid input")

# Use:
raise UserInputError("Please provide a valid image URL (must start with http:// or https://)")
```

### 3. Use Decorators for Command Handlers

Always use the provided decorators for command handlers to ensure consistent error handling:

```python
@commands.command()
@handle_command_errors
async def my_command(self, ctx):
    # Your code here
```

### 4. Log Appropriate Context

When logging errors manually, include relevant context:

```python
logging.error(f"{error_type} in {command_name}: {error_message} | User: {user_id}")
```

### 5. Implement Graceful Degradation

For critical features, implement fallback mechanisms:

```python
async def get_user_data(user_id):
    try:
        # Primary method - database
        return await db.fetch("SELECT * FROM users WHERE user_id = $1", user_id)
    except DatabaseError:
        # Fallback method - cache
        return cache.get(f"user:{user_id}")
```

By following these guidelines, you'll contribute to a more robust and user-friendly bot experience.
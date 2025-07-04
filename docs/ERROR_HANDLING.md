# Error Handling Guidelines for Cognita Bot

This document outlines the standardized error handling patterns implemented in the Cognita bot codebase. Following these guidelines will ensure consistent error handling, better user feedback, and improved error tracking.

## Table of Contents

1. [Exception Hierarchy](#exception-hierarchy)
2. [Error Handling Decorators](#error-handling-decorators)
3. [Global Error Handlers](#global-error-handlers)
4. [Error Response Configuration](#error-response-configuration)
5. [Error Telemetry](#error-telemetry)
6. [Best Practices](#best-practices)

## Exception Hierarchy

The bot uses a comprehensive custom exception hierarchy defined in `utils/exceptions.py`:

```python
CognitaError                                # Base exception for all bot errors
├── UserInputError                          # Errors caused by invalid user input
│   ├── ValidationError                     # Input validation failures
│   └── FormatError                         # Incorrectly formatted input
├── ExternalServiceError                    # Errors from external services
│   ├── APIError                            # Errors from API calls
│   └── ServiceUnavailableError             # Service unavailable errors
├── PermissionError                         # Errors related to permissions
│   ├── RolePermissionError                 # Role-based permission errors
│   └── OwnerOnlyError                      # Owner-only command errors
├── ResourceNotFoundError                   # Resource not found errors
├── ResourceAlreadyExistsError              # Resource already exists errors
├── ResourceInUseError                      # Resource in use errors
├── ConfigurationError                      # Bot configuration errors
│   ├── MissingConfigurationError           # Missing configuration values
│   └── InvalidConfigurationError           # Invalid configuration values
├── RateLimitError                          # Rate limiting errors
│   └── CommandCooldownError                # Command cooldown errors
├── DatabaseError                           # Database operation errors
│   ├── QueryError                          # Database query errors
│   ├── ConnectionError                     # Database connection errors
│   └── TransactionError                    # Database transaction errors
└── DiscordError                            # Discord API errors
    ├── MessageError                        # Message operation errors
    ├── ChannelError                        # Channel operation errors
    └── GuildError                          # Guild operation errors
```

### Using Custom Exceptions

When raising exceptions in your code, use the most specific exception type from the hierarchy:

```python
# Instead of:
if not valid_input:
    raise Exception("Invalid input")

# Use:
if not valid_input:
    raise ValidationError(field="image_url", message="Please provide a valid image URL")
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

The bot has a centralized error handling system that automatically sets up global error handlers:

```python
from utils.error_handling import setup_global_exception_handler

# In your bot's setup_hook method:
setup_global_exception_handler(bot)
```

This sets up:
1. Global command error handler (`on_command_error`)
2. Global application command error handler (`on_app_command_error`)
3. Global uncaught exception handler

These handlers:
1. Log the error with appropriate context
2. Provide user feedback based on the error type
3. Record error telemetry

## Error Response Configuration

The error handling system uses a configuration dictionary to determine how to respond to different types of errors:

```python
ERROR_RESPONSES = {
    UserInputError: {
        "message": "Invalid input: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True
    },
    # ... other error types ...
}
```

For each error type, you can configure:
- The user-facing message template
- The logging level
- Whether the response should be ephemeral (for interactions)

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
except APIError as e:
    logging.error(f"API error: {e}")
except ValidationError as e:
    logging.error(f"Validation error: {e}")
```

### 2. Provide Helpful Error Messages

Error messages should be clear and actionable:

```python
# Instead of:
raise UserInputError("Invalid input")

# Use:
raise ValidationError(
    field="image_url",
    message="Please provide a valid image URL (must start with http:// or https://)"
)
```

### 3. Use Decorators for Command Handlers

Always use the provided decorators for command handlers to ensure consistent error handling:

```python
@commands.command()
@handle_command_errors
async def my_command(self, ctx):
    # Your code here
```

### 4. Use the Standardized Logging Function

Use the `log_error` function for consistent error logging:

```python
from utils.error_handling import log_error

try:
    # Some operation
except ValidationError as e:
    log_error(
        error=e,
        command_name="my_command",
        user_id=user_id,
        log_level=logging.WARNING,
        additional_context="During image processing"
    )
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

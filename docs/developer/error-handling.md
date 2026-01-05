# Error Handling Guidelines for Cognita Bot

This document outlines the standardized error handling patterns implemented in the Cognita bot codebase. Following these guidelines will ensure consistent error handling, better user feedback, and improved error tracking.

## Table of Contents

1. [Exception Hierarchy](#exception-hierarchy)
2. [Security](#security)
3. [Error Handling Decorators](#error-handling-decorators)
4. [Global Error Handlers](#global-error-handlers)
5. [Error Response Configuration](#error-response-configuration)
6. [Error Telemetry](#error-telemetry)
7. [Best Practices](#best-practices)

## Exception Hierarchy

The bot uses a custom exception hierarchy defined in `utils/exceptions.py`:

```python
CognitaError                                # Base exception for all bot errors
├── UserInputError                          # Errors caused by invalid user input
│   └── ValidationError                     # Input validation failures
├── ExternalServiceError                    # Errors from external services
│   └── APIError                            # Errors from API calls
├── PermissionError                         # Errors related to permissions
│   ├── RolePermissionError                 # Role-based permission errors
│   └── OwnerOnlyError                      # Owner-only command errors
├── ResourceNotFoundError                   # Resource not found errors
├── ResourceAlreadyExistsError              # Resource already exists errors
└── DatabaseError                           # Database operation errors
    └── QueryError                          # Database query errors
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

### Exception Details

Each exception type accepts specific parameters:

```python
# ValidationError - for input validation failures
raise ValidationError(field="username", message="Username must be 3-20 characters")

# APIError - for external API failures
raise APIError(service_name="Twitter", status_code=429, message="Rate limited")

# ResourceNotFoundError - for missing resources
raise ResourceNotFoundError(resource_type="gallery item", resource_id="12345")

# RolePermissionError - for role-based access control
raise RolePermissionError(required_role="Moderator")
```

## Security

The error handling system includes security features to prevent information disclosure defined in `utils/error_handling.py`.

### ErrorSecurityLevel Class

Security levels control how much detail is shown in error messages:

```python
class ErrorSecurityLevel:
    DEBUG = 0   # Show detailed error information (for developers/admins)
    NORMAL = 1  # Show general error information (for trusted users)
    SECURE = 2  # Show minimal error information (for all users)
```

Security levels are automatically determined based on user permissions:
- Administrators receive `DEBUG` level (more detailed errors)
- Regular users receive `NORMAL` level

### Sensitive Information Detection

The `SENSITIVE_PATTERNS` list defines regex patterns for detecting sensitive information:

- API keys and tokens
- Discord tokens
- Database connection strings
- IP addresses
- Email addresses
- File paths
- JSON Web Tokens (JWTs)

### Security Functions

```python
from utils.error_handling import (
    detect_sensitive_info,
    redact_sensitive_info,
    sanitize_error_message,
    ErrorSecurityLevel
)

# Detect if text contains sensitive information
if detect_sensitive_info(error_message):
    # Handle sensitive content
    pass

# Redact sensitive information from text
safe_message = redact_sensitive_info(error_message)

# Get a sanitized error message based on security level
user_message = sanitize_error_message(error, ErrorSecurityLevel.NORMAL)
```

The `sanitize_error_message()` function behavior by security level:

- **DEBUG**: Returns error type and message with sensitive info redacted
- **NORMAL**: Returns first line of message (max 100 chars) if no sensitive info detected, otherwise returns a generic message
- **SECURE**: Always returns a generic message: "An error occurred. Please contact an administrator if this persists."

### Sensitive Error Types

Certain error types (`DatabaseError`, `QueryError`, `APIError`, `ExternalServiceError`) are automatically treated as sensitive and will always return sanitized messages to users.

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

Both decorators:
1. Catch exceptions raised by the handler
2. Determine the security level based on user permissions
3. Get the appropriate error response with sanitization
4. Send a user-friendly error message
5. Log the error with context (including guild_id and channel_id)
6. Record error telemetry to the database

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
3. Global uncaught exception handler (`sys.excepthook`)

These handlers:
1. Log the error with appropriate context
2. Provide user feedback based on the error type
3. Record error telemetry

### Lazy Loading Feature

The global app command error handler includes a lazy loading mechanism for commands. When a `CommandNotFound` error occurs:

1. The handler extracts the command name from the error
2. Looks up the corresponding extension in a command-to-extension mapping
3. Attempts to load the extension using `bot.load_extension_if_needed()`
4. Syncs the command tree
5. Attempts to automatically execute the command

Supported lazy-loaded commands include:
- `poll`, `poll_list`, `getpoll`, `findpoll` -> `cogs.patreon_poll`
- `gallery`, `gallery_search`, `gallery_random`, `gallery_stats` -> `cogs.gallery`
- `links`, `tags` -> `cogs.links_tags`
- `twi` -> `cogs.twi`
- `other` -> `cogs.other`
- `creator_links` -> `cogs.creator_links`
- `report` -> `cogs.report`
- `summarization` -> `cogs.summarization`

## Error Response Configuration

The error handling system uses a configuration dictionary to determine how to respond to different types of errors:

```python
ERROR_RESPONSES = {
    # Custom exceptions
    UserInputError: {
        "message": "Invalid input: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True
    },
    ValidationError: {
        "message": "Validation error: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True
    },
    ExternalServiceError: {
        "message": "External service error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True
    },
    # ... other custom exceptions ...

    # Discord.py built-in errors
    commands.CommandNotFound: {
        "message": "Command not found. Use /help to see available commands.",
        "log_level": logging.INFO,
        "ephemeral": True
    },
    commands.MissingRequiredArgument: {
        "message": "Missing required argument: {error.param.name}",
        "log_level": logging.WARNING,
        "ephemeral": True
    },
    commands.BadArgument: {
        "message": "Invalid argument: {error}",
        "log_level": logging.WARNING,
        "ephemeral": True
    },
    commands.CheckFailure: {
        "message": "You don't have permission to use this command.",
        "log_level": logging.WARNING,
        "ephemeral": True
    },
    commands.CommandOnCooldown: {
        "message": "This command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
        "log_level": logging.INFO,
        "ephemeral": True
    },
    discord.app_commands.errors.CommandOnCooldown: {
        "message": "Please wait {error.retry_after:.1f} seconds before using this command again.",
        "log_level": logging.WARNING,
        "ephemeral": True
    },
    discord.app_commands.errors.CheckFailure: {
        "message": "This command can only be used in specific channels.",
        "log_level": logging.DEBUG,
        "ephemeral": True
    },
    commands.NoPrivateMessage: {
        "message": "This command cannot be used in private messages.",
        "log_level": logging.INFO,
        "ephemeral": True
    },
    commands.DisabledCommand: {
        "message": "This command is currently disabled.",
        "log_level": logging.INFO,
        "ephemeral": True
    },
    # Fallbacks
    CognitaError: {
        "message": "Error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True
    },
    Exception: {
        "message": "An unexpected error occurred. The bot administrators have been notified.",
        "log_level": logging.ERROR,
        "ephemeral": True
    }
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
        additional_context="During image processing",
        guild_id=guild_id,      # Optional: guild where error occurred
        channel_id=channel_id   # Optional: channel where error occurred
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

### 6. Be Mindful of Sensitive Information

Never include sensitive information in error messages that will be shown to users:

```python
# Instead of:
raise DatabaseError(f"Connection failed: {connection_string}")

# Use:
raise DatabaseError("Database connection failed. Please try again later.")
```

The error handling system will automatically sanitize messages, but it's best practice to avoid including sensitive data in the first place.

By following these guidelines, you'll contribute to a more robust and user-friendly bot experience.

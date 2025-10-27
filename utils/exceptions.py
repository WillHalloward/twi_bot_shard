"""Custom exception hierarchy for Cognita bot.

This module defines a hierarchy of custom exceptions for standardized error handling
throughout the bot. These exceptions are designed to be caught and handled consistently
in command handlers and middleware.
"""


class CognitaError(Exception):
    """Base exception for all bot errors."""

    def __init__(self, message: str = "An error occurred", *args, **kwargs) -> None:
        self.message = message
        super().__init__(message, *args, **kwargs)


# Input Validation Errors


class UserInputError(CognitaError):
    """Errors caused by invalid user input."""

    def __init__(self, message: str = "Invalid user input", *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)


class ValidationError(UserInputError):
    """Errors caused by input validation failures."""

    def __init__(self, field: str = None, message: str = None, *args, **kwargs) -> None:
        self.field = field
        if field and not message:
            message = f"Invalid value for {field}"
        elif not message:
            message = "Validation failed"
        super().__init__(message, *args, **kwargs)


class FormatError(UserInputError):
    """Errors caused by incorrectly formatted input."""

    def __init__(
        self, expected_format: str = None, message: str = None, *args, **kwargs
    ) -> None:
        self.expected_format = expected_format
        if expected_format and not message:
            message = f"Input has incorrect format. Expected: {expected_format}"
        elif not message:
            message = "Input has incorrect format"
        super().__init__(message, *args, **kwargs)


# External Service Errors


class ExternalServiceError(CognitaError):
    """Errors from external services (Twitter, AO3, etc.)."""

    def __init__(
        self,
        service_name: str = "external service",
        message: str = None,
        *args,
        **kwargs,
    ) -> None:
        self.service_name = service_name
        if message is None:
            message = f"Error communicating with {service_name}"
        super().__init__(message, *args, **kwargs)


class APIError(ExternalServiceError):
    """Errors from API calls."""

    def __init__(
        self,
        service_name: str = "API",
        status_code: int = None,
        response_body: str = None,
        message: str = None,
        *args,
        **kwargs,
    ) -> None:
        self.status_code = status_code
        self.response_body = response_body

        if status_code and not message:
            message = f"API returned status code {status_code}"

        super().__init__(service_name, message, *args, **kwargs)


class ServiceUnavailableError(ExternalServiceError):
    """Errors when an external service is unavailable."""

    def __init__(
        self,
        service_name: str = "external service",
        message: str = None,
        *args,
        **kwargs,
    ) -> None:
        if not message:
            message = f"{service_name} is currently unavailable"
        super().__init__(service_name, message, *args, **kwargs)


# Permission Errors


class PermissionError(CognitaError):
    """Errors related to permissions."""

    def __init__(
        self,
        message: str = "You don't have permission to perform this action",
        *args,
        **kwargs,
    ) -> None:
        super().__init__(message, *args, **kwargs)


class RolePermissionError(PermissionError):
    """Errors related to role-based permissions."""

    def __init__(self, required_role: str = None, message: str = None, *args, **kwargs) -> None:
        self.required_role = required_role
        if required_role and not message:
            message = f"This action requires the {required_role} role"
        super().__init__(message, *args, **kwargs)


class OwnerOnlyError(PermissionError):
    """Errors for commands that can only be used by the bot owner."""

    def __init__(
        self,
        message: str = "This command can only be used by the bot owner",
        *args,
        **kwargs,
    ) -> None:
        super().__init__(message, *args, **kwargs)


# Resource Errors


class ResourceNotFoundError(CognitaError):
    """Errors when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str = "resource",
        resource_id: str | None = None,
        *args,
        **kwargs,
    ) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id

        if resource_id:
            message = f"{resource_type.capitalize()} with ID {resource_id} not found"
        else:
            message = f"{resource_type.capitalize()} not found"

        super().__init__(message, *args, **kwargs)


class ResourceAlreadyExistsError(CognitaError):
    """Errors when attempting to create a resource that already exists."""

    def __init__(
        self,
        resource_type: str = "resource",
        resource_id: str | None = None,
        *args,
        **kwargs,
    ) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id

        if resource_id:
            message = (
                f"{resource_type.capitalize()} with ID {resource_id} already exists"
            )
        else:
            message = f"{resource_type.capitalize()} already exists"

        super().__init__(message, *args, **kwargs)


class ResourceInUseError(CognitaError):
    """Errors when attempting to modify or delete a resource that is in use."""

    def __init__(
        self,
        resource_type: str = "resource",
        resource_id: str | None = None,
        *args,
        **kwargs,
    ) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id

        if resource_id:
            message = f"{resource_type.capitalize()} with ID {resource_id} is currently in use"
        else:
            message = f"{resource_type.capitalize()} is currently in use"

        super().__init__(message, *args, **kwargs)


# Configuration Errors


class ConfigurationError(CognitaError):
    """Errors related to bot configuration."""

    def __init__(self, message: str = "Bot configuration error", *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)


class MissingConfigurationError(ConfigurationError):
    """Errors when a required configuration value is missing."""

    def __init__(self, config_key: str = None, message: str = None, *args, **kwargs) -> None:
        self.config_key = config_key
        if config_key and not message:
            message = f"Missing required configuration value: {config_key}"
        super().__init__(message, *args, **kwargs)


class InvalidConfigurationError(ConfigurationError):
    """Errors when a configuration value is invalid."""

    def __init__(self, config_key: str = None, message: str = None, *args, **kwargs) -> None:
        self.config_key = config_key
        if config_key and not message:
            message = f"Invalid configuration value for: {config_key}"
        super().__init__(message, *args, **kwargs)


# Rate Limiting Errors


class RateLimitError(CognitaError):
    """Errors related to rate limiting."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        *args,
        **kwargs,
    ) -> None:
        self.retry_after = retry_after
        if retry_after:
            message = f"{message}. Try again in {retry_after:.1f} seconds"
        super().__init__(message, *args, **kwargs)


class CommandCooldownError(RateLimitError):
    """Errors when a command is on cooldown."""

    def __init__(
        self,
        command_name: str = None,
        retry_after: float | None = None,
        *args,
        **kwargs,
    ) -> None:
        self.command_name = command_name
        message = "Command is on cooldown"
        if command_name:
            message = f"Command '{command_name}' is on cooldown"
        super().__init__(message, retry_after, *args, **kwargs)


# Database Errors


class DatabaseError(CognitaError):
    """Errors related to database operations."""

    def __init__(self, message: str = "Database operation failed", *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)


class QueryError(DatabaseError):
    """Errors related to database queries."""

    def __init__(self, query: str = None, message: str = None, *args, **kwargs) -> None:
        self.query = query
        if not message:
            message = "Database query failed"
        super().__init__(message, *args, **kwargs)


class ConnectionError(DatabaseError):
    """Errors related to database connections."""

    def __init__(self, message: str = "Failed to connect to database", *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)


class TransactionError(DatabaseError):
    """Errors related to database transactions."""

    def __init__(self, message: str = "Database transaction failed", *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)


# Discord-specific Errors


class DiscordError(CognitaError):
    """Errors related to Discord API operations."""

    def __init__(self, message: str = "Discord API operation failed", *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)


class MessageError(DiscordError):
    """Errors related to message operations."""

    def __init__(self, message: str = "Failed to process message", *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)


class ChannelError(DiscordError):
    """Errors related to channel operations."""

    def __init__(
        self, channel_id: int | None = None, message: str = None, *args, **kwargs
    ) -> None:
        self.channel_id = channel_id
        if channel_id and not message:
            message = f"Failed to perform operation in channel {channel_id}"
        elif not message:
            message = "Failed to perform channel operation"
        super().__init__(message, *args, **kwargs)


class GuildError(DiscordError):
    """Errors related to guild operations."""

    def __init__(
        self, guild_id: int | None = None, message: str = None, *args, **kwargs
    ) -> None:
        self.guild_id = guild_id
        if guild_id and not message:
            message = f"Failed to perform operation in guild {guild_id}"
        elif not message:
            message = "Failed to perform guild operation"
        super().__init__(message, *args, **kwargs)

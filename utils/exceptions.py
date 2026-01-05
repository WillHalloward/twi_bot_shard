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

    def __init__(
        self, required_role: str = None, message: str = None, *args, **kwargs
    ) -> None:
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


# Database Errors


class DatabaseError(CognitaError):
    """Errors related to database operations."""

    def __init__(
        self, message: str = "Database operation failed", *args, **kwargs
    ) -> None:
        super().__init__(message, *args, **kwargs)


class QueryError(DatabaseError):
    """Errors related to database queries."""

    def __init__(self, query: str = None, message: str = None, *args, **kwargs) -> None:
        self.query = query
        if not message:
            message = "Database query failed"
        super().__init__(message, *args, **kwargs)

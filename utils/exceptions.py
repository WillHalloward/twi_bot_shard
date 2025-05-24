"""
Custom exception hierarchy for Cognita bot.

This module defines a hierarchy of custom exceptions for standardized error handling
throughout the bot. These exceptions are designed to be caught and handled consistently
in command handlers and middleware.
"""

import logging
from typing import Optional


class CognitaError(Exception):
    """Base exception for all bot errors."""
    
    def __init__(self, message: str = "An error occurred", *args, **kwargs):
        self.message = message
        super().__init__(message, *args, **kwargs)


class UserInputError(CognitaError):
    """Errors caused by invalid user input."""
    
    def __init__(self, message: str = "Invalid user input", *args, **kwargs):
        super().__init__(message, *args, **kwargs)


class ExternalServiceError(CognitaError):
    """Errors from external services (Twitter, AO3, etc.)."""
    
    def __init__(self, service_name: str = "external service", message: str = None, *args, **kwargs):
        self.service_name = service_name
        if message is None:
            message = f"Error communicating with {service_name}"
        super().__init__(message, *args, **kwargs)


class PermissionError(CognitaError):
    """Errors related to permissions."""
    
    def __init__(self, message: str = "You don't have permission to perform this action", *args, **kwargs):
        super().__init__(message, *args, **kwargs)


class ResourceNotFoundError(CognitaError):
    """Errors when a requested resource is not found."""
    
    def __init__(self, resource_type: str = "resource", resource_id: Optional[str] = None, *args, **kwargs):
        self.resource_type = resource_type
        self.resource_id = resource_id
        
        if resource_id:
            message = f"{resource_type.capitalize()} with ID {resource_id} not found"
        else:
            message = f"{resource_type.capitalize()} not found"
            
        super().__init__(message, *args, **kwargs)


class ConfigurationError(CognitaError):
    """Errors related to bot configuration."""
    
    def __init__(self, message: str = "Bot configuration error", *args, **kwargs):
        super().__init__(message, *args, **kwargs)


class RateLimitError(CognitaError):
    """Errors related to rate limiting."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[float] = None, *args, **kwargs):
        self.retry_after = retry_after
        if retry_after:
            message = f"{message}. Try again in {retry_after:.1f} seconds"
        super().__init__(message, *args, **kwargs)


class DatabaseError(CognitaError):
    """Errors related to database operations.
    
    This is a wrapper around the existing DatabaseError in utils.db to maintain
    compatibility while integrating with the new exception hierarchy.
    """
    
    def __init__(self, message: str = "Database operation failed", *args, **kwargs):
        super().__init__(message, *args, **kwargs)
"""
Common patterns and utilities for reducing code duplication across cogs.

This module provides consolidated utilities for:
- Database operation error handling
- Parameter validation
- Logging patterns
- Common error responses

These utilities help maintain consistency and reduce code duplication
across the bot's cogs while following the project's style guidelines.
"""

import logging
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from functools import wraps
import asyncpg
import discord
from discord import Interaction

from utils.exceptions import DatabaseError, ValidationError, QueryError


T = TypeVar("T")


class CommonPatterns:
    """
    Utility class providing common patterns for cog operations.

    This class contains static methods that encapsulate frequently used
    patterns across cogs, reducing code duplication and ensuring consistency.
    """

    @staticmethod
    async def safe_db_query(
        db_operation: Callable,
        operation_name: str,
        user_id: int,
        logger: logging.Logger,
        error_message: str = "Database operation failed",
    ) -> Any:
        """
        Safely execute a database operation with consistent error handling.

        Args:
            db_operation: The database operation to execute (async callable)
            operation_name: Name of the operation for logging
            user_id: ID of the user performing the operation
            logger: Logger instance for error logging
            error_message: Custom error message for DatabaseError

        Returns:
            The result of the database operation

        Raises:
            DatabaseError: If the database operation fails
        """
        try:
            return await db_operation()
        except asyncpg.PostgresError as e:
            logger.error(
                f"Database error in {operation_name}: {e}",
                extra={
                    "operation": operation_name,
                    "user_id": user_id,
                    "error_type": "postgres_error",
                },
            )
            raise DatabaseError(f"{error_message}: {e}") from e
        except Exception as e:
            logger.error(
                f"Unexpected error in {operation_name}: {e}",
                extra={
                    "operation": operation_name,
                    "user_id": user_id,
                    "error_type": "unexpected_error",
                },
            )
            raise DatabaseError(f"{error_message}: Unexpected error occurred") from e

    @staticmethod
    def validate_positive_number(
        value: Union[int, float],
        field_name: str,
        max_value: Optional[Union[int, float]] = None,
        min_value: Union[int, float] = 1,
    ) -> None:
        """
        Validate that a number is positive and within bounds.

        Args:
            value: The value to validate
            field_name: Name of the field for error messages
            max_value: Maximum allowed value (optional)
            min_value: Minimum allowed value (default: 1)

        Raises:
            ValidationError: If validation fails
        """
        if value < min_value:
            raise ValidationError(
                field=field_name,
                message=f"{field_name.capitalize()} must be at least {min_value}",
            )

        if max_value is not None and value > max_value:
            raise ValidationError(
                field=field_name,
                message=f"{field_name.capitalize()} cannot exceed {max_value}",
            )

    @staticmethod
    def validate_string_length(
        value: str,
        field_name: str,
        max_length: int,
        min_length: int = 1,
        allow_empty: bool = False,
    ) -> None:
        """
        Validate string length and content.

        Args:
            value: The string to validate
            field_name: Name of the field for error messages
            max_length: Maximum allowed length
            min_length: Minimum allowed length (default: 1)
            allow_empty: Whether to allow empty strings (default: False)

        Raises:
            ValidationError: If validation fails
        """
        if not allow_empty and not value.strip():
            raise ValidationError(
                field=field_name, message=f"{field_name.capitalize()} cannot be empty"
            )

        if len(value) < min_length:
            raise ValidationError(
                field=field_name,
                message=f"{field_name.capitalize()} must be at least {min_length} characters",
            )

        if len(value) > max_length:
            raise ValidationError(
                field=field_name,
                message=f"{field_name.capitalize()} cannot exceed {max_length} characters",
            )

    @staticmethod
    def log_command_execution(
        command_name: str,
        user_id: int,
        user_name: str,
        logger: logging.Logger,
        additional_info: Optional[str] = None,
        **extra_fields,
    ) -> None:
        """
        Log command execution with consistent format.

        Args:
            command_name: Name of the command being executed
            user_id: ID of the user executing the command
            user_name: Display name of the user
            logger: Logger instance
            additional_info: Additional information to include
            **extra_fields: Additional fields for structured logging
        """
        log_message = f"{command_name.upper()}: Executed by {user_name} ({user_id})"
        if additional_info:
            log_message += f" - {additional_info}"

        extra = {
            "command": command_name.lower(),
            "user_id": user_id,
            "user_name": user_name,
            **extra_fields,
        }

        logger.info(log_message, extra=extra)

    @staticmethod
    def log_command_error(
        command_name: str,
        user_id: int,
        error: Exception,
        logger: logging.Logger,
        additional_context: Optional[str] = None,
        **extra_fields,
    ) -> None:
        """
        Log command errors with consistent format.

        Args:
            command_name: Name of the command that failed
            user_id: ID of the user who triggered the error
            error: The exception that occurred
            logger: Logger instance
            additional_context: Additional context about the error
            **extra_fields: Additional fields for structured logging
        """
        log_message = (
            f"{command_name.upper()} ERROR: {type(error).__name__}: {str(error)}"
        )
        if additional_context:
            log_message += f" - {additional_context}"

        extra = {
            "command": command_name.lower(),
            "user_id": user_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            **extra_fields,
        }

        logger.error(log_message, extra=extra)

    @staticmethod
    async def send_error_response(
        interaction: Interaction, title: str, message: str, ephemeral: bool = True
    ) -> None:
        """
        Send a consistent error response to the user.

        Args:
            interaction: The Discord interaction
            title: Title for the error embed
            message: Error message to display
            ephemeral: Whether the response should be ephemeral
        """
        embed = discord.Embed(
            title=f"❌ {title}", description=message, color=discord.Color.red()
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(
                    embed=embed, ephemeral=ephemeral
                )
        except discord.HTTPException:
            # Fallback to simple text if embed fails
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"❌ {title}: {message}", ephemeral=ephemeral
                    )
                else:
                    await interaction.response.send_message(
                        f"❌ {title}: {message}", ephemeral=ephemeral
                    )
            except discord.HTTPException:
                # If all else fails, log the error
                logging.getLogger(__name__).error(
                    f"Failed to send error response: {title} - {message}",
                    extra={"user_id": interaction.user.id},
                )

    @staticmethod
    def create_success_embed(
        title: str,
        description: str,
        fields: Optional[Dict[str, Any]] = None,
        color: discord.Color = discord.Color.green(),
    ) -> discord.Embed:
        """
        Create a consistent success embed.

        Args:
            title: Title for the embed
            description: Description for the embed
            fields: Optional dictionary of field names to values
            color: Color for the embed (default: green)

        Returns:
            Configured Discord embed
        """
        embed = discord.Embed(title=f"✅ {title}", description=description, color=color)

        if fields:
            for name, value in fields.items():
                inline = isinstance(value, dict) and value.get("inline", False)
                field_value = (
                    value.get("value", value) if isinstance(value, dict) else value
                )
                embed.add_field(name=name, value=str(field_value), inline=inline)

        return embed


def with_db_error_handling(
    operation_name: str, error_message: str = "Operation failed"
):
    """
    Decorator for consistent database error handling.

    Args:
        operation_name: Name of the operation for logging
        error_message: Custom error message for failures

    Returns:
        Decorated function with error handling
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: Interaction, *args, **kwargs):
            logger = getattr(self, "logger", logging.getLogger(self.__class__.__name__))

            try:
                return await func(self, interaction, *args, **kwargs)
            except (ValidationError, DatabaseError, QueryError):
                # Re-raise our custom exceptions to be handled by the global handler
                raise
            except Exception as e:
                CommonPatterns.log_command_error(
                    operation_name, interaction.user.id, e, logger
                )
                raise DatabaseError(f"{error_message}: {str(e)}") from e

        return wrapper

    return decorator


def with_parameter_validation(**validators):
    """
    Decorator for parameter validation using common patterns.

    Args:
        **validators: Dictionary of parameter names to validation functions

    Returns:
        Decorated function with parameter validation
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: Interaction, *args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, interaction, *args, **kwargs)
            bound_args.apply_defaults()

            # Validate parameters
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    validator(bound_args.arguments[param_name])

            return await func(self, interaction, *args, **kwargs)

        return wrapper

    return decorator

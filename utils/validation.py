"""
Input validation utilities for Twi Bot Shard.

This module provides utilities for validating and sanitizing user inputs,
including command parameters, database inputs, and common data patterns.
"""

import re
import html
import json
import logging
import unicodedata
from datetime import datetime
from enum import Enum, auto
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

import discord
from discord import app_commands
from discord.ext import commands

from utils.exceptions import ValidationError

logger = logging.getLogger("validation")

# Type variables for generic functions
T = TypeVar("T")
CommandT = TypeVar("CommandT", bound=Callable)


class ValidationLevel(Enum):
    """Validation level for input validation."""

    STRICT = auto()  # Reject any input that doesn't match the expected format
    MODERATE = auto()  # Allow some flexibility but sanitize the input
    LENIENT = auto()  # Accept most inputs but sanitize heavily


# Basic validation functions


def validate_string(
    value: Any,
    min_length: int = 0,
    max_length: Optional[int] = None,
    pattern: Optional[Pattern] = None,
    strip: bool = True,
    allow_empty: bool = False,
    error_message: Optional[str] = None,
) -> str:
    """
    Validate a string value.

    Args:
        value: The value to validate
        min_length: Minimum length of the string
        max_length: Maximum length of the string
        pattern: Regular expression pattern the string must match
        strip: Whether to strip whitespace from the string
        allow_empty: Whether to allow empty strings
        error_message: Custom error message to use if validation fails

    Returns:
        The validated string

    Raises:
        ValidationError: If the value is not a valid string
    """
    if value is None:
        if not allow_empty:
            raise ValidationError(error_message or "Value cannot be None")
        return ""

    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            raise ValidationError(
                error_message or f"Expected string, got {type(value).__name__}"
            )

    if strip:
        value = value.strip()

    if not allow_empty and not value:
        raise ValidationError(error_message or "Value cannot be empty")

    if min_length > 0 and len(value) < min_length:
        raise ValidationError(
            error_message or f"Value must be at least {min_length} characters long"
        )

    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            error_message or f"Value cannot be longer than {max_length} characters"
        )

    if pattern is not None and not pattern.match(value):
        raise ValidationError(
            error_message or "Value does not match the required pattern"
        )

    return value


def validate_integer(
    value: Any,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    error_message: Optional[str] = None,
) -> int:
    """
    Validate an integer value.

    Args:
        value: The value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        error_message: Custom error message to use if validation fails

    Returns:
        The validated integer

    Raises:
        ValidationError: If the value is not a valid integer
    """
    if value is None:
        raise ValidationError(error_message or "Value cannot be None")

    try:
        if isinstance(value, str):
            value = value.strip()
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValidationError(
            error_message or f"Expected integer, got {type(value).__name__}"
        )

    if min_value is not None and int_value < min_value:
        raise ValidationError(error_message or f"Value must be at least {min_value}")

    if max_value is not None and int_value > max_value:
        raise ValidationError(
            error_message or f"Value cannot be greater than {max_value}"
        )

    return int_value


def validate_float(
    value: Any,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    error_message: Optional[str] = None,
) -> float:
    """
    Validate a float value.

    Args:
        value: The value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        error_message: Custom error message to use if validation fails

    Returns:
        The validated float

    Raises:
        ValidationError: If the value is not a valid float
    """
    if value is None:
        raise ValidationError(error_message or "Value cannot be None")

    try:
        if isinstance(value, str):
            value = value.strip()
        float_value = float(value)
    except (ValueError, TypeError):
        raise ValidationError(
            error_message or f"Expected float, got {type(value).__name__}"
        )

    if min_value is not None and float_value < min_value:
        raise ValidationError(error_message or f"Value must be at least {min_value}")

    if max_value is not None and float_value > max_value:
        raise ValidationError(
            error_message or f"Value cannot be greater than {max_value}"
        )

    return float_value


def validate_boolean(value: Any, error_message: Optional[str] = None) -> bool:
    """
    Validate a boolean value.

    Args:
        value: The value to validate
        error_message: Custom error message to use if validation fails

    Returns:
        The validated boolean

    Raises:
        ValidationError: If the value is not a valid boolean
    """
    if value is None:
        raise ValidationError(error_message or "Value cannot be None")

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        value = value.strip().lower()
        if value in ("true", "yes", "y", "1", "on"):
            return True
        if value in ("false", "no", "n", "0", "off"):
            return False

    raise ValidationError(
        error_message or f"Expected boolean, got {type(value).__name__}"
    )


def validate_date(
    value: Any,
    min_date: Optional[datetime] = None,
    max_date: Optional[datetime] = None,
    formats: List[str] = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"],
    error_message: Optional[str] = None,
) -> datetime:
    """
    Validate a date value.

    Args:
        value: The value to validate
        min_date: Minimum allowed date
        max_date: Maximum allowed date
        formats: List of date formats to try
        error_message: Custom error message to use if validation fails

    Returns:
        The validated date as a datetime object

    Raises:
        ValidationError: If the value is not a valid date
    """
    if value is None:
        raise ValidationError(error_message or "Value cannot be None")

    if isinstance(value, datetime):
        date_value = value
    elif isinstance(value, str):
        value = value.strip()

        # Try each format
        for fmt in formats:
            try:
                date_value = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            # No format matched
            raise ValidationError(
                error_message
                or f"Date must be in one of these formats: {', '.join(formats)}"
            )
    else:
        raise ValidationError(
            error_message or f"Expected date, got {type(value).__name__}"
        )

    if min_date is not None and date_value < min_date:
        raise ValidationError(
            error_message or f"Date must be on or after {min_date.strftime('%Y-%m-%d')}"
        )

    if max_date is not None and date_value > max_date:
        raise ValidationError(
            error_message
            or f"Date must be on or before {max_date.strftime('%Y-%m-%d')}"
        )

    return date_value


def validate_choice(
    value: Any,
    choices: List[T],
    case_sensitive: bool = False,
    error_message: Optional[str] = None,
) -> T:
    """
    Validate that a value is one of the allowed choices.

    Args:
        value: The value to validate
        choices: List of allowed choices
        case_sensitive: Whether string comparison should be case-sensitive
        error_message: Custom error message to use if validation fails

    Returns:
        The validated choice

    Raises:
        ValidationError: If the value is not one of the allowed choices
    """
    if value is None:
        raise ValidationError(error_message or "Value cannot be None")

    # Direct comparison
    if value in choices:
        return value

    # Case-insensitive string comparison
    if isinstance(value, str) and not case_sensitive:
        value_lower = value.lower()
        for choice in choices:
            if isinstance(choice, str) and choice.lower() == value_lower:
                return choice

    # Format choices for error message
    if all(isinstance(c, str) for c in choices):
        choices_str = ", ".join(f"'{c}'" for c in choices)
    else:
        choices_str = ", ".join(str(c) for c in choices)

    raise ValidationError(error_message or f"Value must be one of: {choices_str}")


# Pattern validation functions


def validate_email(value: Any, error_message: Optional[str] = None) -> str:
    """
    Validate an email address.

    Args:
        value: The value to validate
        error_message: Custom error message to use if validation fails

    Returns:
        The validated email address

    Raises:
        ValidationError: If the value is not a valid email address
    """
    if value is None:
        raise ValidationError(error_message or "Email cannot be None")

    if not isinstance(value, str):
        raise ValidationError(
            error_message or f"Expected string, got {type(value).__name__}"
        )

    value = value.strip()

    # Simple email pattern
    pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    if not pattern.match(value):
        raise ValidationError(error_message or "Invalid email address format")

    return value


def validate_url(
    value: Any,
    allowed_schemes: List[str] = ["http", "https"],
    error_message: Optional[str] = None,
) -> str:
    """
    Validate a URL.

    Args:
        value: The value to validate
        allowed_schemes: List of allowed URL schemes
        error_message: Custom error message to use if validation fails

    Returns:
        The validated URL

    Raises:
        ValidationError: If the value is not a valid URL
    """
    if value is None:
        raise ValidationError(error_message or "URL cannot be None")

    if not isinstance(value, str):
        raise ValidationError(
            error_message or f"Expected string, got {type(value).__name__}"
        )

    value = value.strip()

    # URL pattern with scheme capture group
    pattern = re.compile(
        r"^(https?|ftp)://(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    match = pattern.match(value)
    if not match:
        raise ValidationError(error_message or "Invalid URL format")

    scheme = match.group(1).lower()
    if scheme not in allowed_schemes:
        raise ValidationError(
            error_message or f"URL scheme must be one of: {', '.join(allowed_schemes)}"
        )

    return value


def validate_discord_id(value: Any, error_message: Optional[str] = None) -> int:
    """
    Validate a Discord ID (user, channel, guild, etc.).

    Args:
        value: The value to validate
        error_message: Custom error message to use if validation fails

    Returns:
        The validated Discord ID as an integer

    Raises:
        ValidationError: If the value is not a valid Discord ID
    """
    try:
        if isinstance(value, str):
            # Remove mention format if present
            value = value.strip()
            if value.startswith("<@") and value.endswith(">"):
                value = value[2:-1]
            if value.startswith("!"):
                value = value[1:]

        id_value = int(value)

        # Discord IDs are snowflakes, which are 64-bit integers
        if id_value < 0 or id_value >= (1 << 64):
            raise ValidationError(error_message or "Discord ID out of valid range")

        return id_value
    except (ValueError, TypeError):
        raise ValidationError(error_message or "Invalid Discord ID format")


# Database input sanitization


def sanitize_string(
    value: str, level: ValidationLevel = ValidationLevel.MODERATE
) -> str:
    """
    Sanitize a string for safe use in database operations.

    Args:
        value: The string to sanitize
        level: The validation level to apply

    Returns:
        The sanitized string
    """
    if value is None:
        return ""

    if not isinstance(value, str):
        value = str(value)

    # Basic sanitization
    value = value.strip()

    if level == ValidationLevel.STRICT:
        # Allow only alphanumeric and basic punctuation
        value = re.sub(r"[^\w\s.,;:!?()-]", "", value)
    elif level == ValidationLevel.MODERATE:
        # HTML escape special characters
        value = html.escape(value)
    else:  # LENIENT
        # Normalize Unicode and remove control characters
        value = unicodedata.normalize("NFKC", value)
        value = "".join(c for c in value if not unicodedata.category(c).startswith("C"))

    return value


def sanitize_sql_identifier(value: str) -> str:
    """
    Sanitize a SQL identifier (table name, column name, etc.).

    Args:
        value: The identifier to sanitize

    Returns:
        The sanitized identifier
    """
    if value is None:
        raise ValueError("SQL identifier cannot be None")

    if not isinstance(value, str):
        value = str(value)

    # Allow only alphanumeric and underscore
    value = re.sub(r"[^\w]", "", value)

    # Ensure it doesn't start with a number
    if value and value[0].isdigit():
        value = "i_" + value

    if not value:
        raise ValueError("SQL identifier cannot be empty after sanitization")

    return value


def sanitize_json(value: Any) -> str:
    """
    Sanitize a value for use in JSON.

    Args:
        value: The value to sanitize

    Returns:
        The sanitized JSON string
    """
    try:
        # Ensure the value can be serialized to JSON
        json_str = json.dumps(value)
        return json_str
    except (TypeError, ValueError):
        # If serialization fails, convert to string and try again
        try:
            return json.dumps(str(value))
        except Exception:
            return json.dumps(None)


# Validation decorators


def validate_command_params(**param_validators: Dict[str, Callable[[Any], Any]]):
    """
    Decorator for validating command parameters.

    Args:
        **param_validators: Mapping of parameter names to validator functions

    Returns:
        Decorated command function
    """

    def decorator(command_func: CommandT) -> CommandT:
        @wraps(command_func)
        async def wrapper(*args, **kwargs):
            # Extract context from args
            ctx = args[0] if len(args) > 0 else None

            # Validate each parameter
            for param_name, validator in param_validators.items():
                if param_name in kwargs:
                    try:
                        kwargs[param_name] = validator(kwargs[param_name])
                    except ValidationError as e:
                        if ctx and hasattr(ctx, "send"):
                            await ctx.send(f"Invalid {param_name}: {e}")
                            return
                        raise

            return await command_func(*args, **kwargs)

        return cast(CommandT, wrapper)

    return decorator


def validate_interaction_params(**param_validators: Dict[str, Callable[[Any], Any]]):
    """
    Decorator for validating app command interaction parameters.

    Args:
        **param_validators: Mapping of parameter names to validator functions

    Returns:
        Decorated command function
    """

    def decorator(command_func: CommandT) -> CommandT:
        @wraps(command_func)
        async def wrapper(self, interaction: discord.Interaction, **kwargs):
            # Validate each parameter
            for param_name, validator in param_validators.items():
                if param_name in kwargs:
                    try:
                        kwargs[param_name] = validator(kwargs[param_name])
                    except ValidationError as e:
                        await interaction.response.send_message(
                            f"Invalid {param_name}: {e}", ephemeral=True
                        )
                        return

            return await command_func(self, interaction, **kwargs)

        return cast(CommandT, wrapper)

    return decorator


# Utility functions


def create_validator(validator_func: Callable, *args, **kwargs) -> Callable[[Any], Any]:
    """
    Create a validator function with pre-configured parameters.

    Args:
        validator_func: The validator function to use
        *args: Positional arguments to pass to the validator
        **kwargs: Keyword arguments to pass to the validator

    Returns:
        A configured validator function
    """

    def validator(value: Any) -> Any:
        return validator_func(value, *args, **kwargs)

    return validator


def validate_batch(
    values: Dict[str, Any], validators: Dict[str, Callable[[Any], Any]]
) -> Dict[str, Any]:
    """
    Validate multiple values at once.

    Args:
        values: Dictionary of values to validate
        validators: Dictionary of validator functions

    Returns:
        Dictionary of validated values

    Raises:
        ValidationError: If any value fails validation
    """
    errors = {}
    validated = {}

    for key, validator in validators.items():
        if key in values:
            try:
                validated[key] = validator(values[key])
            except ValidationError as e:
                errors[key] = str(e)

    if errors:
        error_messages = [f"{key}: {message}" for key, message in errors.items()]
        raise ValidationError(f"Validation failed: {', '.join(error_messages)}")

    return validated

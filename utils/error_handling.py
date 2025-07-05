"""
Error handling utilities for Cognita bot.

This module provides utilities for standardized error handling across the bot,
including decorators for command handlers and functions for error telemetry.
It also includes security-focused error handling to prevent information disclosure.
"""

import functools
import logging
import traceback
import datetime
import re
import sys
import json
from typing import (
    Callable,
    TypeVar,
    Optional,
    Any,
    Coroutine,
    Dict,
    Type,
    Union,
    List,
    Pattern,
    Set,
)

import discord
from discord.ext import commands

from utils.exceptions import (
    # Base exception
    CognitaError,
    # Input validation errors
    UserInputError,
    ValidationError,
    FormatError,
    # External service errors
    ExternalServiceError,
    APIError,
    ServiceUnavailableError,
    # Permission errors
    PermissionError,
    RolePermissionError,
    OwnerOnlyError,
    # Resource errors
    ResourceNotFoundError,
    ResourceAlreadyExistsError,
    ResourceInUseError,
    # Configuration errors
    ConfigurationError,
    MissingConfigurationError,
    InvalidConfigurationError,
    # Rate limiting errors
    RateLimitError,
    CommandCooldownError,
    # Database errors
    DatabaseError,
    QueryError,
    ConnectionError,
    TransactionError,
    # Discord-specific errors
    DiscordError,
    MessageError,
    ChannelError,
    GuildError,
)

T = TypeVar("T")
CommandT = TypeVar("CommandT", bound=Callable[..., Coroutine[Any, Any, Any]])

logger = logging.getLogger("error_handling")


def _extract_command_params(interaction: discord.Interaction, command) -> dict:
    """
    Extract command parameters from interaction data.

    Args:
        interaction: The Discord interaction
        command: The app command object

    Returns:
        dict: Dictionary of parameter names to values
    """
    params = {}

    # Get the options from the interaction data
    options = interaction.data.get("options", [])

    # Convert options list to a dictionary
    for option in options:
        params[option["name"]] = option["value"]

    return params


# Patterns for sensitive information that should be redacted
SENSITIVE_PATTERNS: List[Pattern] = [
    # API keys and tokens
    re.compile(
        r'(api[_-]?key|token|secret|password|auth)[=:]\s*["\'`]?([a-zA-Z0-9_\-\.]{20,})["\'`]?',
        re.IGNORECASE,
    ),
    # Discord tokens
    re.compile(r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}"),
    # Database connection strings
    re.compile(r"(postgres|mysql|mongodb|redis)://[^\s]+", re.IGNORECASE),
    # IP addresses
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    # Email addresses
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    # File paths
    re.compile(r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*'),
    re.compile(r"/(?:[^/]+/)*[^/]+"),
    # JSON web tokens
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
]

# Error types that should have sanitized messages
SENSITIVE_ERROR_TYPES: Set[Type[Exception]] = {
    DatabaseError,
    QueryError,
    ConnectionError,
    TransactionError,
    ConfigurationError,
    MissingConfigurationError,
    InvalidConfigurationError,
    APIError,
    ExternalServiceError,
}


# Security levels for error messages
class ErrorSecurityLevel:
    """Security levels for error messages."""

    # Show detailed error information (for developers)
    DEBUG = 0
    # Show general error information (for trusted users)
    NORMAL = 1
    # Show minimal error information (for all users)
    SECURE = 2


def detect_sensitive_info(text: str) -> bool:
    """
    Detect if a string contains sensitive information.

    Args:
        text: The text to check

    Returns:
        True if sensitive information is detected, False otherwise
    """
    if not text:
        return False

    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return True

    return False


def redact_sensitive_info(text: str) -> str:
    """
    Redact sensitive information from a string.

    Args:
        text: The text to redact

    Returns:
        The redacted text
    """
    if not text:
        return text

    redacted_text = text

    for pattern in SENSITIVE_PATTERNS:
        try:
            # Try to use the first capture group in the replacement
            redacted_text = pattern.sub(r"\1: [REDACTED]", redacted_text)
        except re.error:
            # If there's no capture group, replace the entire match
            redacted_text = pattern.sub("[REDACTED]", redacted_text)

    return redacted_text


def sanitize_error_message(
    error: Exception, security_level: int = ErrorSecurityLevel.NORMAL
) -> str:
    """
    Sanitize an error message to prevent information disclosure.

    Args:
        error: The exception to sanitize
        security_level: The security level to apply

    Returns:
        A sanitized error message
    """
    # Get the original error message
    error_type = type(error).__name__
    error_message = getattr(error, "message", str(error))

    # For debug level, just redact sensitive information
    if security_level == ErrorSecurityLevel.DEBUG:
        return f"{error_type}: {redact_sensitive_info(error_message)}"

    # For secure level or sensitive error types, use a generic message
    if (
        security_level == ErrorSecurityLevel.SECURE
        or type(error) in SENSITIVE_ERROR_TYPES
    ):
        return f"An error occurred. Please contact an administrator if this persists."

    # For normal level, check if the message contains sensitive information
    if detect_sensitive_info(error_message):
        # If it does, use a more generic message
        return f"{error_type} error occurred. Details have been logged."
    else:
        # If not, use the original message but ensure it's not too detailed
        # Limit the message length and remove any stack traces or technical details
        sanitized_message = error_message.split("\n")[0]  # Take only the first line
        if len(sanitized_message) > 100:
            sanitized_message = sanitized_message[:97] + "..."
        return sanitized_message


def get_detailed_error_context(
    error: Exception,
    command_name: str,
    user_id: int,
    guild_id: Optional[int] = None,
    channel_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Get detailed context information for an error for internal logging.

    Args:
        error: The exception that occurred
        command_name: Name of the command that caused the error
        user_id: ID of the user who triggered the error
        guild_id: Optional guild ID where the error occurred
        channel_id: Optional channel ID where the error occurred

    Returns:
        A dictionary with detailed error context
    """
    error_type = type(error).__name__
    error_message = getattr(error, "message", str(error))

    # Create a detailed context dictionary
    context = {
        "error_type": error_type,
        "error_message": error_message,
        "command_name": command_name,
        "user_id": user_id,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "traceback": None,
    }

    # Add traceback for non-CognitaError exceptions, but exclude CommandOnCooldown
    if not isinstance(error, CognitaError) and not isinstance(
        error,
        (commands.CommandOnCooldown, discord.app_commands.errors.CommandOnCooldown),
    ):
        context["traceback"] = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

    # Add additional context from the error if available
    if hasattr(error, "context") and isinstance(error.context, dict):
        context["additional_context"] = error.context

    return context


# Error response configuration
# Maps exception types to user-friendly messages and logging levels
ERROR_RESPONSES: Dict[Type[Exception], Dict[str, Any]] = {
    # Input validation errors
    UserInputError: {
        "message": "Invalid input: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    ValidationError: {
        "message": "Validation error: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    FormatError: {
        "message": "Format error: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    # External service errors
    ExternalServiceError: {
        "message": "External service error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    APIError: {
        "message": "API error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    ServiceUnavailableError: {
        "message": "Service unavailable: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    # Permission errors
    PermissionError: {
        "message": "Permission denied: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    RolePermissionError: {
        "message": "Role permission error: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    OwnerOnlyError: {
        "message": "Owner only: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    # Resource errors
    ResourceNotFoundError: {
        "message": "Not found: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    ResourceAlreadyExistsError: {
        "message": "Already exists: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    ResourceInUseError: {
        "message": "Resource in use: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    # Configuration errors
    ConfigurationError: {
        "message": "Configuration error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    MissingConfigurationError: {
        "message": "Missing configuration: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    InvalidConfigurationError: {
        "message": "Invalid configuration: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    # Rate limiting errors
    RateLimitError: {
        "message": "Rate limit exceeded: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    CommandCooldownError: {
        "message": "Command on cooldown: {error.message}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    # Database errors
    DatabaseError: {
        "message": "Database error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    QueryError: {
        "message": "Query error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    ConnectionError: {
        "message": "Database connection error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    TransactionError: {
        "message": "Transaction error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    # Discord-specific errors
    DiscordError: {
        "message": "Discord API error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    MessageError: {
        "message": "Message error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    ChannelError: {
        "message": "Channel error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    GuildError: {
        "message": "Guild error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    # Discord.py built-in errors
    commands.CommandNotFound: {
        "message": "Command not found. Use /help to see available commands.",
        "log_level": logging.INFO,
        "ephemeral": True,
    },
    commands.MissingRequiredArgument: {
        "message": "Missing required argument: {error.param.name}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    commands.BadArgument: {
        "message": "Invalid argument: {error}",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    commands.CheckFailure: {
        "message": "You don't have permission to use this command.",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    commands.CommandOnCooldown: {
        "message": "This command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
        "log_level": logging.INFO,
        "ephemeral": True,
    },
    discord.app_commands.errors.CommandOnCooldown: {
        "message": "Please wait {error.retry_after:.1f} seconds before using this command again.",
        "log_level": logging.WARNING,
        "ephemeral": True,
    },
    commands.NoPrivateMessage: {
        "message": "This command cannot be used in private messages.",
        "log_level": logging.INFO,
        "ephemeral": True,
    },
    commands.DisabledCommand: {
        "message": "This command is currently disabled.",
        "log_level": logging.INFO,
        "ephemeral": True,
    },
    # Fallback for any CognitaError not specifically handled
    CognitaError: {
        "message": "Error: {error.message}",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
    # Fallback for any Exception not specifically handled
    Exception: {
        "message": "An unexpected error occurred. The bot administrators have been notified.",
        "log_level": logging.ERROR,
        "ephemeral": True,
    },
}


def get_error_response(
    error: Exception, security_level: int = ErrorSecurityLevel.NORMAL
) -> Dict[str, Any]:
    """Get the appropriate error response configuration for an exception.

    Args:
        error: The exception to get the response for
        security_level: The security level to apply to the error message

    Returns:
        A dictionary with response configuration
    """
    # Find the most specific error type that matches
    for error_type, response in ERROR_RESPONSES.items():
        if isinstance(error, error_type):
            # Create a copy of the response to avoid modifying the original
            response_copy = response.copy()

            # Sanitize the message template if needed
            if "message" in response_copy:
                # Check if this is a sensitive error type
                if type(error) in SENSITIVE_ERROR_TYPES or detect_sensitive_info(
                    str(error)
                ):
                    # Use a sanitized message
                    response_copy["message"] = sanitize_error_message(
                        error, security_level
                    )
                    # Ensure the message is marked as already sanitized
                    response_copy["sanitized"] = True

            return response_copy

    # Fallback to generic error response
    return ERROR_RESPONSES[Exception].copy()


async def track_error(
    bot,
    error_type: str,
    command_name: str,
    user_id: int,
    error_message: str,
    guild_id: Optional[int] = None,
    channel_id: Optional[int] = None,
) -> int:
    """Record error in database for analysis.

    Args:
        bot: The bot instance
        error_type: Type of error
        command_name: Name of the command that caused the error
        user_id: ID of the user who triggered the error
        error_message: Error message
        guild_id: Optional guild ID where the error occurred
        channel_id: Optional channel ID where the error occurred

    Returns:
        The ID of the inserted error record
    """
    try:
        return await bot.db.fetchval(
            """
            INSERT INTO error_telemetry(
                error_type, command_name, user_id, error_message, 
                guild_id, channel_id, timestamp
            )
            VALUES($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            error_type,
            command_name,
            user_id,
            str(error_message),
            guild_id,
            channel_id,
            datetime.datetime.now(),
        )
    except Exception as e:
        logger.error(f"Failed to record error telemetry: {e}")
        return -1


def log_error(
    error: Exception,
    command_name: str,
    user_id: int,
    log_level: int = logging.ERROR,
    additional_context: str = "",
    guild_id: Optional[int] = None,
    channel_id: Optional[int] = None,
) -> None:
    """Log an error with standardized format.

    Args:
        error: The exception to log
        command_name: Name of the command that caused the error
        user_id: ID of the user who triggered the error
        log_level: Logging level to use
        additional_context: Any additional context to include in the log
        guild_id: Optional guild ID where the error occurred
        channel_id: Optional channel ID where the error occurred
    """
    error_type = type(error).__name__
    error_message = getattr(error, "message", str(error))

    # Create a basic log message for standard logging
    log_message = f"{error_type} in {command_name}: {redact_sensitive_info(error_message)} | User: {user_id}"
    if additional_context:
        log_message += f" | {additional_context}"

    # Log the message at the appropriate level
    if log_level == logging.DEBUG:
        logger.debug(log_message)
    elif log_level == logging.INFO:
        logger.info(log_message)
    elif log_level == logging.WARNING:
        logger.warning(log_message)
    elif log_level == logging.ERROR:
        logger.error(log_message)
    elif log_level == logging.CRITICAL:
        logger.critical(log_message)
    else:
        logger.error(log_message)

    # For errors at WARNING level or higher, log detailed context
    if log_level >= logging.WARNING:
        # Get detailed error context
        context = get_detailed_error_context(
            error=error,
            command_name=command_name,
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        )

        # Add additional context if provided
        if additional_context:
            context["additional_info"] = additional_context

        # Log the detailed context as JSON
        try:
            context_json = json.dumps(context, default=str)
            logger.log(log_level, f"Detailed error context: {context_json}")
        except Exception as e:
            logger.error(f"Failed to serialize error context: {e}")

    # For unexpected errors, log the full traceback (but exclude CommandOnCooldown)
    if (
        isinstance(error, Exception)
        and not isinstance(error, CognitaError)
        and not isinstance(
            error,
            (commands.CommandOnCooldown, discord.app_commands.errors.CommandOnCooldown),
        )
    ):
        error_details = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        logger.log(
            log_level, f"Traceback for {error_type} in {command_name}:\n{error_details}"
        )


def handle_command_errors(func: CommandT) -> CommandT:
    """Decorator for command handlers to standardize error handling.

    This decorator catches exceptions raised by command handlers and provides
    appropriate user feedback based on the exception type.

    Args:
        func: The command handler function to decorate

    Returns:
        The decorated function
    """

    @functools.wraps(func)
    async def wrapper(self, ctx, *args, **kwargs):
        try:
            return await func(self, ctx, *args, **kwargs)
        except Exception as error:
            # Determine security level based on user role
            security_level = ErrorSecurityLevel.NORMAL
            if hasattr(ctx, "author") and hasattr(ctx.author, "guild_permissions"):
                # Use more detailed errors for administrators
                if ctx.author.guild_permissions.administrator:
                    security_level = ErrorSecurityLevel.DEBUG

            # Get the appropriate error response with security level
            response = get_error_response(error, security_level)

            # Format the error message if not already sanitized
            if response.get("sanitized", False):
                user_message = response["message"]
            else:
                try:
                    # Format the message template with the error
                    user_message = response["message"].format(error=error)

                    # Apply additional sanitization if needed
                    if detect_sensitive_info(user_message):
                        user_message = sanitize_error_message(error, security_level)
                except (KeyError, AttributeError):
                    user_message = sanitize_error_message(error, security_level)

            # Send the error message to the user
            await ctx.send(user_message)

            # Log the error with enhanced context
            log_error(
                error=error,
                command_name=func.__name__,
                user_id=ctx.author.id,
                log_level=response.get("log_level", logging.ERROR),
                guild_id=ctx.guild.id if ctx.guild else None,
                channel_id=ctx.channel.id if ctx.channel else None,
            )

            # Record error telemetry
            if hasattr(ctx, "bot"):
                await track_error(
                    ctx.bot,
                    type(error).__name__,
                    func.__name__,
                    ctx.author.id,
                    redact_sensitive_info(getattr(error, "message", str(error))),
                    ctx.guild.id if ctx.guild else None,
                    ctx.channel.id if ctx.channel else None,
                )

    return wrapper


def handle_interaction_errors(func: CommandT) -> CommandT:
    """Decorator for application command callbacks to standardize error handling.

    This decorator catches exceptions raised by application command callbacks and provides
    appropriate user feedback based on the exception type.

    Args:
        func: The application command callback to decorate

    Returns:
        The decorated function
    """

    @functools.wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        try:
            return await func(self, interaction, *args, **kwargs)
        except Exception as error:
            # Determine security level based on user role
            security_level = ErrorSecurityLevel.NORMAL
            if hasattr(interaction, "user") and hasattr(
                interaction.user, "guild_permissions"
            ):
                # Use more detailed errors for administrators
                if interaction.user.guild_permissions.administrator:
                    security_level = ErrorSecurityLevel.DEBUG

            # Get the appropriate error response with security level
            response = get_error_response(error, security_level)

            # Format the error message if not already sanitized
            if response.get("sanitized", False):
                user_message = response["message"]
            else:
                try:
                    # Format the message template with the error
                    user_message = response["message"].format(error=error)

                    # Apply additional sanitization if needed
                    if detect_sensitive_info(user_message):
                        user_message = sanitize_error_message(error, security_level)
                except (KeyError, AttributeError):
                    user_message = sanitize_error_message(error, security_level)

            # Send the error message to the user
            ephemeral = response.get("ephemeral", True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(user_message, ephemeral=ephemeral)
                else:
                    await interaction.response.send_message(
                        user_message, ephemeral=ephemeral
                    )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")

            # Log the error with enhanced context
            log_error(
                error=error,
                command_name=func.__name__,
                user_id=interaction.user.id,
                log_level=response.get("log_level", logging.ERROR),
                guild_id=interaction.guild.id if interaction.guild else None,
                channel_id=interaction.channel.id if interaction.channel else None,
            )

            # Record error telemetry
            if hasattr(interaction, "client"):
                await track_error(
                    interaction.client,
                    type(error).__name__,
                    func.__name__,
                    interaction.user.id,
                    redact_sensitive_info(getattr(error, "message", str(error))),
                    interaction.guild.id if interaction.guild else None,
                    interaction.channel.id if interaction.channel else None,
                )

    return wrapper


async def handle_global_command_error(ctx: commands.Context, error: Exception) -> None:
    """Global error handler for command errors.

    This function handles errors that occur during command invocation and
    provides appropriate user feedback based on the error type.

    Args:
        ctx: The command context
        error: The error that occurred
    """
    # Get the appropriate error response
    response = get_error_response(error)

    # Format the error message
    try:
        user_message = response["message"].format(error=error)
    except (KeyError, AttributeError):
        user_message = str(error)

    # Send the error message to the user
    await ctx.send(user_message)

    # Log the error
    log_error(
        error=error,
        command_name=ctx.command.name if ctx.command else "unknown",
        user_id=ctx.author.id,
        log_level=response.get("log_level", logging.ERROR),
    )

    # Record error telemetry
    if hasattr(ctx, "bot"):
        await track_error(
            ctx.bot,
            type(error).__name__,
            ctx.command.name if ctx.command else "unknown",
            ctx.author.id,
            getattr(error, "message", str(error)),
            ctx.guild.id if ctx.guild else None,
            ctx.channel.id if ctx.channel else None,
        )


async def handle_global_app_command_error(
    interaction: discord.Interaction, error: Exception
) -> None:
    """Global error handler for application command errors.

    This function handles errors that occur during application command invocation and
    provides appropriate user feedback based on the exception type. It also implements
    lazy loading for commands that are not found.

    Args:
        interaction: The interaction context
        error: The error that occurred
    """
    # Check if this is a CommandNotFound error and attempt lazy loading
    if isinstance(error, discord.app_commands.errors.CommandNotFound):
        # Extract command name from the error message
        command_name = None
        error_str = str(error)
        if "Application command '" in error_str and "' not found" in error_str:
            start = error_str.find("Application command '") + len(
                "Application command '"
            )
            end = error_str.find("' not found")
            command_name = error_str[start:end]

        if command_name and hasattr(interaction, "client"):
            # Define command to extension mapping
            command_to_extension = {
                "poll": "cogs.patreon_poll",
                "poll_list": "cogs.patreon_poll",
                "getpoll": "cogs.patreon_poll",
                "findpoll": "cogs.patreon_poll",
                "gallery": "cogs.gallery",
                "gallery_search": "cogs.gallery",
                "gallery_random": "cogs.gallery",
                "gallery_stats": "cogs.gallery",
                "links": "cogs.links_tags",
                "tags": "cogs.links_tags",
                "twi": "cogs.twi",
                "other": "cogs.other",
                "creator_links": "cogs.creator_links",
                "report": "cogs.report",
                "summarization": "cogs.summarization",
            }

            extension_name = command_to_extension.get(command_name)
            if extension_name and hasattr(
                interaction.client, "load_extension_if_needed"
            ):
                logger.info(
                    f"Attempting to lazy load extension {extension_name} for command {command_name}"
                )

                try:
                    # Attempt to load the extension
                    success = await interaction.client.load_extension_if_needed(
                        extension_name
                    )

                    if success:
                        logger.info(f"Successfully loaded extension {extension_name}")

                        # Sync the command tree to register the new commands
                        try:
                            await interaction.client.tree.sync()
                            logger.info("Command tree synced after lazy loading")

                            # Try to find and execute the newly loaded command
                            command = None
                            for cmd in interaction.client.tree.get_commands():
                                if cmd.name == command_name:
                                    command = cmd
                                    break

                            if command:
                                logger.info(
                                    f"Found command {command_name}, attempting to execute it automatically"
                                )
                                try:
                                    # Try to invoke the command using the proper Discord.py method
                                    # First, try using the command's _invoke method if it exists
                                    try:
                                        if hasattr(command, "_invoke"):
                                            await command._invoke(interaction)
                                        else:
                                            raise AttributeError("No _invoke method")
                                    except (AttributeError, TypeError):
                                        # Fall back to calling the callback directly
                                        if hasattr(command, "callback"):
                                            # Try to get the cog from the command's binding or other attributes
                                            cog = None
                                            if hasattr(command, "binding"):
                                                cog = command.binding
                                            elif hasattr(command, "cog"):
                                                cog = command.cog
                                            elif hasattr(command, "_cog"):
                                                cog = command._cog

                                            if cog is not None:
                                                # Call the callback with the cog instance
                                                await command.callback(
                                                    cog,
                                                    interaction,
                                                    **_extract_command_params(
                                                        interaction, command
                                                    ),
                                                )
                                            else:
                                                # Try calling without cog (might work for some commands)
                                                await command.callback(
                                                    interaction,
                                                    **_extract_command_params(
                                                        interaction, command
                                                    ),
                                                )
                                        else:
                                            logger.warning(
                                                f"Command {command_name} has no known invocation method"
                                            )
                                            raise Exception(
                                                "No known invocation method"
                                            )

                                    logger.info(
                                        f"Successfully executed command {command_name} after lazy loading"
                                    )

                                    # Don't continue with normal error handling since we've handled this case
                                    return

                                except Exception as e:
                                    logger.error(
                                        f"Failed to automatically execute command {command_name}: {e}"
                                    )
                                    # Fall back to telling the user to try again
                                    try:
                                        if interaction.response.is_done():
                                            await interaction.followup.send(
                                                f"The `/{command_name}` command has been loaded, but there was an issue executing it automatically. Please try your command again.",
                                                ephemeral=True,
                                            )
                                        else:
                                            await interaction.response.send_message(
                                                f"The `/{command_name}` command has been loaded, but there was an issue executing it automatically. Please try your command again.",
                                                ephemeral=True,
                                            )
                                    except Exception as msg_error:
                                        logger.error(
                                            f"Failed to send fallback message: {msg_error}"
                                        )
                            else:
                                logger.warning(
                                    f"Command {command_name} not found after loading and syncing"
                                )
                                # Fall back to telling the user to try again
                                try:
                                    if interaction.response.is_done():
                                        await interaction.followup.send(
                                            f"The `/{command_name}` command has been loaded. Please try your command again.",
                                            ephemeral=True,
                                        )
                                    else:
                                        await interaction.response.send_message(
                                            f"The `/{command_name}` command has been loaded. Please try your command again.",
                                            ephemeral=True,
                                        )
                                except Exception as msg_error:
                                    logger.error(
                                        f"Failed to send command not found message: {msg_error}"
                                    )

                            # Don't continue with normal error handling since we've handled this case
                            return

                        except Exception as e:
                            logger.error(
                                f"Failed to sync command tree after lazy loading: {e}"
                            )
                    else:
                        logger.warning(
                            f"Failed to load extension {extension_name} for command {command_name}"
                        )

                except Exception as e:
                    logger.error(f"Error during lazy loading of {extension_name}: {e}")

    # Skip CommandOnCooldown errors as they should be handled by command-specific error handlers
    if isinstance(error, discord.app_commands.errors.CommandOnCooldown):
        # Only log the error for telemetry, don't send a message to avoid duplicates
        command_name = interaction.command.name if interaction.command else "unknown"
        log_error(
            error=error,
            command_name=command_name,
            user_id=interaction.user.id,
            log_level=logging.WARNING,
        )

        # Record error telemetry
        if hasattr(interaction, "client"):
            await track_error(
                interaction.client,
                type(error).__name__,
                command_name,
                interaction.user.id,
                getattr(error, "message", str(error)),
                interaction.guild.id if interaction.guild else None,
                interaction.channel.id if interaction.channel else None,
            )
        return

    # Get the appropriate error response
    response = get_error_response(error)

    # Format the error message
    try:
        user_message = response["message"].format(error=error)
    except (KeyError, AttributeError):
        user_message = str(error)

    # Send the error message to the user
    ephemeral = response.get("ephemeral", True)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(user_message, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(user_message, ephemeral=ephemeral)
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}")

    # Log the error
    command_name = interaction.command.name if interaction.command else "unknown"
    log_error(
        error=error,
        command_name=command_name,
        user_id=interaction.user.id,
        log_level=response.get("log_level", logging.ERROR),
    )

    # Record error telemetry
    if hasattr(interaction, "client"):
        await track_error(
            interaction.client,
            type(error).__name__,
            command_name,
            interaction.user.id,
            getattr(error, "message", str(error)),
            interaction.guild.id if interaction.guild else None,
            interaction.channel.id if interaction.channel else None,
        )


def setup_global_exception_handler(bot: commands.Bot) -> None:
    """Set up global exception handlers for the bot.

    This function sets up handlers for uncaught exceptions in the bot.

    Args:
        bot: The bot instance
    """

    # Set up command error handler
    @bot.event
    async def on_command_error(ctx: commands.Context, error: Exception) -> None:
        await handle_global_command_error(ctx, error)

    # Set up app command error handler
    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: Exception
    ) -> None:
        await handle_global_app_command_error(interaction, error)

    # Set up global exception handler for uncaught exceptions
    def global_exception_handler(exctype, value, traceback_obj):
        logger.critical(f"Uncaught exception: {exctype.__name__}: {value}")
        logger.critical(
            "".join(traceback.format_exception(exctype, value, traceback_obj))
        )
        sys.__excepthook__(exctype, value, traceback_obj)

    sys.excepthook = global_exception_handler

    logger.info("Global exception handlers set up successfully")

"""Decorators for Twi Bot Shard.

This module provides decorators for cross-cutting concerns like
logging, error handling, and permission checks.
"""

import functools
from collections.abc import Callable
from typing import Any, TypeVar, cast

from discord import app_commands

T = TypeVar("T")
CommandT = TypeVar("CommandT", bound=Callable[..., Any])


def log_command(command_name: str | None = None) -> Callable[[CommandT], CommandT]:
    """Decorator to log command usage.

    Args:
        command_name: Optional name for the command. If not provided, the function name will be used.

    Returns:
        A decorator that logs command usage.
    """

    def decorator(func: CommandT) -> CommandT:
        cmd_name = command_name or func.__name__

        @functools.wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Extract the interaction/context from args
            ctx_or_interaction = args[0] if args else None

            # Log command usage
            if ctx_or_interaction:
                await self.log_command_usage(ctx_or_interaction, cmd_name)

            # Call the original function with all arguments
            return await func(self, *args, **kwargs)

        return cast(CommandT, wrapper)

    return decorator


def handle_errors(command_name: str | None = None) -> Callable[[CommandT], CommandT]:
    """Decorator to handle command errors.

    Args:
        command_name: Optional name for the command. If not provided, the function name will be used.

    Returns:
        A decorator that handles command errors.
    """

    def decorator(func: CommandT) -> CommandT:
        cmd_name = command_name or func.__name__

        @functools.wraps(func)
        async def wrapper(
            self: Any, ctx_or_interaction: Any, *args: Any, **kwargs: Any
        ) -> Any:
            try:
                # Call the original function
                return await func(self, ctx_or_interaction, *args, **kwargs)
            except Exception as e:
                # Handle the error
                await self.handle_error(ctx_or_interaction, e, cmd_name)

        return cast(CommandT, wrapper)

    return decorator


def require_bot_channel() -> Callable[[CommandT], CommandT]:
    """Decorator to require that a command is used in the bot channel.

    Returns:
        A decorator that checks if the command is used in the bot channel.
    """

    def decorator(func: CommandT) -> CommandT:
        # Check if the function is a command or app command
        is_app_command = hasattr(func, "__discord_app_commands_is_command__")

        if is_app_command:
            # For app commands, use the app_commands.check decorator
            from utils.permissions import app_is_bot_channel

            func = app_commands.check(app_is_bot_channel)(func)  # type: ignore
        else:
            # For traditional commands, use the commands.check decorator
            from utils.permissions import is_bot_channel_wrapper

            func = is_bot_channel_wrapper(func)  # type: ignore

        return cast(CommandT, func)

    return decorator


def require_admin() -> Callable[[CommandT], CommandT]:
    """Decorator to require that a command is used by an admin.

    Returns:
        A decorator that checks if the command is used by an admin.
    """

    def decorator(func: CommandT) -> CommandT:
        # Check if the function is a command or app command
        is_app_command = hasattr(func, "__discord_app_commands_is_command__")

        if is_app_command:
            # For app commands, use the app_commands.check decorator
            from utils.permissions import app_admin_or_me_check

            func = app_commands.check(app_admin_or_me_check)(func)  # type: ignore
        else:
            # For traditional commands, use the commands.check decorator
            from utils.permissions import admin_or_me_check_wrapper

            func = admin_or_me_check_wrapper(func)  # type: ignore

        return cast(CommandT, func)

    return decorator

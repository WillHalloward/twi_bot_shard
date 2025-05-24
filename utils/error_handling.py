"""
Error handling utilities for Cognita bot.

This module provides utilities for standardized error handling across the bot,
including decorators for command handlers and functions for error telemetry.
"""

import functools
import logging
import traceback
import datetime
from typing import Callable, TypeVar, Optional, Any, Coroutine

import discord
from discord.ext import commands

from utils.exceptions import (
    CognitaError, UserInputError, ExternalServiceError,
    PermissionError, ResourceNotFoundError, ConfigurationError,
    RateLimitError
)

T = TypeVar('T')
CommandT = TypeVar('CommandT', bound=Callable[..., Coroutine[Any, Any, Any]])

logger = logging.getLogger('error_handling')


async def track_error(
    bot, 
    error_type: str, 
    command_name: str, 
    user_id: int, 
    error_message: str,
    guild_id: Optional[int] = None,
    channel_id: Optional[int] = None
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
            error_type, command_name, user_id, str(error_message),
            guild_id, channel_id, datetime.datetime.now()
        )
    except Exception as e:
        logger.error(f"Failed to record error telemetry: {e}")
        return -1


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
        except UserInputError as e:
            await ctx.send(f"Invalid input: {e.message}")
            logger.warning(f"UserInputError in {func.__name__}: {e.message} | User: {ctx.author.id}")
        except ExternalServiceError as e:
            await ctx.send(f"External service error: {e.message}")
            logger.warning(f"ExternalServiceError ({e.service_name}) in {func.__name__}: {e.message} | User: {ctx.author.id}")
        except PermissionError as e:
            await ctx.send(f"Permission denied: {e.message}")
            logger.warning(f"PermissionError in {func.__name__}: {e.message} | User: {ctx.author.id}")
        except ResourceNotFoundError as e:
            await ctx.send(f"Not found: {e.message}")
            logger.warning(f"ResourceNotFoundError in {func.__name__}: {e.message} | User: {ctx.author.id}")
        except ConfigurationError as e:
            await ctx.send(f"Configuration error: {e.message}")
            logger.error(f"ConfigurationError in {func.__name__}: {e.message} | User: {ctx.author.id}")
        except RateLimitError as e:
            await ctx.send(f"Rate limit exceeded: {e.message}")
            logger.warning(f"RateLimitError in {func.__name__}: {e.message} | User: {ctx.author.id}")
        except CognitaError as e:
            await ctx.send(f"Error: {e.message}")
            logger.error(f"CognitaError in {func.__name__}: {e.message} | User: {ctx.author.id}")
            
            # Record error telemetry
            if hasattr(ctx, 'bot'):
                await track_error(
                    ctx.bot,
                    type(e).__name__,
                    func.__name__,
                    ctx.author.id,
                    e.message,
                    ctx.guild.id if ctx.guild else None,
                    ctx.channel.id if ctx.channel else None
                )
        except Exception as e:
            await ctx.send("An unexpected error occurred. The bot administrators have been notified.")
            error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.exception(f"Unexpected error in {func.__name__}: {e} | User: {ctx.author.id}")
            
            # Record error telemetry
            if hasattr(ctx, 'bot'):
                await track_error(
                    ctx.bot,
                    type(e).__name__,
                    func.__name__,
                    ctx.author.id,
                    str(e),
                    ctx.guild.id if ctx.guild else None,
                    ctx.channel.id if ctx.channel else None
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
        except UserInputError as e:
            await interaction.response.send_message(f"Invalid input: {e.message}", ephemeral=True)
            logger.warning(f"UserInputError in {func.__name__}: {e.message} | User: {interaction.user.id}")
        except ExternalServiceError as e:
            await interaction.response.send_message(f"External service error: {e.message}", ephemeral=True)
            logger.warning(f"ExternalServiceError ({e.service_name}) in {func.__name__}: {e.message} | User: {interaction.user.id}")
        except PermissionError as e:
            await interaction.response.send_message(f"Permission denied: {e.message}", ephemeral=True)
            logger.warning(f"PermissionError in {func.__name__}: {e.message} | User: {interaction.user.id}")
        except ResourceNotFoundError as e:
            await interaction.response.send_message(f"Not found: {e.message}", ephemeral=True)
            logger.warning(f"ResourceNotFoundError in {func.__name__}: {e.message} | User: {interaction.user.id}")
        except ConfigurationError as e:
            await interaction.response.send_message(f"Configuration error: {e.message}", ephemeral=True)
            logger.error(f"ConfigurationError in {func.__name__}: {e.message} | User: {interaction.user.id}")
        except RateLimitError as e:
            await interaction.response.send_message(f"Rate limit exceeded: {e.message}", ephemeral=True)
            logger.warning(f"RateLimitError in {func.__name__}: {e.message} | User: {interaction.user.id}")
        except CognitaError as e:
            await interaction.response.send_message(f"Error: {e.message}", ephemeral=True)
            logger.error(f"CognitaError in {func.__name__}: {e.message} | User: {interaction.user.id}")
            
            # Record error telemetry
            if hasattr(interaction, 'client'):
                await track_error(
                    interaction.client,
                    type(e).__name__,
                    func.__name__,
                    interaction.user.id,
                    e.message,
                    interaction.guild.id if interaction.guild else None,
                    interaction.channel.id if interaction.channel else None
                )
        except Exception as e:
            # Check if the interaction has already been responded to
            if interaction.response.is_done():
                await interaction.followup.send("An unexpected error occurred. The bot administrators have been notified.", ephemeral=True)
            else:
                await interaction.response.send_message("An unexpected error occurred. The bot administrators have been notified.", ephemeral=True)
                
            error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.exception(f"Unexpected error in {func.__name__}: {e} | User: {interaction.user.id}")
            
            # Record error telemetry
            if hasattr(interaction, 'client'):
                await track_error(
                    interaction.client,
                    type(e).__name__,
                    func.__name__,
                    interaction.user.id,
                    str(e),
                    interaction.guild.id if interaction.guild else None,
                    interaction.channel.id if interaction.channel else None
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
    # Handle command-specific errors
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use !help to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Invalid argument: {error}")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds.")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command cannot be used in private messages.")
    elif isinstance(error, commands.DisabledCommand):
        await ctx.send("This command is currently disabled.")
    # Handle custom exceptions
    elif isinstance(error, CognitaError):
        await ctx.send(f"Error: {error.message}")
        logger.error(f"CognitaError in {ctx.command.name}: {error.message} | User: {ctx.author.id}")
    # Handle unexpected errors
    else:
        await ctx.send("An unexpected error occurred. The bot administrators have been notified.")
        error_details = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        logger.exception(f"Unexpected error in {ctx.command.name if ctx.command else 'unknown command'}: {error} | User: {ctx.author.id}")
    
    # Record error telemetry
    if hasattr(ctx, 'bot'):
        await track_error(
            ctx.bot,
            type(error).__name__,
            ctx.command.name if ctx.command else "unknown",
            ctx.author.id,
            str(error),
            ctx.guild.id if ctx.guild else None,
            ctx.channel.id if ctx.channel else None
        )
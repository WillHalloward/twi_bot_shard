"""Permission utilities for Cognita bot.

Simplified permission system that leverages Discord's native permissions
with bot owner override support.
"""

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.exceptions import OwnerOnlyError, PermissionError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("permissions")


# =============================================================================
# Core Permission Checks
# =============================================================================


def is_bot_owner(user_id: int) -> bool:
    """Check if user is the bot owner."""
    return user_id == config.bot_owner_id


async def is_admin(
    bot: "commands.Bot",
    guild_id: int,
    user_id: int,
    user_roles: list[int] | None = None,
) -> bool:
    """Check if user is an admin in the guild.

    Checks:
    1. Bot owner always has admin
    2. User has configured admin role for the server
    3. User has Discord administrator permission

    Args:
        bot: The bot instance
        guild_id: The guild ID
        user_id: The user ID
        user_roles: Optional list of user role IDs

    Returns:
        True if user has admin permissions
    """
    # Bot owner always has admin
    if is_bot_owner(user_id):
        return True

    guild = bot.get_guild(guild_id)
    if not guild:
        return False

    member = guild.get_member(user_id)
    if not member:
        return False

    # Check Discord administrator permission
    if member.guild_permissions.administrator:
        return True

    # Check configured admin role from settings
    settings_cog = bot.get_cog("Settings")
    if settings_cog:
        return await settings_cog.is_admin(bot, guild_id, user_id, user_roles)

    return False


async def is_moderator(
    bot: "commands.Bot",
    guild_id: int,
    user_id: int,
) -> bool:
    """Check if user is a moderator in the guild.

    Checks:
    1. Bot owner always has mod
    2. User has admin (admins are also mods)
    3. User has Discord ban_members permission

    Args:
        bot: The bot instance
        guild_id: The guild ID
        user_id: The user ID

    Returns:
        True if user has moderator permissions
    """
    if is_bot_owner(user_id):
        return True

    guild = bot.get_guild(guild_id)
    if not guild:
        return False

    member = guild.get_member(user_id)
    if not member:
        return False

    return member.guild_permissions.ban_members


# =============================================================================
# Check Functions for Commands
# =============================================================================


async def admin_or_me_check(
    ctx_or_interaction: commands.Context | discord.Interaction,
) -> bool:
    """Check if user is an admin or the bot owner.

    Works with both Context (prefix commands) and Interaction (slash commands).

    Args:
        ctx_or_interaction: The command context or interaction

    Returns:
        True if user is admin or bot owner

    Raises:
        PermissionError: If user lacks permission
    """
    is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

    user = ctx_or_interaction.user if is_interaction else ctx_or_interaction.author
    guild = ctx_or_interaction.guild
    bot = ctx_or_interaction.client if is_interaction else ctx_or_interaction.bot

    if not guild:
        raise PermissionError("This command can only be used in a server")

    user_roles = [role.id for role in user.roles]
    has_perm = await is_admin(bot, guild.id, user.id, user_roles)

    if not has_perm:
        raise PermissionError("You need admin permissions to use this command")

    return True


def admin_or_me_check_wrapper(func: commands.Command) -> commands.Command:
    """Wrapper for admin_or_me_check to use with @commands.check decorator."""

    async def predicate(ctx: commands.Context) -> bool:
        return await admin_or_me_check(ctx)

    return commands.check(predicate)(func)


def app_admin_or_me_check(interaction: discord.Interaction) -> bool:
    """Wrapper for admin_or_me_check to use with @app_commands.check decorator."""
    return admin_or_me_check(interaction)


async def moderator_check(
    ctx_or_interaction: commands.Context | discord.Interaction,
) -> bool:
    """Check if user is a moderator or the bot owner.

    Works with both Context (prefix commands) and Interaction (slash commands).

    Args:
        ctx_or_interaction: The command context or interaction

    Returns:
        True if user is moderator or bot owner

    Raises:
        PermissionError: If user lacks permission
    """
    is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

    user = ctx_or_interaction.user if is_interaction else ctx_or_interaction.author
    guild = ctx_or_interaction.guild
    bot = ctx_or_interaction.client if is_interaction else ctx_or_interaction.bot

    if not guild:
        raise PermissionError("This command can only be used in a server")

    has_perm = await is_moderator(bot, guild.id, user.id)

    if not has_perm:
        raise PermissionError("You need moderator permissions to use this command")

    return True


def moderator_check_wrapper(func: commands.Command) -> commands.Command:
    """Wrapper for moderator_check to use with @commands.check decorator."""

    async def predicate(ctx: commands.Context) -> bool:
        return await moderator_check(ctx)

    return commands.check(predicate)(func)


def app_moderator_check(interaction: discord.Interaction) -> bool:
    """Wrapper for moderator_check to use with @app_commands.check decorator."""
    return moderator_check(interaction)


# =============================================================================
# Channel Checks
# =============================================================================


async def is_bot_channel(
    ctx_or_interaction: commands.Context | discord.Interaction,
) -> bool:
    """Check if command is in the designated bot channel.

    Args:
        ctx_or_interaction: The command context or interaction

    Returns:
        True if in bot channel
    """
    return ctx_or_interaction.channel.id == config.bot_channel_id


def is_bot_channel_wrapper(func: commands.Command) -> commands.Command:
    """Wrapper for is_bot_channel to use with @commands.check decorator."""

    async def predicate(ctx: commands.Context) -> bool:
        return await is_bot_channel(ctx)

    return commands.check(predicate)(func)


async def app_is_bot_channel(interaction: discord.Interaction) -> bool:
    """Wrapper for is_bot_channel to use with @app_commands.check decorator."""
    return await is_bot_channel(interaction)


# =============================================================================
# Owner-Only Check
# =============================================================================


async def owner_only_check(
    ctx_or_interaction: commands.Context | discord.Interaction,
) -> bool:
    """Check if user is the bot owner.

    Args:
        ctx_or_interaction: The command context or interaction

    Returns:
        True if user is bot owner

    Raises:
        OwnerOnlyError: If user is not the owner
    """
    is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
    user = ctx_or_interaction.user if is_interaction else ctx_or_interaction.author

    if not is_bot_owner(user.id):
        raise OwnerOnlyError()

    return True


def owner_only(func: commands.Command) -> commands.Command:
    """Decorator to restrict command to bot owner only."""

    async def predicate(
        ctx_or_interaction: commands.Context | discord.Interaction,
    ) -> bool:
        return await owner_only_check(ctx_or_interaction)

    if isinstance(func, commands.Command):
        return commands.check(predicate)(func)
    return app_commands.check(predicate)(func)


# =============================================================================
# Setup Function (for compatibility)
# =============================================================================


async def setup_permissions(bot: "commands.Bot") -> None:
    """Set up the permission system.

    This is a no-op in the simplified system - permissions are checked
    dynamically using Discord's native permission system.

    Args:
        bot: The bot instance
    """
    logger.info("Permission system initialized (using Discord native permissions)")

"""Permission utilities for Cognita bot.

This module provides utilities for permission checks across the bot,
including a comprehensive role-based access control system,
functions to check if a user has specific permissions,
and channel-specific checks.
"""

import enum
import json
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.exceptions import OwnerOnlyError, PermissionError, RolePermissionError

logger = logging.getLogger("permissions")


class PermissionLevel(enum.IntEnum):
    """Enum representing permission levels in the bot.

    Higher values represent higher permission levels.
    """

    NONE = 0
    USER = 10
    MODERATOR = 50
    ADMIN = 80
    OWNER = 100

    @classmethod
    def from_string(cls, level_str: str) -> "PermissionLevel":
        """Convert a string permission level to enum value."""
        try:
            return cls[level_str.upper()]
        except KeyError:
            try:
                return cls(int(level_str))
            except (ValueError, KeyError):
                return cls.NONE


class Permission(enum.Enum):
    """Enum representing specific permissions in the bot.

    Each permission has a name and a minimum required permission level.
    """

    # Basic permissions
    VIEW_COMMANDS = ("view_commands", PermissionLevel.USER)
    USE_BASIC_COMMANDS = ("use_basic_commands", PermissionLevel.USER)

    # Moderation permissions
    MANAGE_MESSAGES = ("manage_messages", PermissionLevel.MODERATOR)
    MANAGE_THREADS = ("manage_threads", PermissionLevel.MODERATOR)
    MANAGE_ROLES = ("manage_roles", PermissionLevel.MODERATOR)
    KICK_MEMBERS = ("kick_members", PermissionLevel.MODERATOR)
    BAN_MEMBERS = ("ban_members", PermissionLevel.MODERATOR)

    # Admin permissions
    MANAGE_GUILD = ("manage_guild", PermissionLevel.ADMIN)
    MANAGE_CHANNELS = ("manage_channels", PermissionLevel.ADMIN)
    MANAGE_WEBHOOKS = ("manage_webhooks", PermissionLevel.ADMIN)
    MANAGE_PERMISSIONS = ("manage_permissions", PermissionLevel.ADMIN)

    # Bot owner permissions
    MANAGE_BOT = ("manage_bot", PermissionLevel.OWNER)

    def __init__(self, name: str, level: PermissionLevel) -> None:
        self.permission_name = name
        self.required_level = level

    @classmethod
    def get_by_name(cls, name: str) -> Optional["Permission"]:
        """Get a permission by its name."""
        for permission in cls:
            if permission.permission_name == name:
                return permission
        return None


class PermissionManager:
    """Manager for handling permissions and role-based access control.

    This class provides methods for checking if users have specific permissions,
    managing permission roles, and handling permission-related database operations.
    """

    def __init__(self, bot) -> None:
        """Initialize the permission manager.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger("permissions.manager")
        self._cache = {}  # Cache for permission checks

    async def _init_db(self) -> None:
        """Initialize the database tables for permissions."""
        try:
            # Create role_permissions table if it doesn't exist
            await self.bot.db.execute(
                """
                CREATE TABLE IF NOT EXISTS role_permissions (
                    guild_id BIGINT NOT NULL,
                    role_id BIGINT NOT NULL,
                    permission_level INT NOT NULL DEFAULT 0,
                    permissions JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, role_id)
                )
            """
            )

            # Create user_permissions table if it doesn't exist
            await self.bot.db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_permissions (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    permission_level INT NOT NULL DEFAULT 0,
                    permissions JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, user_id)
                )
            """
            )

            self.logger.info("Permission tables initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize permission tables: {e}")
            raise

    async def get_user_permission_level(
        self, guild_id: int, user_id: int, user_roles: list[int] = None
    ) -> PermissionLevel:
        """Get the permission level for a user in a guild.

        Args:
            guild_id: The guild ID
            user_id: The user ID
            user_roles: Optional list of user role IDs (to avoid additional API calls)

        Returns:
            The user's permission level
        """
        # Check if user is the bot owner
        if user_id == config.bot_owner_id:
            return PermissionLevel.OWNER

        # Check cache
        cache_key = f"user_level:{guild_id}:{user_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Check user-specific permission level
        user_level = await self.bot.db.fetchval(
            """
            SELECT permission_level FROM user_permissions
            WHERE guild_id = $1 AND user_id = $2
        """,
            guild_id,
            user_id,
        )

        if user_level is not None:
            self._cache[cache_key] = PermissionLevel(user_level)
            return PermissionLevel(user_level)

        # Check role-based permission levels
        if user_roles is None:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return PermissionLevel.NONE

            member = guild.get_member(user_id)
            if not member:
                return PermissionLevel.NONE

            user_roles = [role.id for role in member.roles]

        # Get the highest permission level from the user's roles
        role_levels = await self.bot.db.fetch(
            """
            SELECT permission_level FROM role_permissions
            WHERE guild_id = $1 AND role_id = ANY($2)
        """,
            guild_id,
            user_roles,
        )

        max_level = PermissionLevel.USER  # Default to USER level
        for record in role_levels:
            level = PermissionLevel(record["permission_level"])
            if level > max_level:
                max_level = level

        # Cache the result
        self._cache[cache_key] = max_level
        return max_level

    async def has_permission(
        self,
        guild_id: int,
        user_id: int,
        permission: Permission | str,
        user_roles: list[int] = None,
    ) -> bool:
        """Check if a user has a specific permission.

        Args:
            guild_id: The guild ID
            user_id: The user ID
            permission: The permission to check (can be a Permission enum or a string)
            user_roles: Optional list of user role IDs (to avoid additional API calls)

        Returns:
            True if the user has the permission, False otherwise
        """
        # Convert string permission to enum
        if isinstance(permission, str):
            permission_obj = Permission.get_by_name(permission)
            if permission_obj is None:
                self.logger.warning(f"Unknown permission: {permission}")
                return False
        else:
            permission_obj = permission

        # Get the user's permission level
        user_level = await self.get_user_permission_level(guild_id, user_id, user_roles)

        # Check if the user's level is sufficient
        if user_level >= permission_obj.required_level:
            return True

        # Check for specific permission overrides
        # First check user-specific permissions
        user_permissions = await self.bot.db.fetchval(
            """
            SELECT permissions FROM user_permissions
            WHERE guild_id = $1 AND user_id = $2
        """,
            guild_id,
            user_id,
        )

        if user_permissions:
            permissions_dict = json.loads(user_permissions)
            if permission_obj.permission_name in permissions_dict:
                return permissions_dict[permission_obj.permission_name]

        # Then check role-specific permissions
        if user_roles is None:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return False

            member = guild.get_member(user_id)
            if not member:
                return False

            user_roles = [role.id for role in member.roles]

        role_permissions = await self.bot.db.fetch(
            """
            SELECT permissions FROM role_permissions
            WHERE guild_id = $1 AND role_id = ANY($2)
        """,
            guild_id,
            user_roles,
        )

        for record in role_permissions:
            if record["permissions"]:
                permissions_dict = json.loads(record["permissions"])
                if (
                    permission_obj.permission_name in permissions_dict
                    and permissions_dict[permission_obj.permission_name]
                ):
                    return True

        return False

    async def set_role_permission_level(
        self, guild_id: int, role_id: int, level: PermissionLevel
    ) -> None:
        """Set the permission level for a role.

        Args:
            guild_id: The guild ID
            role_id: The role ID
            level: The permission level to set
        """
        try:
            # Check if a record exists for this role
            existing = await self.bot.db.fetchval(
                "SELECT role_id FROM role_permissions WHERE guild_id = $1 AND role_id = $2",
                guild_id,
                role_id,
            )

            if existing:
                # Update existing record
                await self.bot.db.execute(
                    """
                    UPDATE role_permissions 
                    SET permission_level = $3, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = $1 AND role_id = $2
                """,
                    guild_id,
                    role_id,
                    level.value,
                )
            else:
                # Insert new record
                await self.bot.db.execute(
                    """
                    INSERT INTO role_permissions (guild_id, role_id, permission_level)
                    VALUES ($1, $2, $3)
                """,
                    guild_id,
                    role_id,
                    level.value,
                )

            # Clear cache
            self._clear_guild_cache(guild_id)

            self.logger.info(
                f"Set permission level {level.name} for role {role_id} in guild {guild_id}"
            )
        except Exception as e:
            self.logger.error(f"Error setting role permission level: {e}")
            raise

    async def set_user_permission_level(
        self, guild_id: int, user_id: int, level: PermissionLevel
    ) -> None:
        """Set the permission level for a user.

        Args:
            guild_id: The guild ID
            user_id: The user ID
            level: The permission level to set
        """
        try:
            # Check if a record exists for this user
            existing = await self.bot.db.fetchval(
                "SELECT user_id FROM user_permissions WHERE guild_id = $1 AND user_id = $2",
                guild_id,
                user_id,
            )

            if existing:
                # Update existing record
                await self.bot.db.execute(
                    """
                    UPDATE user_permissions 
                    SET permission_level = $3, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = $1 AND user_id = $2
                """,
                    guild_id,
                    user_id,
                    level.value,
                )
            else:
                # Insert new record
                await self.bot.db.execute(
                    """
                    INSERT INTO user_permissions (guild_id, user_id, permission_level)
                    VALUES ($1, $2, $3)
                """,
                    guild_id,
                    user_id,
                    level.value,
                )

            # Clear cache
            cache_key = f"user_level:{guild_id}:{user_id}"
            if cache_key in self._cache:
                del self._cache[cache_key]

            self.logger.info(
                f"Set permission level {level.name} for user {user_id} in guild {guild_id}"
            )
        except Exception as e:
            self.logger.error(f"Error setting user permission level: {e}")
            raise

    async def set_permission_override(
        self,
        guild_id: int,
        target_id: int,
        permission: Permission | str,
        value: bool,
        is_role: bool = False,
    ) -> None:
        """Set a specific permission override for a user or role.

        Args:
            guild_id: The guild ID
            target_id: The user or role ID
            permission: The permission to set
            value: The permission value (True to grant, False to deny)
            is_role: Whether the target is a role (True) or a user (False)
        """
        # Convert string permission to enum
        if isinstance(permission, str):
            permission_obj = Permission.get_by_name(permission)
            if permission_obj is None:
                self.logger.warning(f"Unknown permission: {permission}")
                return
        else:
            permission_obj = permission

        try:
            table = "role_permissions" if is_role else "user_permissions"
            id_column = "role_id" if is_role else "user_id"

            # Check if a record exists
            existing = await self.bot.db.fetchval(
                f"""
                SELECT permissions FROM {table}
                WHERE guild_id = $1 AND {id_column} = $2
            """,
                guild_id,
                target_id,
            )

            permissions_dict = json.loads(existing) if existing else {}
            permissions_dict[permission_obj.permission_name] = value

            if existing:
                # Update existing record
                await self.bot.db.execute(
                    f"""
                    UPDATE {table}
                    SET permissions = $3, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = $1 AND {id_column} = $2
                """,
                    guild_id,
                    target_id,
                    json.dumps(permissions_dict),
                )
            else:
                # Insert new record with default permission level
                await self.bot.db.execute(
                    f"""
                    INSERT INTO {table} (guild_id, {id_column}, permissions)
                    VALUES ($1, $2, $3)
                """,
                    guild_id,
                    target_id,
                    json.dumps(permissions_dict),
                )

            # Clear cache
            if is_role:
                self._clear_guild_cache(guild_id)
            else:
                cache_key = f"user_level:{guild_id}:{target_id}"
                if cache_key in self._cache:
                    del self._cache[cache_key]

            target_type = "role" if is_role else "user"
            self.logger.info(
                f"Set permission override {permission_obj.permission_name}={value} for {target_type} {target_id} in guild {guild_id}"
            )
        except Exception as e:
            self.logger.error(f"Error setting permission override: {e}")
            raise

    def _clear_guild_cache(self, guild_id: int) -> None:
        """Clear all cached permission data for a guild.

        Args:
            guild_id: The guild ID
        """
        keys_to_delete = [
            k for k in self._cache if k.startswith(f"user_level:{guild_id}:")
        ]
        for key in keys_to_delete:
            del self._cache[key]

    def clear_cache(self) -> None:
        """Clear all cached permission data."""
        self._cache.clear()

    async def check_permission(
        self,
        ctx_or_interaction: commands.Context | discord.Interaction,
        permission: Permission | str,
    ) -> bool:
        """Check if the user has a specific permission.

        This function works with both Context objects (for traditional commands)
        and Interaction objects (for application commands).

        Args:
            ctx_or_interaction: The command context or interaction
            permission: The permission to check

        Returns:
            True if the user has the permission, False otherwise

        Raises:
            PermissionError: If the user doesn't have the required permission
        """
        # Determine if we're dealing with a Context or an Interaction
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

        # Get the user and guild
        user = ctx_or_interaction.user if is_interaction else ctx_or_interaction.author
        guild = ctx_or_interaction.guild

        if not guild:
            raise PermissionError("This command can only be used in a server")

        # Get user roles for efficiency
        user_roles = [role.id for role in user.roles]

        # Check if the user has the permission
        has_perm = await self.has_permission(guild.id, user.id, permission, user_roles)

        if not has_perm:
            # Convert string permission to enum for error message
            if isinstance(permission, str):
                permission_obj = Permission.get_by_name(permission)
                if permission_obj is None:
                    raise PermissionError(
                        f"You don't have the required permission: {permission}"
                    )
            else:
                permission_obj = permission

            # Raise appropriate exception based on required level
            if permission_obj.required_level == PermissionLevel.OWNER:
                raise OwnerOnlyError()
            else:
                raise RolePermissionError(
                    f"{permission_obj.required_level.name.lower()} role"
                )

        return True


# Global permission manager instance
# This will be initialized in the bot's setup
_permission_manager = None


def get_permission_manager():
    """Get the global permission manager instance."""
    if _permission_manager is None:
        raise RuntimeError(
            "Permission manager not initialized. Call init_permission_manager first."
        )
    return _permission_manager


def init_permission_manager(bot):
    """Initialize the global permission manager instance."""
    global _permission_manager
    _permission_manager = PermissionManager(bot)
    return _permission_manager


async def setup_permissions(bot) -> None:
    """Set up the permission system.

    This function initializes the permission manager and creates the necessary database tables.
    It should be called during bot startup.

    Args:
        bot: The bot instance
    """
    manager = init_permission_manager(bot)
    await manager._init_db()

    # Migrate existing admin roles from server_settings
    try:
        # Get all admin roles from server_settings
        admin_roles = await bot.db.fetch(
            """
            SELECT guild_id, admin_role_id FROM server_settings
            WHERE admin_role_id IS NOT NULL
        """
        )

        # Set permission level for each admin role
        for record in admin_roles:
            guild_id = record["guild_id"]
            role_id = record["admin_role_id"]
            await manager.set_role_permission_level(
                guild_id, role_id, PermissionLevel.ADMIN
            )

        logger.info(f"Migrated {len(admin_roles)} admin roles from server_settings")
    except Exception as e:
        logger.error(f"Error migrating admin roles: {e}")


# Permission check functions for use with commands


async def admin_or_me_check(ctx_or_interaction):
    """Check if the user is an admin or the bot owner.

    This function works with both Context objects (for traditional commands)
    and Interaction objects (for application commands).

    Args:
        ctx_or_interaction: The command context or interaction

    Returns:
        bool: True if the user is an admin or the bot owner, False otherwise
    """
    try:
        # Get the permission manager
        manager = get_permission_manager()

        # Check if the user has the MANAGE_GUILD permission
        return await manager.check_permission(
            ctx_or_interaction, Permission.MANAGE_GUILD
        )
    except Exception as e:
        # Fall back to the old check if there's an error
        logger.error(f"Error in admin_or_me_check: {e}")

        # Determine if we're dealing with a Context or an Interaction
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

        # Get the appropriate bot instance
        bot = ctx_or_interaction.client if is_interaction else ctx_or_interaction.bot

        # Get the user and guild
        user = (
            ctx_or_interaction.user
            if is_interaction
            else ctx_or_interaction.message.author
        )
        guild = ctx_or_interaction.guild

        if not guild:
            return False

        # Get user roles for efficiency
        user_roles = [role.id for role in user.roles]

        # Get the settings cog
        settings_cog = bot.get_cog("Settings")

        # Use the is_admin utility from the settings cog
        if settings_cog:
            return await settings_cog.is_admin(bot, guild.id, user.id, user_roles)
        else:
            # Fallback to the old hardcoded check if settings cog is not loaded
            role = discord.utils.get(guild.roles, id=346842813687922689)
            return bool(user.id == 268608466690506753 or role in user.roles)


def admin_or_me_check_wrapper(ctx):
    """Wrapper for async admin_or_me_check to use with @commands.check decorator.

    Args:
        ctx: The command context

    Returns:
        A check function that can be used with @commands.check
    """

    async def predicate(ctx):
        return await admin_or_me_check(ctx)

    return commands.check(predicate)


def app_admin_or_me_check(interaction):
    """Wrapper for async admin_or_me_check to use with @app_commands.check decorator.

    Args:
        interaction: The interaction object

    Returns:
        bool: True if the user is an admin or the bot owner, False otherwise
    """
    return admin_or_me_check(interaction)


async def moderator_check(ctx_or_interaction):
    """Check if the user is a moderator, admin, or the bot owner.

    This function works with both Context objects (for traditional commands)
    and Interaction objects (for application commands).

    Args:
        ctx_or_interaction: The command context or interaction

    Returns:
        bool: True if the user is a moderator, admin, or the bot owner, False otherwise
    """
    try:
        # Get the permission manager
        manager = get_permission_manager()

        # Check if the user has the BAN_MEMBERS permission
        return await manager.check_permission(
            ctx_or_interaction, Permission.BAN_MEMBERS
        )
    except Exception as e:
        # Fall back to Discord's built-in permission check
        logger.error(f"Error in moderator_check: {e}")

        # Determine if we're dealing with a Context or an Interaction
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

        # Get the user and guild
        user = ctx_or_interaction.user if is_interaction else ctx_or_interaction.author
        guild = ctx_or_interaction.guild

        if not guild:
            return False

        # Check if the user has ban_members permission
        return user.guild_permissions.ban_members


def moderator_check_wrapper(ctx):
    """Wrapper for async moderator_check to use with @commands.check decorator.

    Args:
        ctx: The command context

    Returns:
        A check function that can be used with @commands.check
    """

    async def predicate(ctx):
        return await moderator_check(ctx)

    return commands.check(predicate)


def app_moderator_check(interaction):
    """Wrapper for async moderator_check to use with @app_commands.check decorator.

    Args:
        interaction: The interaction object

    Returns:
        bool: True if the user is a moderator, admin, or the bot owner, False otherwise
    """
    return moderator_check(interaction)


async def is_bot_channel(interaction_or_ctx):
    """Check if the command is being used in the designated bot channel.

    This function works with both Context objects (for traditional commands)
    and Interaction objects (for application commands).

    Args:
        interaction_or_ctx: The command context or interaction

    Returns:
        bool: True if the command is being used in the bot channel, False otherwise
    """
    # Determine if we're dealing with a Context or an Interaction
    isinstance(interaction_or_ctx, discord.Interaction)

    # Get the channel
    channel = interaction_or_ctx.channel

    # Check if the channel ID matches the bot channel ID
    return channel.id == config.bot_channel_id


def is_bot_channel_wrapper(ctx):
    """Wrapper for is_bot_channel to use with @commands.check decorator.

    Args:
        ctx: The command context

    Returns:
        A check function that can be used with @commands.check
    """

    async def predicate(ctx):
        return await is_bot_channel(ctx)

    return commands.check(predicate)


async def app_is_bot_channel(interaction):
    """Wrapper for async is_bot_channel to use with @app_commands.check decorator.

    Args:
        interaction: The interaction object

    Returns:
        bool: True if the command is being used in the bot channel, False otherwise
    """
    return await is_bot_channel(interaction)


# Permission check decorators for easier use


def has_permission(permission: Permission | str):
    """Decorator to check if a user has a specific permission.

    This decorator works with both traditional commands and app commands.

    Args:
        permission: The permission to check

    Returns:
        A decorator that can be used with @commands.command or @app_commands.command
    """

    async def predicate(ctx_or_interaction):
        manager = get_permission_manager()
        return await manager.check_permission(ctx_or_interaction, permission)

    # For traditional commands
    def decorator(func):
        if isinstance(func, commands.Command):
            return commands.check(predicate)(func)
        else:
            return app_commands.check(predicate)(func)

    return decorator


def has_permission_level(level: PermissionLevel):
    """Decorator to check if a user has a specific permission level.

    This decorator works with both traditional commands and app commands.

    Args:
        level: The permission level to check

    Returns:
        A decorator that can be used with @commands.command or @app_commands.command
    """

    async def predicate(ctx_or_interaction) -> bool:
        # Determine if we're dealing with a Context or an Interaction
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

        # Get the user and guild
        user = ctx_or_interaction.user if is_interaction else ctx_or_interaction.author
        guild = ctx_or_interaction.guild

        if not guild:
            return False

        # Get the permission manager
        manager = get_permission_manager()

        # Get user roles for efficiency
        user_roles = [role.id for role in user.roles]

        # Get the user's permission level
        user_level = await manager.get_user_permission_level(
            guild.id, user.id, user_roles
        )

        # Check if the user's level is sufficient
        if user_level >= level:
            return True

        # Raise appropriate exception
        if level == PermissionLevel.OWNER:
            raise OwnerOnlyError()
        else:
            raise RolePermissionError(f"{level.name.lower()} role")

    # For traditional commands
    def decorator(func):
        if isinstance(func, commands.Command):
            return commands.check(predicate)(func)
        else:
            return app_commands.check(predicate)(func)

    return decorator

"""Utility commands cog for the Twi Bot Shard.

This module provides a variety of utility commands for server management, user information,
role management, and other miscellaneous functionality. It includes commands for user info,
server info, role management, quotes, dice rolling, and more.
"""

# Import standard library modules first
import asyncio
import logging
import random
import re
import time
from datetime import UTC
from itertools import groupby

# Import third-party modules in a specific order
# Discord-related imports
import discord
import structlog
from discord import app_commands
from discord.ext import commands

# Other third-party imports

# Import AO3 last to avoid potential import deadlocks
import AO3

import config
from utils.command_groups import admin
from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    DatabaseError,
    ExternalServiceError,
    PermissionError,
    ValidationError,
)
from utils.permissions import (
    app_admin_or_me_check,
)

# AO3 session will be initialized in the cog's cog_load method
# to avoid blocking the bot startup with authentication


async def user_info_function(interaction: discord.Interaction, member: discord.Member) -> None:
    """Create and send an embed with detailed information about a Discord user.

    This function creates an embed containing comprehensive information about a user,
    including their account creation date, server join date, ID, color, roles, and
    additional metadata. It's used by both the /info user command and the User Info context menu.

    Args:
        interaction: The Discord interaction object
        member: The member to get information about, defaults to the command user if None

    Raises:
        ValidationError: If member data is invalid or unavailable
        ExternalServiceError: If Discord API operations fail
    """
    try:
        # Default to command user if no member specified
        if member is None:
            member = interaction.user

        # Validate member object
        if not member:
            raise ValidationError(message="❌ Unable to identify the target user")

        logging.info(
            f"OTHER USER_INFO: User info request by user {interaction.user.id} for user {member.id} ({member.name})"
        )

        # Create enhanced embed with user's color or default
        user_color = (
            member.color
            if hasattr(member, "color") and member.color != discord.Color.default()
            else discord.Color(0x3CD63D)
        )
        embed = discord.Embed(
            title="👤 User Information",
            description=f"**{member.display_name}**\n{member.mention}",
            color=user_color,
            timestamp=discord.utils.utcnow(),
        )

        # Set thumbnail with error handling
        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception as e:
            logging.warning(
                f"OTHER USER_INFO WARNING: Could not set thumbnail for user {member.id}: {e}"
            )
            # Continue without thumbnail

        # Account creation date
        try:
            created_at = member.created_at.strftime("%d-%m-%Y @ %H:%M:%S")
            account_age = (discord.utils.utcnow() - member.created_at).days
            embed.add_field(
                name="📅 Account Created",
                value=f"{created_at}\n*({account_age} days ago)*",
                inline=True,
            )
        except Exception as e:
            logging.warning(
                f"OTHER USER_INFO WARNING: Could not format creation date for user {member.id}: {e}"
            )
            embed.add_field(name="📅 Account Created", value="*Unknown*", inline=True)

        # Server join date (only for guild members)
        if hasattr(member, "joined_at") and member.joined_at:
            try:
                joined_at = member.joined_at.strftime("%d-%m-%Y @ %H:%M:%S")
                join_age = (discord.utils.utcnow() - member.joined_at).days
                embed.add_field(
                    name="🏠 Joined Server",
                    value=f"{joined_at}\n*({join_age} days ago)*",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER USER_INFO WARNING: Could not format join date for user {member.id}: {e}"
                )
                embed.add_field(name="🏠 Joined Server", value="*Unknown*", inline=True)
        else:
            embed.add_field(
                name="🏠 Server Status", value="*Not a server member*", inline=True
            )

        # User ID and additional info
        embed.add_field(
            name="🆔 User Details",
            value=f"**ID:** {member.id}\n**Username:** {member.name}\n**Bot:** {'Yes' if member.bot else 'No'}",
            inline=True,
        )

        # User color
        if hasattr(member, "color"):
            color_hex = (
                str(member.color)
                if member.color != discord.Color.default()
                else "#000000"
            )
            embed.add_field(
                name="🎨 Color", value=f"{color_hex}\n{member.color}", inline=True
            )

        # User status and activity (for guild members)
        if hasattr(member, "status") and hasattr(member, "activity"):
            try:
                status_emoji = {
                    discord.Status.online: "🟢",
                    discord.Status.idle: "🟡",
                    discord.Status.dnd: "🔴",
                    discord.Status.offline: "⚫",
                }.get(member.status, "❓")

                status_text = f"{status_emoji} {member.status.name.title()}"
                if member.activity:
                    status_text += f"\n*{member.activity.name}*"

                embed.add_field(name="📊 Status", value=status_text, inline=True)
            except Exception as e:
                logging.warning(
                    f"OTHER USER_INFO WARNING: Could not get status for user {member.id}: {e}"
                )

        # Roles (for guild members)
        if hasattr(member, "roles") and len(member.roles) > 1:  # More than @everyone
            try:
                roles_list = []
                for role in reversed(member.roles):
                    if not role.is_default():
                        roles_list.append(role.mention)

                if roles_list:
                    # Limit roles display to prevent embed from being too long
                    if len(roles_list) > 20:
                        roles_text = (
                            "\n".join(roles_list[:20])
                            + f"\n*... and {len(roles_list) - 20} more*"
                        )
                    else:
                        roles_text = "\n".join(roles_list)

                    embed.add_field(
                        name=f"🎭 Roles ({len(roles_list)})",
                        value=roles_text,
                        inline=False,
                    )
            except Exception as e:
                logging.warning(
                    f"OTHER USER_INFO WARNING: Could not format roles for user {member.id}: {e}"
                )
                embed.add_field(
                    name="🎭 Roles", value="*Could not retrieve roles*", inline=False
                )

        # Permissions (for guild members with special permissions)
        if hasattr(member, "guild_permissions"):
            try:
                special_perms = []
                if member.guild_permissions.administrator:
                    special_perms.append("👑 Administrator")
                if member.guild_permissions.manage_guild:
                    special_perms.append("⚙️ Manage Server")
                if member.guild_permissions.manage_channels:
                    special_perms.append("📝 Manage Channels")
                if member.guild_permissions.manage_roles:
                    special_perms.append("🎭 Manage Roles")
                if member.guild_permissions.ban_members:
                    special_perms.append("🔨 Ban Members")
                if member.guild_permissions.kick_members:
                    special_perms.append("👢 Kick Members")

                if special_perms:
                    embed.add_field(
                        name="🔑 Key Permissions",
                        value="\n".join(special_perms[:6]),  # Limit to 6 permissions
                        inline=True,
                    )
            except Exception as e:
                logging.warning(
                    f"OTHER USER_INFO WARNING: Could not check permissions for user {member.id}: {e}"
                )

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        logging.info(
            f"OTHER USER_INFO: Successfully generated user info for user {member.id}"
        )
        await interaction.response.send_message(embed=embed)

    except (ValidationError, ExternalServiceError):
        # Re-raise our custom exceptions
        raise
    except discord.HTTPException as e:
        error_msg = (
            f"❌ **Discord API Error**\nFailed to send user information: {str(e)}"
        )
        logging.error(
            f"OTHER USER_INFO ERROR: Discord HTTP error for user {member.id if member else 'unknown'}: {e}"
        )
        raise ExternalServiceError(message=error_msg) from e
    except Exception as e:
        error_msg = (
            f"❌ **User Info Failed**\nUnable to retrieve user information: {str(e)}"
        )
        logging.error(
            f"OTHER USER_INFO ERROR: Unexpected error for user {member.id if member else 'unknown'}: {e}"
        )
        raise ExternalServiceError(message=error_msg) from e


class OtherCogs(commands.Cog, name="Other"):
    """Cog providing various utility commands for server management and user interaction.

    This cog includes commands for user information, server information, role management,
    quotes, dice rolling, and other utility functions. It also provides context menu
    commands for pinning messages and viewing user information.

    Attributes:
        bot: The bot instance
        quote_cache: Cache of quotes for autocomplete
        category_cache: Cache of role categories for autocomplete
        pin_cache: Cache of channels where pinning is allowed
    """

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the OtherCogs cog.

        Args:
            bot: The bot instance to which this cog is attached
        """
        self.bot: commands.Bot = bot
        self.logger = structlog.get_logger("cogs.other")
        self.quote_cache = None
        self.category_cache = None
        self.pin_cache = None
        self.ao3_session = None
        self.ao3_login_successful = False
        self.ao3_login_in_progress = False

        self.pin = app_commands.ContextMenu(
            name="Pin",
            callback=self.pin,
        )
        self.bot.tree.add_command(self.pin)

        self.info_user_context = app_commands.ContextMenu(
            name="User info",
            callback=self.info_user_context,
        )
        self.bot.tree.add_command(self.info_user_context)

    async def _initialize_ao3_session(self, max_retries: int = 3) -> None:
        """Initialize AO3 session with retry logic.

        This method runs the blocking AO3 authentication in an executor to avoid
        blocking the event loop. If authentication fails, it will retry with
        exponential backoff up to max_retries times.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
        """
        if self.ao3_login_in_progress:
            self.logger.warning("AO3 login already in progress, skipping duplicate attempt")
            return

        self.ao3_login_in_progress = True

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(f"Attempting AO3 login (attempt {attempt}/{max_retries})")

                # Run the blocking AO3.Session call in an executor to avoid blocking the event loop
                loop = asyncio.get_event_loop()
                session = await loop.run_in_executor(
                    None,  # Use default executor
                    AO3.Session,
                    str(config.ao3_username),
                    str(config.ao3_password)
                )

                self.ao3_session = session
                self.ao3_login_successful = True
                self.logger.info("AO3 login successful")
                self.ao3_login_in_progress = False
                return

            except Exception as e:
                self.logger.error(
                    f"AO3 login failed (attempt {attempt}/{max_retries}): {e}",
                    exc_info=True
                )

                if attempt < max_retries:
                    # Exponential backoff: 2^attempt seconds (2, 4, 8...)
                    wait_time = 2 ** attempt
                    self.logger.info(f"Retrying AO3 login in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error("AO3 login failed after all retry attempts")
                    self.ao3_login_successful = False

        self.ao3_login_in_progress = False

    async def cog_load(self) -> None:
        """Load initial data when the cog is added to the bot.

        This method is called automatically when the cog is loaded.
        It populates the quote cache, category cache, and pin cache
        for use in commands and autocomplete. It also initiates the
        AO3 login process in the background.
        """
        # Bind commands in the admin group to this cog instance
        # Commands added to external groups don't get automatically bound
        cog_method_names = {"ao3_status", "set_pin_channels"}

        for cmd in admin.commands:
            if cmd.callback.__name__ in cog_method_names:
                cmd.binding = self

        self.quote_cache = await self.bot.db.fetch(
            "SELECT quote, row_number FROM (SELECT quote, ROW_NUMBER () OVER () FROM quotes) x"
        )
        self.category_cache = await self.bot.db.fetch(
            "SELECT DISTINCT (category) FROM roles WHERE category IS NOT NULL"
        )
        self.pin_cache = await self.bot.db.fetch(
            "SELECT id FROM channels where allow_pins = TRUE"
        )

        # Start AO3 login in background (don't await to avoid blocking cog load)
        asyncio.create_task(self._initialize_ao3_session())

    @admin.command(
        name="ao3_status",
        description="Check AO3 authentication status or retry login",
    )
    @app_commands.describe(retry="Set to True to retry AO3 login")
    @app_commands.checks.has_permissions(administrator=True)
    @handle_interaction_errors
    async def ao3_status(self, interaction: discord.Interaction, retry: bool = False) -> None:
        """Check AO3 authentication status or manually retry login.

        This admin command allows checking the current AO3 authentication status
        and optionally retry the login process if it previously failed.

        Args:
            interaction: The Discord interaction object
            retry: Whether to retry the AO3 login process

        Raises:
            PermissionError: If user lacks administrator permissions
        """
        await interaction.response.defer(ephemeral=True)

        if retry:
            if self.ao3_login_in_progress:
                await interaction.followup.send(
                    "⏳ AO3 login is already in progress. Please wait...",
                    ephemeral=True
                )
                return

            self.logger.info(f"Admin {interaction.user.id} triggered manual AO3 login retry")
            await interaction.followup.send(
                "🔄 Retrying AO3 login... This may take up to 90 seconds per attempt.",
                ephemeral=True
            )

            # Retry login in background
            asyncio.create_task(self._initialize_ao3_session())

            # Wait a moment and check status
            await asyncio.sleep(2)

            if self.ao3_login_successful:
                await interaction.edit_original_response(
                    content="✅ AO3 login successful!"
                )
            elif self.ao3_login_in_progress:
                await interaction.edit_original_response(
                    content="⏳ AO3 login in progress... Check status again in a moment."
                )
            else:
                await interaction.edit_original_response(
                    content="❌ AO3 login failed. Check bot logs for details."
                )
        else:
            # Just check status
            if self.ao3_login_successful:
                status_msg = "✅ **AO3 Status: Connected**\nAuthentication is working properly."
            elif self.ao3_login_in_progress:
                status_msg = "⏳ **AO3 Status: Connecting**\nLogin attempt in progress..."
            else:
                status_msg = "❌ **AO3 Status: Disconnected**\nAuthentication failed. Use `retry: True` to retry."

            await interaction.followup.send(status_msg, ephemeral=True)

    @app_commands.command(
        name="ping",
        description="Gives the latency of the bot",
    )
    @handle_interaction_errors
    async def ping(self, interaction: discord.Interaction) -> None:
        """Display the bot's current latency to Discord.

        This command calculates and displays the bot's WebSocket latency to Discord
        in milliseconds, which can be useful for diagnosing connection issues.
        Also provides additional timing information for comprehensive diagnostics.

        Args:
            interaction: The Discord interaction object

        Raises:
            ExternalServiceError: If latency measurement fails
            ValidationError: If interaction timing is invalid
        """
        try:
            # Record start time for response latency calculation
            start_time = time.time()

            # Get WebSocket latency
            ws_latency = self.bot.latency
            if ws_latency < 0:
                raise ValidationError(message="❌ Invalid latency measurement received")

            ws_latency_ms = round(ws_latency * 1000, 2)

            # Defer to measure response time
            await interaction.response.defer()

            # Calculate response latency
            response_time = round((time.time() - start_time) * 1000, 2)

            # Determine latency status with emojis
            if ws_latency_ms < 100:
                status_emoji = "🟢"
                status_text = "Excellent"
            elif ws_latency_ms < 200:
                status_emoji = "🟡"
                status_text = "Good"
            elif ws_latency_ms < 500:
                status_emoji = "🟠"
                status_text = "Fair"
            else:
                status_emoji = "🔴"
                status_text = "Poor"

            # Create embed with detailed ping information
            embed = discord.Embed(
                title="🏓 Bot Latency Information",
                color=(
                    discord.Color.green()
                    if ws_latency_ms < 200
                    else (
                        discord.Color.orange()
                        if ws_latency_ms < 500
                        else discord.Color.red()
                    )
                ),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="WebSocket Latency",
                value=f"{status_emoji} **{ws_latency_ms}ms**\n*{status_text}*",
                inline=True,
            )

            embed.add_field(
                name="Response Time",
                value=f"⚡ **{response_time}ms**\n*API Response*",
                inline=True,
            )

            embed.add_field(
                name="Bot Status", value="🤖 **Online**\n*Ready to serve*", inline=True
            )

            embed.set_footer(text="Latency measured to Discord's servers")

            logging.info(
                f"OTHER PING: Latency check by user {interaction.user.id} - WS: {ws_latency_ms}ms, Response: {response_time}ms"
            )
            await interaction.followup.send(embed=embed)

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = (
                f"❌ **Ping Measurement Failed**\nUnable to measure latency: {str(e)}"
            )
            logging.error(
                f"OTHER PING ERROR: Failed to measure latency for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @app_commands.command(
        name="avatar", description="Posts the full version of a avatar"
    )
    @handle_interaction_errors
    async def av(
        self, interaction: discord.Interaction, member: discord.Member = None
    ) -> None:
        """Display the full-size avatar of a user.

        This command creates an embed containing the full-size version of a user's
        avatar, which can be useful for viewing avatars in higher resolution.
        Supports both server-specific and global avatars.

        Args:
            interaction: The Discord interaction object
            member: The member whose avatar to display, defaults to the command user if None

        Raises:
            ValidationError: If member data is invalid or unavailable
            ExternalServiceError: If avatar URL cannot be retrieved
        """
        try:
            # Default to command user if no member specified
            if member is None:
                member = interaction.user

            # Validate member object
            if not member:
                raise ValidationError(message="❌ Unable to identify the target user")

            logging.info(
                f"OTHER AVATAR: Avatar request by user {interaction.user.id} for user {member.id} ({member.name})"
            )

            # Get avatar URLs with fallbacks
            try:
                # Try to get server-specific avatar first, fall back to global avatar
                if hasattr(member, "guild_avatar") and member.guild_avatar:
                    avatar_url = member.guild_avatar.url
                    avatar_type = "Server Avatar"
                    avatar_emoji = "🏠"
                else:
                    avatar_url = member.display_avatar.url
                    avatar_type = "Global Avatar"
                    avatar_emoji = "🌐"

                if not avatar_url:
                    raise ExternalServiceError(
                        message="❌ Avatar URL could not be retrieved"
                    )

            except AttributeError as e:
                logging.warning(
                    f"OTHER AVATAR WARNING: Avatar attribute error for user {member.id}: {e}"
                )
                # Fallback to basic avatar
                avatar_url = (
                    member.default_avatar.url
                    if hasattr(member, "default_avatar")
                    else None
                )
                avatar_type = "Default Avatar"
                avatar_emoji = "👤"

                if not avatar_url:
                    raise ExternalServiceError(
                        message="❌ No avatar available for this user"
                    )

            # Create enhanced embed
            embed = discord.Embed(
                title=f"{avatar_emoji} {avatar_type}",
                description=f"**{member.display_name}**\n{member.mention}",
                color=(
                    member.color
                    if hasattr(member, "color")
                    and member.color != discord.Color.default()
                    else discord.Color(0x3CD63D)
                ),
                timestamp=discord.utils.utcnow(),
            )

            # Set the avatar image
            embed.set_image(url=avatar_url)

            # Add user information
            embed.add_field(
                name="👤 User Info",
                value=f"**ID:** {member.id}\n**Username:** {member.name}",
                inline=True,
            )

            # Add avatar format information
            try:
                avatar_format = avatar_url.split(".")[-1].split("?")[0].upper()
                embed.add_field(
                    name="🖼️ Format",
                    value=f"**Type:** {avatar_format}\n**High Resolution:** [Click here]({avatar_url})",
                    inline=True,
                )
            except Exception:
                # If format detection fails, just show the URL
                embed.add_field(
                    name="🖼️ Direct Link",
                    value=f"[High Resolution]({avatar_url})",
                    inline=True,
                )

            # Add timestamp info
            if hasattr(member, "created_at"):
                embed.set_footer(
                    text=f"Account created: {member.created_at.strftime('%Y-%m-%d')}"
                )

            logging.info(
                f"OTHER AVATAR: Successfully retrieved {avatar_type.lower()} for user {member.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except discord.HTTPException as e:
            error_msg = f"❌ **Discord API Error**\nFailed to send avatar: {str(e)}"
            logging.error(
                f"OTHER AVATAR ERROR: Discord HTTP error for user {member.id if member else 'unknown'}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e
        except Exception as e:
            error_msg = (
                f"❌ **Avatar Display Failed**\nUnable to display avatar: {str(e)}"
            )
            logging.error(
                f"OTHER AVATAR ERROR: Unexpected error for user {member.id if member else 'unknown'}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    info = app_commands.Group(name="info", description="Information commands")

    @info.command(
        name="user",
        description="Gives the account information of a user.",
    )
    @handle_interaction_errors
    async def info_user(
        self, interaction: discord.Interaction, member: discord.Member = None
    ) -> None:
        """Display detailed information about a Discord user.

        This command shows comprehensive information about a user, including their account
        creation date, server join date, ID, color, roles, permissions, and status.
        Provides enhanced formatting and graceful error handling.

        Args:
            interaction: The Discord interaction object
            member: The member to get information about, defaults to the command user if None

        Raises:
            ValidationError: If member data is invalid or unavailable
            ExternalServiceError: If Discord API operations fail
        """
        try:
            logging.info(
                f"OTHER INFO_USER: User info command invoked by user {interaction.user.id} for user {member.id if member else 'self'}"
            )
            await user_info_function(interaction, member)
        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Info User Command Failed**\nUnable to process user info request: {str(e)}"
            logging.error(
                f"OTHER INFO_USER ERROR: Unexpected error in info_user command: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @handle_interaction_errors
    async def info_user_context(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Context menu command to display detailed information about a Discord user.

        This context menu command shows the same comprehensive information as the /info user command,
        but can be accessed by right-clicking on a user. Provides enhanced formatting and
        graceful error handling.

        Args:
            interaction: The Discord interaction object
            member: The member to get information about

        Raises:
            ValidationError: If member data is invalid or unavailable
            ExternalServiceError: If Discord API operations fail
        """
        try:
            logging.info(
                f"OTHER INFO_USER_CONTEXT: Context menu user info invoked by user {interaction.user.id} for user {member.id}"
            )
            await user_info_function(interaction, member)
        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Context User Info Failed**\nUnable to process user info request: {str(e)}"
            logging.error(
                f"OTHER INFO_USER_CONTEXT ERROR: Unexpected error in context menu user info: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @info.command(
        name="server",
        description="Gives the server information of the server the command was used in.",
    )
    @handle_interaction_errors
    async def info_server(self, interaction: discord.Interaction) -> None:
        """Display detailed information about the current Discord server.

        This command shows comprehensive information about the server, including
        its creation date, owner, member count, role count, emoji counts, channels,
        and various server features with enhanced formatting and error handling.

        Args:
            interaction: The Discord interaction object

        Raises:
            ValidationError: If guild context is missing or invalid
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Validate guild context
            if not interaction.guild:
                raise ValidationError(
                    message="❌ This command can only be used in a server"
                )

            guild = interaction.guild
            logging.info(
                f"OTHER INFO_SERVER: Server info requested by user {interaction.user.id} for guild {guild.id} ({guild.name})"
            )

            # Create enhanced embed
            embed = discord.Embed(
                title=f"🏰 {guild.name}",
                description=(
                    guild.description if guild.description else "*No description set*"
                ),
                color=discord.Color(0x3CD63D),
                timestamp=discord.utils.utcnow(),
            )

            # Set thumbnail with error handling
            try:
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not set thumbnail for guild {guild.id}: {e}"
                )

            # Basic server information
            try:
                created_at = guild.created_at.strftime("%d-%m-%Y @ %H:%M:%S")
                server_age = (discord.utils.utcnow() - guild.created_at).days
                embed.add_field(
                    name="📅 Created",
                    value=f"{created_at}\n*({server_age} days ago)*",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not format creation date for guild {guild.id}: {e}"
                )
                embed.add_field(name="📅 Created", value="*Unknown*", inline=True)

            # Server ID and owner
            try:
                owner_text = guild.owner.mention if guild.owner else "*Unknown*"
                embed.add_field(
                    name="👑 Owner",
                    value=f"{owner_text}\n**ID:** {guild.id}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not get owner info for guild {guild.id}: {e}"
                )
                embed.add_field(
                    name="👑 Owner", value=f"*Unknown*\n**ID:** {guild.id}", inline=True
                )

            # Member information
            try:
                member_count = guild.member_count if guild.member_count else "Unknown"
                # Get approximate member counts by status if available
                online_count = (
                    sum(1 for m in guild.members if m.status != discord.Status.offline)
                    if guild.members
                    else "Unknown"
                )
                embed.add_field(
                    name="👥 Members",
                    value=f"**Total:** {member_count}\n**Online:** {online_count}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not get member info for guild {guild.id}: {e}"
                )
                embed.add_field(name="👥 Members", value="*Unknown*", inline=True)

            # Roles information
            try:
                role_count = len(guild.roles) - 1  # Exclude @everyone
                embed.add_field(
                    name="🎭 Roles",
                    value=f"**Count:** {role_count}/250\n**Highest:** {guild.roles[-1].mention if len(guild.roles) > 1 else '@everyone'}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not get role info for guild {guild.id}: {e}"
                )
                embed.add_field(name="🎭 Roles", value="*Unknown*", inline=True)

            # Channel information
            try:
                text_channels = len(guild.text_channels)
                voice_channels = len(guild.voice_channels)
                categories = len(guild.categories)
                embed.add_field(
                    name="📝 Channels",
                    value=f"**Text:** {text_channels}\n**Voice:** {voice_channels}\n**Categories:** {categories}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not get channel info for guild {guild.id}: {e}"
                )
                embed.add_field(name="📝 Channels", value="*Unknown*", inline=True)

            # Emoji and sticker information
            try:
                normal_emojis = sum(1 for emoji in guild.emojis if not emoji.animated)
                animated_emojis = sum(1 for emoji in guild.emojis if emoji.animated)
                sticker_count = len(guild.stickers)

                embed.add_field(
                    name="😀 Emojis & Stickers",
                    value=f"**Static:** {normal_emojis}/{guild.emoji_limit}\n**Animated:** {animated_emojis}/{guild.emoji_limit}\n**Stickers:** {sticker_count}/{guild.sticker_limit}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not get emoji/sticker info for guild {guild.id}: {e}"
                )
                embed.add_field(
                    name="😀 Emojis & Stickers", value="*Unknown*", inline=True
                )

            # Active threads
            try:
                active_threads = await guild.active_threads()
                thread_count = len(active_threads)
                embed.add_field(
                    name="🧵 Active Threads",
                    value=f"**Count:** {thread_count}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not get thread info for guild {guild.id}: {e}"
                )
                embed.add_field(
                    name="🧵 Active Threads", value="*Unknown*", inline=True
                )

            # Server features and boosts
            try:
                features_text = ""
                if guild.premium_tier > 0:
                    features_text += f"**Boost Level:** {guild.premium_tier}\n**Boosts:** {guild.premium_subscription_count}\n"

                if guild.verification_level:
                    features_text += (
                        f"**Verification:** {guild.verification_level.name.title()}\n"
                    )

                if guild.vanity_url:
                    features_text += f"**Vanity URL:** {guild.vanity_url}\n"

                if not features_text:
                    features_text = "*No special features*"

                embed.add_field(
                    name="✨ Features", value=features_text.strip(), inline=False
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not get server features for guild {guild.id}: {e}"
                )

            # Banner
            try:
                if guild.banner:
                    embed.set_image(url=guild.banner.url)
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_SERVER WARNING: Could not set banner for guild {guild.id}: {e}"
                )

            embed.set_footer(text=f"Requested by {interaction.user.display_name}")

            logging.info(
                f"OTHER INFO_SERVER: Successfully generated server info for guild {guild.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except discord.HTTPException as e:
            error_msg = (
                f"❌ **Discord API Error**\nFailed to send server information: {str(e)}"
            )
            logging.error(
                f"OTHER INFO_SERVER ERROR: Discord HTTP error for guild {interaction.guild.id if interaction.guild else 'unknown'}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e
        except Exception as e:
            error_msg = f"❌ **Server Info Failed**\nUnable to retrieve server information: {str(e)}"
            logging.error(
                f"OTHER INFO_SERVER ERROR: Unexpected error for guild {interaction.guild.id if interaction.guild else 'unknown'}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @info.command(
        name="role", description="Gives the role information of the role given."
    )
    @handle_interaction_errors
    async def info_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        """Display detailed information about a Discord role.

        This command shows comprehensive information about a role, including its color,
        creation date, whether it's hoisted (displayed separately), permissions,
        ID, and the number of members who have the role with enhanced formatting.

        Args:
            interaction: The Discord interaction object
            role: The role to get information about

        Raises:
            ValidationError: If role data is invalid or unavailable
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Validate role object
            if not role:
                raise ValidationError(message="❌ Unable to identify the target role")

            logging.info(
                f"OTHER INFO_ROLE: Role info requested by user {interaction.user.id} for role {role.id} ({role.name})"
            )

            # Create enhanced embed with role color
            role_color = (
                discord.Color(role.color.value)
                if role.color.value != 0
                else discord.Color(0x3CD63D)
            )
            embed = discord.Embed(
                title=f"🎭 {role.name}",
                color=role_color,
                timestamp=discord.utils.utcnow(),
            )

            # Basic role information
            try:
                created_at = role.created_at.strftime("%d-%m-%Y @ %H:%M:%S")
                role_age = (discord.utils.utcnow() - role.created_at).days
                embed.add_field(
                    name="📅 Created",
                    value=f"{created_at}\n*({role_age} days ago)*",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_ROLE WARNING: Could not format creation date for role {role.id}: {e}"
                )
                embed.add_field(name="📅 Created", value="*Unknown*", inline=True)

            # Role ID and position
            try:
                position = role.position
                total_roles = len(role.guild.roles) if role.guild else "Unknown"
                embed.add_field(
                    name="🆔 Details",
                    value=f"**ID:** {role.id}\n**Position:** {position}/{total_roles}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_ROLE WARNING: Could not get role details for role {role.id}: {e}"
                )
                embed.add_field(
                    name="🆔 Details",
                    value=f"**ID:** {role.id}\n**Position:** *Unknown*",
                    inline=True,
                )

            # Role color information
            try:
                color_hex = (
                    hex(role.color.value) if role.color.value != 0 else "#000000"
                )
                color_rgb = f"({role.color.r}, {role.color.g}, {role.color.b})"
                embed.add_field(
                    name="🎨 Color",
                    value=f"**Hex:** {color_hex}\n**RGB:** {color_rgb}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_ROLE WARNING: Could not get color info for role {role.id}: {e}"
                )
                embed.add_field(name="🎨 Color", value="*Unknown*", inline=True)

            # Role properties
            try:
                properties = []
                if role.hoist:
                    properties.append("📌 Hoisted")
                if role.mentionable:
                    properties.append("📢 Mentionable")
                if role.managed:
                    properties.append("🤖 Managed")
                if role.is_default():
                    properties.append("👥 Default Role")
                if role.is_premium_subscriber():
                    properties.append("💎 Booster Role")
                if role.is_bot_managed():
                    properties.append("🤖 Bot Role")
                if role.is_integration():
                    properties.append("🔗 Integration Role")

                properties_text = (
                    "\n".join(properties) if properties else "*No special properties*"
                )
                embed.add_field(name="⚙️ Properties", value=properties_text, inline=True)
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_ROLE WARNING: Could not get properties for role {role.id}: {e}"
                )
                embed.add_field(name="⚙️ Properties", value="*Unknown*", inline=True)

            # Member count
            try:
                member_count = len(role.members)
                total_members = (
                    role.guild.member_count
                    if role.guild and role.guild.member_count
                    else "Unknown"
                )
                percentage = (
                    f"({member_count / role.guild.member_count * 100:.1f}%)"
                    if role.guild and role.guild.member_count
                    else ""
                )

                embed.add_field(
                    name="👥 Members",
                    value=f"**Count:** {member_count}/{total_members}\n{percentage}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_ROLE WARNING: Could not get member count for role {role.id}: {e}"
                )
                embed.add_field(name="👥 Members", value="*Unknown*", inline=True)

            # Key permissions
            try:
                key_perms = []
                if role.permissions.administrator:
                    key_perms.append("👑 Administrator")
                if role.permissions.manage_guild:
                    key_perms.append("⚙️ Manage Server")
                if role.permissions.manage_channels:
                    key_perms.append("📝 Manage Channels")
                if role.permissions.manage_roles:
                    key_perms.append("🎭 Manage Roles")
                if role.permissions.ban_members:
                    key_perms.append("🔨 Ban Members")
                if role.permissions.kick_members:
                    key_perms.append("👢 Kick Members")
                if role.permissions.manage_messages:
                    key_perms.append("🗑️ Manage Messages")
                if role.permissions.mention_everyone:
                    key_perms.append("📢 Mention Everyone")

                if key_perms:
                    perms_text = "\n".join(key_perms[:8])  # Limit to 8 permissions
                    if len(key_perms) > 8:
                        perms_text += f"\n*... and {len(key_perms) - 8} more*"
                else:
                    perms_text = "*No special permissions*"

                embed.add_field(
                    name="🔑 Key Permissions", value=perms_text, inline=False
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_ROLE WARNING: Could not get permissions for role {role.id}: {e}"
                )
                embed.add_field(
                    name="🔑 Key Permissions", value="*Unknown*", inline=False
                )

            # Role mention
            try:
                embed.add_field(
                    name="📝 Mention",
                    value=f"`{role.mention}` → {role.mention}",
                    inline=False,
                )
            except Exception as e:
                logging.warning(
                    f"OTHER INFO_ROLE WARNING: Could not format mention for role {role.id}: {e}"
                )

            embed.set_footer(text=f"Requested by {interaction.user.display_name}")

            logging.info(
                f"OTHER INFO_ROLE: Successfully generated role info for role {role.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except discord.HTTPException as e:
            error_msg = (
                f"❌ **Discord API Error**\nFailed to send role information: {str(e)}"
            )
            logging.error(
                f"OTHER INFO_ROLE ERROR: Discord HTTP error for role {role.id if role else 'unknown'}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e
        except Exception as e:
            error_msg = f"❌ **Role Info Failed**\nUnable to retrieve role information: {str(e)}"
            logging.error(
                f"OTHER INFO_ROLE ERROR: Unexpected error for role {role.id if role else 'unknown'}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @app_commands.command(
        name="say",
        description="Makes Cognita repeat whatever was said",
    )
    @commands.is_owner()
    @handle_interaction_errors
    async def say(
        self,
        interaction: discord.Interaction,
        say: str,
        channel: discord.TextChannel = None,
    ) -> None:
        """Make the bot repeat a message in the current channel or a specified channel.

        This owner-only command makes the bot send a message with the specified content
        in the current channel (if no channel is specified) or in the specified channel.
        Includes comprehensive security checks, content validation, and detailed logging for audit purposes.

        Args:
            interaction: The Discord interaction object
            say: The message content to repeat
            channel: Optional channel to send the message to (defaults to current channel)

        Raises:
            ValidationError: If message content or channel is invalid or contains prohibited content
            PermissionError: If user lacks required permissions or bot cannot access channel
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Input validation
            if not say or len(say.strip()) == 0:
                raise ValidationError(message="❌ Message content cannot be empty")

            say = say.strip()

            # Determine target channel (use provided channel or current channel)
            target_channel = channel if channel else interaction.channel

            # Content length validation
            if len(say) > 2000:
                raise ValidationError(
                    message="❌ Message too long (maximum 2000 characters)"
                )

            # Security checks - content filtering
            prohibited_patterns = [
                r"@everyone",
                r"@here",
                r"<@&\d+>",  # Role mentions
                r"discord\.gg/",  # Discord invites
                r"https?://discord\.com/invite/",  # Discord invites
            ]

            import re

            for pattern in prohibited_patterns:
                if re.search(pattern, say, re.IGNORECASE):
                    logging.warning(
                        f"OTHER SAY SECURITY: Prohibited content detected by user {interaction.user.id}: '{pattern}' in '{say[:100]}'"
                    )
                    raise ValidationError(
                        message=f"❌ Message contains prohibited content: {pattern}"
                    )

            # Additional security checks
            if say.count("@") > 5:  # Prevent mass mentions
                raise ValidationError(
                    message="❌ Too many mentions in message (maximum 5)"
                )

            if len(say.split("\n")) > 20:  # Prevent spam with excessive newlines
                raise ValidationError(
                    message="❌ Too many line breaks in message (maximum 20)"
                )

            # Channel validation (only if a specific channel was provided)
            if channel:
                if not isinstance(channel, discord.TextChannel):
                    raise ValidationError(message="❌ Target must be a text channel")

                # Cross-guild channel validation
                if interaction.guild and channel.guild != interaction.guild:
                    logging.warning(
                        f"OTHER SAY SECURITY: Cross-guild channel access attempted by user {interaction.user.id}: source guild {interaction.guild.id}, target guild {channel.guild.id}"
                    )
                    raise PermissionError(
                        message="❌ Cannot send messages to channels in other servers"
                    )

            # Log the command usage for security audit
            if channel:
                logging.info(
                    f"OTHER SAY: Say command used by owner {interaction.user.id} ({interaction.user.name}) targeting channel {target_channel.id} ({target_channel.name}) in guild {target_channel.guild.id if target_channel.guild else 'DM'}"
                )
            else:
                logging.info(
                    f"OTHER SAY: Say command used by owner {interaction.user.id} ({interaction.user.name}) in channel {interaction.channel.id} ({'DM' if isinstance(interaction.channel, discord.DMChannel) else interaction.channel.name})"
                )
            logging.info(
                f"OTHER SAY CONTENT: '{say[:200]}{'...' if len(say) > 200 else ''}'"
            )

            # Validate bot permissions in target channel
            if target_channel.guild:
                bot_member = target_channel.guild.get_member(interaction.client.user.id)
                if not bot_member:
                    raise PermissionError(
                        message=(
                            "❌ Bot is not a member of the target channel's server"
                            if channel
                            else "❌ Bot member not found in guild"
                        )
                    )

                channel_perms = target_channel.permissions_for(bot_member)
                if not channel_perms.send_messages:
                    raise PermissionError(
                        message=(
                            f"❌ Bot lacks permission to send messages in {target_channel.mention}"
                            if channel
                            else "❌ Bot lacks permission to send messages in this channel"
                        )
                    )

                if channel and not channel_perms.view_channel:
                    raise PermissionError(
                        message=f"❌ Bot cannot view the target channel {target_channel.mention}"
                    )

                if not channel_perms.embed_links and any(
                    word in say.lower() for word in ["http", "www", ".com", ".org"]
                ):
                    logging.warning(
                        "OTHER SAY WARNING: Bot lacks embed permissions in target channel but message contains links"
                        if channel
                        else "OTHER SAY WARNING: Bot lacks embed permissions but message contains links"
                    )

            # Additional channel-specific checks (only if a specific channel was provided)
            if channel:
                try:
                    # Check if channel is accessible
                    (
                        await target_channel.fetch_message(
                            target_channel.last_message_id
                        )
                        if target_channel.last_message_id
                        else None
                    )
                except discord.NotFound:
                    # Channel exists but no messages, that's fine
                    pass
                except discord.Forbidden:
                    raise PermissionError(
                        message=f"❌ Bot lacks access to read {target_channel.mention}"
                    )
                except Exception as e:
                    logging.warning(
                        f"OTHER SAY WARNING: Could not verify channel access for {target_channel.id}: {e}"
                    )

            # Send the actual message to target channel first
            try:
                sent_message = await target_channel.send(say)
                if channel:
                    logging.info(
                        f"OTHER SAY SUCCESS: Message sent successfully to channel {target_channel.id} with message ID {sent_message.id}"
                    )
                else:
                    logging.info(
                        f"OTHER SAY SUCCESS: Message sent successfully with ID {sent_message.id}"
                    )

                # Send confirmation to user (ephemeral) after successful send
                # Truncate message content for display if too long
                display_message = say if len(say) <= 100 else say[:100] + "..."

                if channel:
                    # Include jump URL when a specific channel was provided
                    jump_url = f"https://discord.com/channels/{target_channel.guild.id if target_channel.guild else '@me'}/{target_channel.id}/{sent_message.id}"
                    await interaction.response.send_message(
                        f"✅ **Message Sent Successfully**\n**Target Channel:** {target_channel.mention}\n**Server:** {target_channel.guild.name if target_channel.guild else 'DM'}\n**Message:** {display_message}\n**Jump to Message:** {jump_url}",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        f"✅ **Message Sent Successfully**\n**Channel:** {target_channel.mention if hasattr(target_channel, 'mention') else 'DM'}\n**Message:** {display_message}",
                        ephemeral=True,
                    )

            except discord.HTTPException as e:
                if channel:
                    error_msg = f"❌ **Failed to Send Message**\nDiscord API Error: {str(e)}\n**Target:** {target_channel.mention}"
                    logging.error(
                        f"OTHER SAY ERROR: Discord HTTP error when sending to channel {target_channel.id}: {e}"
                    )
                else:
                    error_msg = (
                        f"❌ **Failed to Send Message**\nDiscord API Error: {str(e)}"
                    )
                    logging.error(
                        f"OTHER SAY ERROR: Discord HTTP error when sending message: {e}"
                    )
                raise ExternalServiceError(message=error_msg) from e

        except (ValidationError, PermissionError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Say Command Failed**\nUnexpected error: {str(e)}"
            logging.error(f"OTHER SAY ERROR: Unexpected error in say command: {e}")
            raise ExternalServiceError(message=error_msg) from e

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """Event handler for when a member's roles are updated.

        This listener detects when a member gains a special role and sends a themed
        announcement message to the inn general channel. Each special role has a
        unique announcement message themed around The Wandering Inn.

        Args:
            before: The member's state before the update
            after: The member's state after the update
        """
        # Acid jars, Acid Flies, Frying Pans, Enchanted Soup, Barefoot Clients.
        # Green, Purple, Orange, Blue, Red
        list_of_ids = [
            config.special_role_ids["acid_jars"],
            config.special_role_ids["acid_flies"],
            config.special_role_ids["frying_pans"],
            config.special_role_ids["enchanted_soup"],
            config.special_role_ids["barefoot_clients"],
        ]
        gained = set(after.roles) - set(before.roles)
        if gained:
            gained = gained.pop()
            if gained.id in list_of_ids:
                channel = self.bot.get_channel(config.inn_general_channel_id)
                # Acid jar
                if gained.id == config.special_role_ids["acid_jars"]:
                    embed = discord.Embed(
                        title="Hey be careful over there!",
                        description=f"Those {gained.mention} will melt your hands off {after.mention}!",
                    )
                # Acid Flies
                elif gained.id == config.special_role_ids["acid_flies"]:
                    embed = discord.Embed(
                        title="Make some room at the tables!",
                        description=f"{after.mention} just ordered a bowl of {gained.mention}!",
                    )
                # Frying Pans
                elif gained.id == config.special_role_ids["frying_pans"]:
                    embed = discord.Embed(
                        title="Someone ordered a frying pan!",
                        description=f"Hope {after.mention} can dodge!",
                    )
                # Enchanted Soup
                elif gained.id == config.special_role_ids["enchanted_soup"]:
                    embed = discord.Embed(
                        title="Hey get down from there Mrsha!",
                        description=f"Looks like {after.mention} will have to order a new serving of {gained.mention} because Mrsha just ate theirs!",
                    )
                # Barefoot Clients
                elif gained.id == config.special_role_ids["barefoot_clients"]:
                    embed = discord.Embed(
                        title="Make way!",
                        description=f"{gained.mention} {after.mention} coming through!",
                    )
                else:
                    embed = discord.Embed(
                        title="Make some room in the inn!",
                        description=f"{after.mention} just joined the ranks of {gained.mention}!",
                    )
                embed.set_thumbnail(url=after.display_avatar.url)
                await channel.send(embed=embed, content=f"{after.mention}")

    quote = app_commands.Group(name="quote", description="Quote commands")

    @quote.command(name="add", description="Adds a quote to the list of quotes")
    @handle_interaction_errors
    async def quote_add(self, interaction: discord.Interaction, quote: str) -> None:
        """Add a new quote to the database.

        This command adds a new quote to the database, recording the author's name,
        ID, and the current timestamp. It also updates the quote cache for autocomplete.
        Includes comprehensive error handling and input validation.

        Args:
            interaction: The Discord interaction object
            quote: The quote text to add

        Raises:
            ValidationError: If quote content is invalid or too long
            DatabaseError: If database operations fail
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Input validation
            if not quote or len(quote.strip()) == 0:
                raise ValidationError(message="❌ Quote cannot be empty")

            quote = quote.strip()

            # Content length validation
            if len(quote) > 2000:
                raise ValidationError(
                    message="❌ Quote too long (maximum 2000 characters)"
                )

            # Content validation - prevent abuse
            if len(quote) < 3:
                raise ValidationError(
                    message="❌ Quote too short (minimum 3 characters)"
                )

            # Check for excessive newlines or special characters
            if quote.count("\n") > 10:
                raise ValidationError(
                    message="❌ Too many line breaks in quote (maximum 10)"
                )

            logging.info(
                f"OTHER QUOTE_ADD: Quote add request by user {interaction.user.id} ({interaction.user.display_name}): '{quote[:100]}{'...' if len(quote) > 100 else ''}'"
            )

            # Insert quote into database with error handling
            try:
                await self.bot.db.execute(
                    "INSERT INTO quotes(quote, author, author_id, time, tokens) VALUES ($1,$2,$3,now(),to_tsvector($4))",
                    quote,
                    interaction.user.display_name,
                    interaction.user.id,
                    quote,
                )
            except Exception as e:
                logging.error(
                    f"OTHER QUOTE_ADD ERROR: Database insert failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"❌ Failed to add quote to database: {str(e)}"
                )

            # Get the new quote count
            try:
                row_number = await self.bot.db.fetchrow("SELECT COUNT(*) FROM quotes")
                quote_index = row_number["count"] if row_number else "Unknown"
            except Exception as e:
                logging.warning(
                    f"OTHER QUOTE_ADD WARNING: Could not get quote count: {e}"
                )
                quote_index = "Unknown"

            # Update quote cache
            try:
                self.quote_cache = await self.bot.db.fetch(
                    "SELECT quote, row_number FROM (SELECT quote, ROW_NUMBER () OVER () FROM quotes) x"
                )
                logging.info(
                    f"OTHER QUOTE_ADD: Successfully updated quote cache with {len(self.quote_cache)} quotes"
                )
            except Exception as e:
                logging.warning(
                    f"OTHER QUOTE_ADD WARNING: Failed to update quote cache: {e}"
                )
                # Continue without cache update

            # Create enhanced response embed
            embed = discord.Embed(
                title="✅ Quote Added Successfully",
                description=f"**Quote #{quote_index}**",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            # Truncate quote for display if too long
            display_quote = quote if len(quote) <= 200 else quote[:200] + "..."
            embed.add_field(
                name="📝 Quote Content", value=f"```{display_quote}```", inline=False
            )

            embed.add_field(
                name="👤 Added By",
                value=f"{interaction.user.mention}\n**ID:** {interaction.user.id}",
                inline=True,
            )

            embed.add_field(
                name="📊 Quote Stats",
                value=f"**Index:** {quote_index}\n**Length:** {len(quote)} characters",
                inline=True,
            )

            embed.set_footer(text="Use /quote get to retrieve quotes")

            logging.info(
                f"OTHER QUOTE_ADD: Successfully added quote #{quote_index} by user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Quote Add Failed**\nUnexpected error: {str(e)}"
            logging.error(
                f"OTHER QUOTE_ADD ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @quote.command(name="find", description="Searches for a quote")
    @handle_interaction_errors
    async def quote_find(self, interaction: discord.Interaction, search: str) -> None:
        """Search for quotes containing specific words.

        This command searches the quotes database for quotes containing the specified
        search terms. It uses PostgreSQL's full-text search capabilities for efficient
        searching. Includes comprehensive error handling and enhanced result formatting.

        Args:
            interaction: The Discord interaction object
            search: The search terms to look for in quotes

        Raises:
            ValidationError: If search terms are invalid or too long
            DatabaseError: If database search operations fail
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Input validation
            if not search or len(search.strip()) == 0:
                raise ValidationError(message="❌ Search terms cannot be empty")

            search = search.strip()

            # Search length validation
            if len(search) > 100:
                raise ValidationError(
                    message="❌ Search terms too long (maximum 100 characters)"
                )

            # Content validation - prevent abuse
            if len(search) < 2:
                raise ValidationError(
                    message="❌ Search terms too short (minimum 2 characters)"
                )

            logging.info(
                f"OTHER QUOTE_FIND: Quote search request by user {interaction.user.id} for terms: '{search}'"
            )

            # Format search terms for PostgreSQL full-text search
            try:
                formatted_search = search.replace(" ", " & ")
                # Escape special characters that could cause SQL issues
                import re

                formatted_search = re.sub(r"[^\w\s&|!()]", "", formatted_search)
            except Exception as e:
                logging.error(f"OTHER QUOTE_FIND ERROR: Search formatting failed: {e}")
                raise ValidationError(message="❌ Invalid search terms format")

            # Execute database search with error handling
            try:
                results = await self.bot.db.fetch(
                    "SELECT quote, x.row_number FROM (SELECT tokens, quote, ROW_NUMBER() OVER () as row_number FROM quotes) x WHERE x.tokens @@ to_tsquery($1);",
                    formatted_search,
                )
            except Exception as e:
                logging.error(
                    f"OTHER QUOTE_FIND ERROR: Database search failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"❌ Failed to search quotes database: {str(e)}"
                )

            # Process and format results
            if not results or len(results) == 0:
                embed = discord.Embed(
                    title="🔍 Quote Search Results",
                    description=f"**Search Terms:** `{search}`",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="📭 No Results Found",
                    value="No quotes found matching your search terms.\n\n**Suggestions:**\n• Try different keywords\n• Use fewer search terms\n• Check spelling",
                    inline=False,
                )
                embed.set_footer(text="Use /quote add to add new quotes")

                logging.info(
                    f"OTHER QUOTE_FIND: No results found for search '{search}' by user {interaction.user.id}"
                )
                await interaction.response.send_message(embed=embed)
                return

            # Format results for display
            first_result = results[0]
            result_count = len(results)

            embed = discord.Embed(
                title="🔍 Quote Search Results",
                description=f"**Search Terms:** `{search}`\n**Found:** {result_count} quote{'s' if result_count != 1 else ''}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            # Display first result
            quote_text = first_result["quote"]
            display_quote = (
                quote_text if len(quote_text) <= 300 else quote_text[:300] + "..."
            )

            embed.add_field(
                name=f"📝 Quote #{first_result['row_number']}",
                value=f"```{display_quote}```",
                inline=False,
            )

            # If multiple results, show additional result indices
            if result_count > 1:
                additional_indices = [
                    str(result["row_number"]) for result in results[1:]
                ]

                # Limit display to prevent embed from being too long
                if len(additional_indices) > 20:
                    displayed_indices = additional_indices[:20]
                    indices_text = (
                        ", ".join(displayed_indices)
                        + f" ... and {len(additional_indices) - 20} more"
                    )
                else:
                    indices_text = ", ".join(additional_indices)

                embed.add_field(
                    name="📋 Additional Results",
                    value=f"**Quote indices:** {indices_text}\n\n*Use `/quote get <index>` to view specific quotes*",
                    inline=False,
                )

            embed.set_footer(text=f"Showing result 1 of {result_count}")

            logging.info(
                f"OTHER QUOTE_FIND: Found {result_count} results for search '{search}' by user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Quote Search Failed**\nUnexpected error: {str(e)}"
            logging.error(
                f"OTHER QUOTE_FIND ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @quote.command(name="delete", description="Delete a quote")
    @handle_interaction_errors
    async def quote_delete(self, interaction: discord.Interaction, delete: int) -> None:
        """Delete a quote from the database by its index.

        This command removes a quote from the database based on its row number.
        It also updates the quote cache for autocomplete after deletion.
        Includes comprehensive error handling and security checks.

        Args:
            interaction: The Discord interaction object
            delete: The row number of the quote to delete

        Raises:
            ValidationError: If quote index is invalid
            PermissionError: If user lacks permission to delete the quote
            DatabaseError: If database operations fail
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Input validation
            if delete is None or delete < 1:
                raise ValidationError(
                    message="❌ Quote index must be a positive number"
                )

            if delete > 10000:  # Reasonable upper limit
                raise ValidationError(message="❌ Quote index too high (maximum 10000)")

            logging.info(
                f"OTHER QUOTE_DELETE: Quote delete request by user {interaction.user.id} for index {delete}"
            )

            # First, check if the quote exists and get its details
            try:
                u_quote = await self.bot.db.fetchrow(
                    "SELECT quote, row_number, author_id FROM (SELECT quote, author_id, ROW_NUMBER () OVER () as row_number FROM quotes) x WHERE row_number = $1",
                    delete,
                )
            except Exception as e:
                logging.error(
                    f"OTHER QUOTE_DELETE ERROR: Database lookup failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(message=f"❌ Failed to lookup quote: {str(e)}")

            if not u_quote:
                embed = discord.Embed(
                    title="❌ Quote Not Found",
                    description=f"**Index:** {delete}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="📭 No Quote Found",
                    value=f"No quote exists at index {delete}.\n\n**Suggestions:**\n• Use `/quote get` to see available quotes\n• Check the quote index number",
                    inline=False,
                )
                embed.set_footer(text="Use /quote find to search for quotes")

                logging.info(
                    f"OTHER QUOTE_DELETE: Quote not found at index {delete} for user {interaction.user.id}"
                )
                await interaction.response.send_message(embed=embed)
                return

            # Permission check - only allow deletion by quote author or admins
            quote_author_id = u_quote.get("author_id")
            is_quote_author = quote_author_id == interaction.user.id
            is_admin = False

            # Check if user has admin permissions
            if interaction.guild:
                try:
                    is_admin = (
                        interaction.user.guild_permissions.administrator
                        or interaction.user.guild_permissions.manage_messages
                    )
                except Exception as e:
                    logging.warning(
                        f"OTHER QUOTE_DELETE WARNING: Could not check permissions for user {interaction.user.id}: {e}"
                    )

            if not is_quote_author and not is_admin:
                embed = discord.Embed(
                    title="❌ Permission Denied",
                    description=f"**Quote #{delete}**",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="🔒 Access Restricted",
                    value="You can only delete quotes that you added, or you need administrator/manage messages permissions.",
                    inline=False,
                )
                embed.set_footer(text="Contact a moderator if you need help")

                logging.warning(
                    f"OTHER QUOTE_DELETE SECURITY: Permission denied for user {interaction.user.id} to delete quote {delete} (author: {quote_author_id})"
                )
                raise PermissionError(
                    message="❌ You don't have permission to delete this quote"
                )

            # Store quote details for confirmation message
            quote_text = u_quote["quote"]
            quote_row = u_quote["row_number"]

            # Delete the quote from database
            try:
                await self.bot.db.execute(
                    "DELETE FROM quotes WHERE serial_id in (SELECT serial_id FROM quotes ORDER BY time LIMIT 1 OFFSET $1)",
                    delete - 1,
                )
                logging.info(
                    f"OTHER QUOTE_DELETE: Successfully deleted quote #{delete} by user {interaction.user.id}"
                )
            except Exception as e:
                logging.error(
                    f"OTHER QUOTE_DELETE ERROR: Database deletion failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"❌ Failed to delete quote from database: {str(e)}"
                )

            # Update quote cache
            try:
                self.quote_cache = await self.bot.db.fetch(
                    "SELECT quote, row_number FROM (SELECT quote, ROW_NUMBER () OVER () FROM quotes) x"
                )
                logging.info(
                    f"OTHER QUOTE_DELETE: Successfully updated quote cache with {len(self.quote_cache)} quotes"
                )
            except Exception as e:
                logging.warning(
                    f"OTHER QUOTE_DELETE WARNING: Failed to update quote cache: {e}"
                )
                # Continue without cache update

            # Create confirmation embed
            embed = discord.Embed(
                title="✅ Quote Deleted Successfully",
                description=f"**Quote #{quote_row}**",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            # Truncate quote for display if too long
            display_quote = (
                quote_text if len(quote_text) <= 200 else quote_text[:200] + "..."
            )
            embed.add_field(
                name="🗑️ Deleted Quote", value=f"```{display_quote}```", inline=False
            )

            embed.add_field(
                name="👤 Deleted By",
                value=f"{interaction.user.mention}\n**ID:** {interaction.user.id}",
                inline=True,
            )

            embed.add_field(
                name="📊 Action Info",
                value=f"**Original Index:** {quote_row}\n**Permission:** {'Author' if is_quote_author else 'Admin'}",
                inline=True,
            )

            embed.set_footer(text="Quote indices may have shifted after deletion")

            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Quote Delete Failed**\nUnexpected error: {str(e)}"
            logging.error(
                f"OTHER QUOTE_DELETE ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @quote_delete.autocomplete("delete")
    async def quote_delete_autocomplete(
        self, interaction: discord.Interaction, current: int
    ) -> list[app_commands.Choice[int]]:
        """Provide autocomplete suggestions for the quote delete command.

        This method filters the cached quotes based on the user's current input
        and returns matching options for the autocomplete dropdown.

        Args:
            interaction: The interaction that triggered the autocomplete
            current: The current number input by the user

        Returns:
            A list of up to 25 matching quote choices with their row numbers
        """
        ln = []
        for x in self.quote_cache:
            ln.append({"quote": x["quote"], "row_number": x["row_number"]})
        return [
            app_commands.Choice(
                name=f"{quote['row_number']}: {quote['quote']}"[0:100],
                value=quote["row_number"],
            )
            for quote in ln
            if str(current) in str(quote["row_number"]) or current == ""
        ][0:25]

    @quote.command(
        name="get",
        description="Posts a quote a random quote or a quote with the given index",
    )
    @handle_interaction_errors
    async def quote_get(self, interaction: discord.Interaction, index: int = None) -> None:
        """Retrieve and display a quote from the database.

        This command retrieves either a random quote or a specific quote by its
        row number. If no index is provided, a random quote is selected.
        Includes comprehensive error handling and enhanced formatting.

        Args:
            interaction: The Discord interaction object
            index: Optional row number of the quote to retrieve, random if None

        Raises:
            ValidationError: If quote index is invalid
            DatabaseError: If database operations fail
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Input validation for specific index
            if index is not None:
                if index < 1:
                    raise ValidationError(
                        message="❌ Quote index must be a positive number"
                    )

                if index > 10000:  # Reasonable upper limit
                    raise ValidationError(
                        message="❌ Quote index too high (maximum 10000)"
                    )

            is_random = index is None
            logging.info(
                f"OTHER QUOTE_GET: Quote get request by user {interaction.user.id} for {'random quote' if is_random else f'index {index}'}"
            )

            # Execute database query with error handling
            try:
                if is_random:
                    u_quote = await self.bot.db.fetchrow(
                        "SELECT quote, row_number, author, author_id, time FROM (SELECT quote, author, author_id, time, ROW_NUMBER () OVER () as row_number FROM quotes) x ORDER BY random() LIMIT 1"
                    )
                else:
                    u_quote = await self.bot.db.fetchrow(
                        "SELECT quote, row_number, author, author_id, time FROM (SELECT quote, author, author_id, time, ROW_NUMBER () OVER () as row_number FROM quotes) x WHERE row_number = $1",
                        index,
                    )
            except Exception as e:
                logging.error(
                    f"OTHER QUOTE_GET ERROR: Database query failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"❌ Failed to retrieve quote from database: {str(e)}"
                )

            # Handle no quote found
            if not u_quote:
                if is_random:
                    embed = discord.Embed(
                        title="📭 No Quotes Available",
                        description="The quote database appears to be empty.",
                        color=discord.Color.orange(),
                        timestamp=discord.utils.utcnow(),
                    )
                    embed.add_field(
                        name="💡 Suggestion",
                        value="Be the first to add a quote using `/quote add`!",
                        inline=False,
                    )
                    embed.set_footer(text="Help build the quote collection")

                    logging.info(
                        f"OTHER QUOTE_GET: No quotes available for random request by user {interaction.user.id}"
                    )
                else:
                    embed = discord.Embed(
                        title="❌ Quote Not Found",
                        description=f"**Index:** {index}",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow(),
                    )
                    embed.add_field(
                        name="📭 No Quote Found",
                        value=f"No quote exists at index {index}.\n\n**Suggestions:**\n• Try a different index number\n• Use `/quote get` without an index for a random quote\n• Use `/quote find` to search for quotes",
                        inline=False,
                    )
                    embed.set_footer(text="Quote indices start from 1")

                    logging.info(
                        f"OTHER QUOTE_GET: Quote not found at index {index} for user {interaction.user.id}"
                    )

                await interaction.response.send_message(embed=embed)
                return

            # Extract quote details
            quote_text = u_quote["quote"]
            quote_number = u_quote["row_number"]
            quote_author = u_quote.get("author", "Unknown")
            quote_author_id = u_quote.get("author_id")
            quote_time = u_quote.get("time")

            # Create enhanced embed
            embed = discord.Embed(
                title=f"💬 Quote #{quote_number}" + (" (Random)" if is_random else ""),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            # Add quote content
            display_quote = (
                quote_text if len(quote_text) <= 1000 else quote_text[:1000] + "..."
            )
            embed.add_field(
                name="📝 Quote", value=f"```{display_quote}```", inline=False
            )

            # Add author information if available
            if quote_author and quote_author != "Unknown":
                author_info = f"**Added by:** {quote_author}"
                if quote_author_id:
                    author_info += f"\n**ID:** {quote_author_id}"
                if quote_time:
                    try:
                        formatted_time = quote_time.strftime("%Y-%m-%d %H:%M:%S")
                        author_info += f"\n**Added:** {formatted_time}"
                    except Exception:
                        pass

                embed.add_field(name="👤 Author Info", value=author_info, inline=True)

            # Add quote statistics
            stats_info = (
                f"**Index:** {quote_number}\n**Length:** {len(quote_text)} characters"
            )
            if is_random:
                stats_info += "\n**Type:** Random selection"

            embed.add_field(name="📊 Quote Stats", value=stats_info, inline=True)

            # Add helpful footer
            if is_random:
                embed.set_footer(text="Use /quote get <index> for a specific quote")
            else:
                embed.set_footer(text="Use /quote get for a random quote")

            logging.info(
                f"OTHER QUOTE_GET: Successfully retrieved quote #{quote_number} for user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Quote Get Failed**\nUnexpected error: {str(e)}"
            logging.error(
                f"OTHER QUOTE_GET ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @quote_get.autocomplete("index")
    async def quote_get_autocomplete(
        self,
        interaction,
        current: int,
    ) -> list[app_commands.Choice[int]]:
        """Provide autocomplete suggestions for the quote get command.

        This method filters the cached quotes based on the user's current input
        and returns matching options for the autocomplete dropdown.

        Args:
            interaction: The interaction that triggered the autocomplete
            current: The current number input by the user

        Returns:
            A list of up to 25 matching quote choices with their row numbers
        """
        ln = []
        for x in self.quote_cache:
            ln.append({"quote": x["quote"], "row_number": x["row_number"]})
        return [
            app_commands.Choice(
                name=f"{quote['row_number']}: {quote['quote']}"[0:100],
                value=quote["row_number"],
            )
            for quote in ln
            if str(current) in str(quote["row_number"]) or current == ""
        ][0:25]

    @quote.command(name="who", description="Posts who added a quote")
    @handle_interaction_errors
    async def quote_who(self, interaction: discord.Interaction, index: int) -> None:
        """Display information about who added a specific quote.

        This command retrieves metadata about a quote, including the username
        and ID of the user who added it, and when it was added.
        Includes comprehensive error handling and enhanced formatting.

        Args:
            interaction: The Discord interaction object
            index: The row number of the quote to get information about

        Raises:
            ValidationError: If quote index is invalid
            DatabaseError: If database operations fail
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Input validation
            if index is None or index < 1:
                raise ValidationError(
                    message="❌ Quote index must be a positive number"
                )

            if index > 10000:  # Reasonable upper limit
                raise ValidationError(message="❌ Quote index too high (maximum 10000)")

            logging.info(
                f"OTHER QUOTE_WHO: Quote who request by user {interaction.user.id} for index {index}"
            )

            # Execute database query with error handling
            try:
                u_quote = await self.bot.db.fetchrow(
                    "SELECT author, author_id, time, row_number, quote FROM (SELECT author, author_id, time, quote, ROW_NUMBER () OVER () as row_number FROM quotes) x WHERE row_number = $1",
                    index,
                )
            except Exception as e:
                logging.error(
                    f"OTHER QUOTE_WHO ERROR: Database query failed for user {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message=f"❌ Failed to retrieve quote information: {str(e)}"
                )

            # Handle no quote found
            if not u_quote:
                embed = discord.Embed(
                    title="❌ Quote Not Found",
                    description=f"**Index:** {index}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="📭 No Quote Found",
                    value=f"No quote exists at index {index}.\n\n**Suggestions:**\n• Check the quote index number\n• Use `/quote get` to see available quotes\n• Use `/quote find` to search for quotes",
                    inline=False,
                )
                embed.set_footer(text="Quote indices start from 1")

                logging.info(
                    f"OTHER QUOTE_WHO: Quote not found at index {index} for user {interaction.user.id}"
                )
                await interaction.response.send_message(embed=embed)
                return

            # Extract quote details
            quote_author = u_quote.get("author", "Unknown")
            quote_author_id = u_quote.get("author_id")
            quote_time = u_quote.get("time")
            quote_number = u_quote["row_number"]
            quote_text = u_quote.get("quote", "")

            # Create enhanced embed
            embed = discord.Embed(
                title=f"👤 Quote #{quote_number} - Author Information",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            # Add quote preview (truncated)
            if quote_text:
                preview_text = (
                    quote_text if len(quote_text) <= 150 else quote_text[:150] + "..."
                )
                embed.add_field(
                    name="📝 Quote Preview", value=f"```{preview_text}```", inline=False
                )

            # Add author information
            author_info = ""
            if quote_author and quote_author != "Unknown":
                author_info += f"**Username:** {quote_author}\n"
            else:
                author_info += "**Username:** *Unknown*\n"

            if quote_author_id:
                author_info += f"**User ID:** {quote_author_id}\n"
                # Try to get current user info if they're still in the server
                try:
                    if interaction.guild:
                        member = interaction.guild.get_member(quote_author_id)
                        if member:
                            author_info += f"**Current Name:** {member.display_name}\n"
                            author_info += "**Status:** Active member\n"
                        else:
                            author_info += "**Status:** No longer in server\n"
                except Exception:
                    pass
            else:
                author_info += "**User ID:** *Unknown*\n"

            embed.add_field(
                name="👤 Author Details", value=author_info.strip(), inline=True
            )

            # Add timestamp information
            time_info = ""
            if quote_time:
                try:
                    formatted_time = quote_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                    time_info += f"**Added:** {formatted_time}\n"

                    # Calculate how long ago
                    from datetime import datetime

                    now = datetime.now(UTC)
                    if quote_time.tzinfo is None:
                        quote_time = quote_time.replace(tzinfo=UTC)

                    time_diff = now - quote_time
                    days = time_diff.days

                    if days == 0:
                        time_info += "**Age:** Today\n"
                    elif days == 1:
                        time_info += "**Age:** 1 day ago\n"
                    elif days < 30:
                        time_info += f"**Age:** {days} days ago\n"
                    elif days < 365:
                        months = days // 30
                        time_info += (
                            f"**Age:** {months} month{'s' if months != 1 else ''} ago\n"
                        )
                    else:
                        years = days // 365
                        time_info += (
                            f"**Age:** {years} year{'s' if years != 1 else ''} ago\n"
                        )

                except Exception as e:
                    logging.warning(
                        f"OTHER QUOTE_WHO WARNING: Could not format time for quote {index}: {e}"
                    )
                    time_info += f"**Added:** {quote_time}\n"
            else:
                time_info += "**Added:** *Unknown*\n"

            embed.add_field(
                name="📅 Timestamp Info", value=time_info.strip(), inline=True
            )

            # Add quote statistics
            stats_info = f"**Quote Index:** {quote_number}\n"
            if quote_text:
                stats_info += f"**Length:** {len(quote_text)} characters\n"

            embed.add_field(
                name="📊 Quote Stats", value=stats_info.strip(), inline=True
            )

            embed.set_footer(text="Use /quote get to view the full quote")

            logging.info(
                f"OTHER QUOTE_WHO: Successfully retrieved author info for quote #{quote_number} for user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Quote Who Failed**\nUnexpected error: {str(e)}"
            logging.error(
                f"OTHER QUOTE_WHO ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @quote_who.autocomplete("index")
    async def quote_who_autocomplete(
        self,
        interaction,
        current: int,
    ) -> list[app_commands.Choice[int]]:
        """Provide autocomplete suggestions for the quote who command.

        This method filters the cached quotes based on the user's current input
        and returns matching options for the autocomplete dropdown.

        Args:
            interaction: The interaction that triggered the autocomplete
            current: The current number input by the user

        Returns:
            A list of up to 25 matching quote choices with their row numbers
        """
        ln = []
        for x in self.quote_cache:
            ln.append({"quote": x["quote"], "row_number": x["row_number"]})
        return [
            app_commands.Choice(
                name=f"{quote['row_number']}: {quote['quote']}"[0:100],
                value=quote["row_number"],
            )
            for quote in ln
            if str(current) in str(quote["row_number"]) or current == ""
        ][0:25]

    @app_commands.command(
        name="roles",
        description="Posts all the roles in the server you can assign yourself",
    )
    @handle_interaction_errors
    async def role_list(self, interaction: discord.Interaction) -> None:
        """Display a list of all self-assignable roles in the server.

        This command creates an embed containing all roles that users can assign
        to themselves using the /role command. Roles are grouped by category and
        displayed as mentions for easy assignment. Includes comprehensive error handling.

        Args:
            interaction: The Discord interaction object

        Raises:
            ValidationError: If guild context is missing
            DatabaseError: If database operations fail
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Validate guild context
            if not interaction.guild:
                raise ValidationError(
                    message="❌ This command can only be used in a server"
                )

            logging.info(
                f"OTHER ROLE_LIST: Role list request by user {interaction.user.id} in guild {interaction.guild.id}"
            )

            # Get user's current roles for permission checking
            try:
                user_roles = [role.id for role in interaction.user.roles]
            except Exception as e:
                logging.warning(
                    f"OTHER ROLE_LIST WARNING: Could not get user roles for {interaction.user.id}: {e}"
                )
                user_roles = []

            # Query database for self-assignable roles
            try:
                roles = await self.bot.db.fetch(
                    "SELECT id, name, required_roles, weight, category "
                    "FROM roles "
                    "WHERE (required_roles && $2::bigint[] OR required_roles is NULL) "
                    "AND guild_id = $1 "
                    "AND self_assignable = TRUE "
                    "ORDER BY weight, name DESC",
                    interaction.guild.id,
                    user_roles,
                )
            except Exception as e:
                logging.error(
                    f"OTHER ROLE_LIST ERROR: Database query failed for guild {interaction.guild.id}: {e}"
                )
                raise DatabaseError(
                    message=f"❌ Failed to retrieve role list: {str(e)}"
                )

            # Handle no roles found
            if not roles:
                embed = discord.Embed(
                    title="📋 Self-Assignable Roles",
                    description="No self-assignable roles are currently available.",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow(),
                )

                embed.add_field(
                    name="🔧 Setup Required",
                    value="No roles have been configured for self-assignment on this server.\n\n**For Administrators:**\nUse `/admin_role add` to add roles to the self-assignment list.",
                    inline=False,
                )

                embed.add_field(
                    name="💡 What are self-assignable roles?",
                    value="Self-assignable roles allow users to give themselves specific roles without needing administrator intervention. Common examples include:\n• Notification preferences\n• Game roles\n• Interest groups\n• Pronouns",
                    inline=False,
                )

                embed.set_footer(text="Contact a moderator for more information")

                logging.info(
                    f"OTHER ROLE_LIST: No self-assignable roles found for guild {interaction.guild.id}"
                )
                await interaction.response.send_message(embed=embed)
                return

            # Create enhanced embed
            embed = discord.Embed(
                title="🎭 Self-Assignable Roles",
                description=f"**Server:** {interaction.guild.name}\n**Available Roles:** {len(roles)}\n\n*Use `/role <role>` to assign yourself a role*",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            # Set thumbnail with error handling
            try:
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
            except Exception as e:
                logging.warning(
                    f"OTHER ROLE_LIST WARNING: Could not set thumbnail for guild {interaction.guild.id}: {e}"
                )

            # Sort roles by category and weight
            try:
                roles.sort(
                    key=lambda k: (k["category"] or "Uncategorized", k["weight"] or 0)
                )
            except Exception as e:
                logging.warning(f"OTHER ROLE_LIST WARNING: Could not sort roles: {e}")

            # Group roles by category and build embed fields
            try:

                for key, group in groupby(
                    roles, key=lambda k: k["category"] or "Uncategorized"
                ):
                    role_mentions = ""
                    role_count = 0
                    field_number = 1

                    for row in group:
                        try:
                            role = interaction.guild.get_role(row["id"])
                            if role:
                                # Check if user meets requirements

                                temp_str = f"{role.mention}\n"
                                role_count += 1

                                # Check if adding this role would exceed field limit
                                if (
                                    len(temp_str + role_mentions) > 1000
                                ):  # Leave some buffer
                                    # Add current field and start a new one
                                    embed.add_field(
                                        name=f"**{key.title()}**"
                                        + (
                                            f" ({field_number})"
                                            if field_number > 1
                                            else ""
                                        ),
                                        value=role_mentions.strip() or "*No roles*",
                                        inline=False,
                                    )
                                    role_mentions = temp_str
                                    field_number += 1
                                else:
                                    role_mentions += temp_str
                            else:
                                logging.warning(
                                    f"OTHER ROLE_LIST WARNING: Role {row['id']} not found in guild {interaction.guild.id}"
                                )
                        except Exception as e:
                            logging.warning(
                                f"OTHER ROLE_LIST WARNING: Error processing role {row.get('id', 'unknown')}: {e}"
                            )
                            continue

                    # Add the final field for this category
                    if role_mentions.strip():
                        embed.add_field(
                            name=f"**{key.title()}**"
                            + (f" ({field_number})" if field_number > 1 else ""),
                            value=role_mentions.strip(),
                            inline=False,
                        )

                # Add summary information

            except Exception as e:
                logging.error(
                    f"OTHER ROLE_LIST ERROR: Error building role list for guild {interaction.guild.id}: {e}"
                )
                raise ExternalServiceError(
                    message=f"❌ Failed to format role list: {str(e)}"
                )

            embed.set_footer(
                text="Use /role <role> to assign • /role <role> again to remove"
            )

            logging.info(
                f"OTHER ROLE_LIST: Successfully generated role list with {len(roles)} roles for guild {interaction.guild.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Role List Failed**\nUnexpected error: {str(e)}"
            logging.error(
                f"OTHER ROLE_LIST ERROR: Unexpected error for guild {interaction.guild.id if interaction.guild else 'unknown'}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    admin_role = app_commands.Group(
        name="admin_role", description="Admin role commands"
    )

    @admin_role.command(name="weight", description="Changes the weight of a role")
    @app_commands.check(app_admin_or_me_check)
    @handle_interaction_errors
    async def update_role_weight(
        self, interaction: discord.Interaction, role: discord.role.Role, new_weight: int
    ) -> None:
        """Change the weight of a role in the role list.

        This admin-only command updates the weight of a role, which affects its
        position in the role list when displayed with the /roles command.
        Roles with lower weights appear higher in the list within their category.
        Includes comprehensive error handling and validation.

        Args:
            interaction: The Discord interaction object
            role: The role to update
            new_weight: The new weight value to assign to the role

        Raises:
            ValidationError: If parameters are invalid or role doesn't exist in database
            PermissionError: If user lacks required permissions
            DatabaseError: If database operations fail
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Validate guild context
            if not interaction.guild:
                raise ValidationError(
                    message="❌ This command can only be used in a server"
                )

            # Input validation
            if not role:
                raise ValidationError(message="❌ Role is required")

            # Weight validation
            if new_weight < -1000 or new_weight > 1000:
                raise ValidationError(
                    message="❌ Weight must be between -1000 and 1000"
                )

            logging.info(
                f"OTHER UPDATE_ROLE_WEIGHT: Role weight update request by admin {interaction.user.id} for role {role.id} ({role.name}) to weight {new_weight}"
            )

            # Check if role exists in the database
            try:
                existing_role = await self.bot.db.fetchrow(
                    "SELECT id, name, weight, category, self_assignable FROM roles WHERE id = $1 AND guild_id = $2",
                    role.id,
                    interaction.guild.id,
                )
            except Exception as e:
                logging.error(
                    f"OTHER UPDATE_ROLE_WEIGHT ERROR: Database lookup failed for role {role.id}: {e}"
                )
                raise DatabaseError(
                    message=f"❌ Failed to lookup role in database: {str(e)}"
                )

            if not existing_role:
                embed = discord.Embed(
                    title="❌ Role Not Found",
                    description=f"**Role:** {role.mention}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="🔍 Role Not in Database",
                    value=f"The role {role.mention} is not configured in the role system.\n\n**To add it:**\nUse `/admin_role add {role.mention}` first.",
                    inline=False,
                )
                embed.set_footer(
                    text="Only configured roles can have their weight changed"
                )

                logging.info(
                    f"OTHER UPDATE_ROLE_WEIGHT: Role {role.id} not found in database for guild {interaction.guild.id}"
                )
                await interaction.response.send_message(embed=embed)
                return

            # Store old weight for comparison
            old_weight = existing_role.get("weight", 0)

            # Update the role weight in database
            try:
                result = await self.bot.db.execute(
                    "UPDATE roles SET weight = $1 WHERE id = $2 AND guild_id = $3",
                    new_weight,
                    role.id,
                    interaction.guild.id,
                )

                # Check if update was successful
                if result == "UPDATE 0":
                    raise DatabaseError(
                        message="❌ No rows were updated - role may not exist"
                    )

            except Exception as e:
                logging.error(
                    f"OTHER UPDATE_ROLE_WEIGHT ERROR: Database update failed for role {role.id}: {e}"
                )
                raise DatabaseError(
                    message=f"❌ Failed to update role weight: {str(e)}"
                )

            # Create success embed
            embed = discord.Embed(
                title="✅ Role Weight Updated",
                description=f"**Role:** {role.mention}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="⚖️ Weight Change",
                value=f"**Old Weight:** {old_weight}\n**New Weight:** {new_weight}\n**Change:** {new_weight - old_weight:+d}",
                inline=True,
            )

            embed.add_field(
                name="📊 Role Info",
                value=f"**Category:** {existing_role.get('category', 'Uncategorized')}\n**Self-Assignable:** {'Yes' if existing_role.get('self_assignable') else 'No'}",
                inline=True,
            )

            embed.add_field(
                name="👤 Updated By",
                value=f"{interaction.user.mention}\n**ID:** {interaction.user.id}",
                inline=True,
            )

            embed.add_field(
                name="💡 Weight Info",
                value="Lower weights appear higher in the role list within their category. Negative weights are allowed for priority roles.",
                inline=False,
            )

            embed.set_footer(text="Use /roles to see the updated role list")

            logging.info(
                f"OTHER UPDATE_ROLE_WEIGHT: Successfully updated role {role.id} weight from {old_weight} to {new_weight} by admin {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Role Weight Update Failed**\nUnexpected error: {str(e)}"
            logging.error(
                f"OTHER UPDATE_ROLE_WEIGHT ERROR: Unexpected error for role {role.id if role else 'unknown'}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @admin_role.command(name="add", description="Adds a role to the self assign list")
    @app_commands.check(app_admin_or_me_check)
    @handle_interaction_errors
    async def role_add(
        self,
        interaction: discord.Interaction,
        role: discord.role.Role,
        category: str = "Uncategorized",
        auto_replace: bool = False,
        required_roles: str = None,
    ) -> None:
        """Add a role to the self-assignable roles list.

        This admin-only command makes a role self-assignable by users with the /role command.
        It allows specifying a category for organization, whether the role should automatically
        replace other roles in the same category, and any roles required to access this role.

        Args:
            interaction: The interaction that triggered the command
            role: The role to make self-assignable
            category: The category to place the role in (default: 'Uncategorized')
            auto_replace: Whether this role should replace other roles in the same category
            required_roles: Space-separated list of role mentions or IDs required to access this role

        Raises:
            ValidationError: If role data is invalid or required roles cannot be parsed
            DatabaseError: If database operations fail
            PermissionError: If bot lacks permissions to manage the role
        """
        try:
            # Input validation
            if not role:
                raise ValidationError(
                    message="❌ **Invalid Role**\nRole parameter is required"
                )

            if not interaction.guild:
                raise ValidationError(
                    message="❌ **Server Required**\nThis command can only be used in a server"
                )

            # Validate category name
            if len(category) > 50:
                raise ValidationError(
                    message="❌ **Invalid Category**\nCategory name must be 50 characters or less"
                )

            # Check if bot can manage this role
            if role >= interaction.guild.me.top_role:
                raise PermissionError(
                    message=f"❌ **Permission Error**\nI cannot manage {role.mention} as it's higher than my highest role"
                )

            # Parse required roles if provided
            list_of_roles = None
            if required_roles is not None:
                list_of_roles = []
                required_roles_list = required_roles.split()

                for user_role in required_roles_list:
                    matched_id = re.search(r"\d+", user_role)
                    if matched_id:
                        role_id = int(matched_id.group())
                        temp = discord.utils.get(interaction.guild.roles, id=role_id)
                        if temp:
                            list_of_roles.append(temp.id)
                        else:
                            raise ValidationError(
                                message=f"❌ **Invalid Required Role**\nRole with ID {role_id} not found in this server"
                            )
                    else:
                        raise ValidationError(
                            message=f"❌ **Invalid Role Format**\nCould not parse role: {user_role}"
                        )

            logging.info(
                f"OTHER ROLE_ADD: User {interaction.user.id} adding role {role.id} ({role.name}) to self-assign list with category '{category}'"
            )

            # Check if role already exists in database
            existing_role = await self.bot.db.fetchrow(
                "SELECT self_assignable FROM roles WHERE id = $1 AND guild_id = $2",
                role.id,
                interaction.guild.id,
            )

            if existing_role and existing_role["self_assignable"]:
                raise ValidationError(
                    message=f"❌ **Role Already Self-Assignable**\n{role.mention} is already in the self-assign list"
                )

            # Update database with corrected parameter order
            await self.bot.db.execute(
                "UPDATE roles SET self_assignable = TRUE, required_roles = $1, alias = $2, category = $3, auto_replace = $4 "
                "WHERE id = $2 AND guild_id = $5",
                list_of_roles,
                role.id,
                category.lower(),
                auto_replace,
                interaction.guild.id,
            )

            # Create success embed
            embed = discord.Embed(
                title="✅ Role Added to Self-Assign List",
                description=f"Successfully added {role.mention} to the self-assignable roles",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(name="📂 Category", value=category, inline=True)

            embed.add_field(
                name="🔄 Auto Replace",
                value="Yes" if auto_replace else "No",
                inline=True,
            )

            if list_of_roles:
                required_role_mentions = []
                for role_id in list_of_roles:
                    req_role = interaction.guild.get_role(role_id)
                    if req_role:
                        required_role_mentions.append(req_role.mention)

                embed.add_field(
                    name="🔒 Required Roles",
                    value=(
                        ", ".join(required_role_mentions)
                        if required_role_mentions
                        else "None"
                    ),
                    inline=False,
                )
            else:
                embed.add_field(name="🔒 Required Roles", value="None", inline=False)

            embed.set_footer(text="Users can now assign this role using /role")

            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except discord.Forbidden as e:
            error_msg = f"❌ **Permission Error**\nI don't have permission to manage roles: {str(e)}"
            logging.error(
                f"OTHER ROLE_ADD ERROR: Permission error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise PermissionError(message=error_msg) from e
        except Exception as e:
            error_msg = f"❌ **Role Add Failed**\nUnexpected error while adding role to self-assign list: {str(e)}"
            logging.error(
                f"OTHER ROLE_ADD ERROR: Unexpected error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise DatabaseError(message=error_msg) from e

    @role_add.autocomplete("category")
    async def role_add_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Provide autocomplete suggestions for role categories.

        This method filters the cached role categories based on the user's current input
        and returns matching options for the autocomplete dropdown.

        Args:
            interaction: The interaction that triggered the autocomplete
            current: The current text input by the user

        Returns:
            A list of up to 25 matching category name choices
        """
        return [
            app_commands.Choice(name=category, value=category)
            for category in self.category_cache
            if current.lower() in category.lower() or current == ""
        ][0:25]

    @admin_role.command(
        name="remove", description="removes a role from the self assign list"
    )
    @app_commands.check(app_admin_or_me_check)
    @handle_interaction_errors
    async def role_remove(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """Remove a role from the self-assignable roles list.

        This admin-only command removes a role from the self-assignable roles list,
        preventing users from assigning it to themselves with the /role command.
        It resets all role settings to their defaults.

        Args:
            interaction: The interaction that triggered the command
            role: The role to remove from the self-assignable list

        Raises:
            ValidationError: If role data is invalid or role is not self-assignable
            DatabaseError: If database operations fail
            PermissionError: If user lacks permissions
        """
        try:
            # Input validation
            if not role:
                raise ValidationError(
                    message="❌ **Invalid Role**\nRole parameter is required"
                )

            if not interaction.guild:
                raise ValidationError(
                    message="❌ **Server Required**\nThis command can only be used in a server"
                )

            logging.info(
                f"OTHER ROLE_REMOVE: User {interaction.user.id} removing role {role.id} ({role.name}) from self-assign list"
            )

            # Check if role exists in database and is currently self-assignable
            existing_role = await self.bot.db.fetchrow(
                "SELECT self_assignable, category FROM roles WHERE id = $1 AND guild_id = $2",
                role.id,
                interaction.guild.id,
            )

            if not existing_role:
                raise ValidationError(
                    message=f"❌ **Role Not Found**\n{role.mention} is not tracked in the database"
                )

            if not existing_role["self_assignable"]:
                raise ValidationError(
                    message=f"❌ **Role Not Self-Assignable**\n{role.mention} is not currently in the self-assign list"
                )

            # Remove role from self-assign list with corrected SQL
            await self.bot.db.execute(
                "UPDATE roles SET self_assignable = FALSE, weight = 0, alias = NULL, category = NULL, required_roles = NULL, auto_replace = FALSE "
                "WHERE id = $1 AND guild_id = $2",
                role.id,
                interaction.guild.id,
            )

            # Create success embed
            embed = discord.Embed(
                title="✅ Role Removed from Self-Assign List",
                description=f"Successfully removed {role.mention} from the self-assignable roles",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="🗑️ Removed Role",
                value=f"{role.mention}\n**ID:** {role.id}",
                inline=True,
            )

            if existing_role["category"]:
                embed.add_field(
                    name="📂 Previous Category",
                    value=existing_role["category"],
                    inline=True,
                )

            embed.add_field(
                name="ℹ️ Status",
                value="All role settings have been reset to defaults",
                inline=False,
            )

            embed.set_footer(text="Users can no longer assign this role using /role")

            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Role Remove Failed**\nUnexpected error while removing role from self-assign list: {str(e)}"
            logging.error(
                f"OTHER ROLE_REMOVE ERROR: Unexpected error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise DatabaseError(message=error_msg) from e

    @app_commands.command(
        name="role", description="Adds or removes a role from yourself"
    )
    @handle_interaction_errors
    async def role(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """Add or remove a self-assignable role from yourself.

        This command toggles a self-assignable role on the user who runs it.
        If the user already has the role, it will be removed. If they don't have it,
        it will be added. The command checks if the role is self-assignable and if
        the user has any required roles needed to access it.

        If the role has auto_replace enabled, any other roles in the same category
        will be removed when this role is added.

        Args:
            interaction: The interaction that triggered the command
            role: The role to add or remove

        Raises:
            ValidationError: If role data is invalid or user lacks required roles
            PermissionError: If bot lacks permissions to manage roles
            DatabaseError: If database operations fail
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Input validation
            if not role:
                raise ValidationError(
                    message="❌ **Invalid Role**\nRole parameter is required"
                )

            if not interaction.guild:
                raise ValidationError(
                    message="❌ **Server Required**\nThis command can only be used in a server"
                )

            if not isinstance(interaction.user, discord.Member):
                raise ValidationError(
                    message="❌ **Member Required**\nThis command requires a server member"
                )

            # Check if bot can manage this role
            if role >= interaction.guild.me.top_role:
                raise PermissionError(
                    message=f"❌ **Permission Error**\nI cannot manage {role.mention} as it's higher than my highest role"
                )

            logging.info(
                f"OTHER ROLE: User {interaction.user.id} requesting role toggle for {role.id} ({role.name})"
            )

            # Get role information from database
            s_role = await self.bot.db.fetchrow(
                "SELECT * FROM roles WHERE id = $1 AND guild_id = $2",
                role.id,
                interaction.guild.id,
            )

            if not s_role:
                raise ValidationError(
                    message=f"❌ **Role Not Found**\n{role.mention} is not tracked in the database"
                )

            if not s_role["self_assignable"]:
                raise ValidationError(
                    message=f"❌ **Role Not Self-Assignable**\n{role.mention} is not available for self-assignment"
                )

            # Check required roles
            user_role_ids = [r.id for r in interaction.user.roles]

            if s_role["required_roles"] is not None:
                required_roles = s_role["required_roles"]
                has_required = any(
                    req_role_id in user_role_ids for req_role_id in required_roles
                )

                if not has_required:
                    # Get required role names for better error message
                    required_role_names = []
                    for req_role_id in required_roles:
                        req_role = interaction.guild.get_role(req_role_id)
                        if req_role:
                            required_role_names.append(req_role.mention)

                    required_text = (
                        ", ".join(required_role_names)
                        if required_role_names
                        else "specified roles"
                    )
                    raise ValidationError(
                        message=f"❌ **Missing Required Roles**\nYou need one of these roles to access {role.mention}: {required_text}"
                    )

            # Determine action (add or remove)
            action = "remove" if role in interaction.user.roles else "add"

            if action == "remove":
                # Remove the role
                await interaction.user.remove_roles(
                    role, reason=f"Self-role removal by {interaction.user}"
                )

                embed = discord.Embed(
                    title="🗑️ Role Removed",
                    description=f"Successfully removed {role.mention} from your roles",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )

                logging.info(
                    f"OTHER ROLE: Successfully removed role {role.id} from user {interaction.user.id}"
                )

            else:
                # Handle auto-replace if enabled
                if s_role["auto_replace"] and s_role["category"]:
                    # Get roles in the same category that the user has
                    category_roles = await self.bot.db.fetch(
                        "SELECT id FROM roles WHERE id = ANY($1::bigint[]) AND category = $2 AND guild_id = $3",
                        user_role_ids,
                        s_role["category"],
                        interaction.guild.id,
                    )

                    # Remove roles in the same category
                    removed_roles = []
                    for category_role_data in category_roles:
                        category_role = interaction.guild.get_role(
                            category_role_data["id"]
                        )
                        if category_role and category_role in interaction.user.roles:
                            await interaction.user.remove_roles(
                                category_role, reason=f"Auto-replace for {role.name}"
                            )
                            removed_roles.append(category_role.mention)

                # Add the new role
                await interaction.user.add_roles(
                    role, reason=f"Self-role assignment by {interaction.user}"
                )

                embed = discord.Embed(
                    title="✅ Role Added",
                    description=f"Successfully added {role.mention} to your roles",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow(),
                )

                # Show auto-replaced roles if any
                if (
                    s_role["auto_replace"]
                    and "removed_roles" in locals()
                    and removed_roles
                ):
                    embed.add_field(
                        name="🔄 Auto-Replaced Roles",
                        value=", ".join(removed_roles),
                        inline=False,
                    )

                logging.info(
                    f"OTHER ROLE: Successfully added role {role.id} to user {interaction.user.id}"
                )

            # Add role information to embed
            embed.add_field(
                name="🎭 Role", value=f"{role.mention}\n**ID:** {role.id}", inline=True
            )

            if s_role["category"]:
                embed.add_field(
                    name="📂 Category", value=s_role["category"], inline=True
                )

            embed.set_footer(text=f"Action: {action.title()}")
            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except discord.Forbidden as e:
            error_msg = f"❌ **Permission Error**\nI don't have permission to manage roles: {str(e)}"
            logging.error(
                f"OTHER ROLE ERROR: Permission error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise PermissionError(message=error_msg) from e
        except discord.HTTPException as e:
            error_msg = f"❌ **Discord API Error**\nFailed to modify roles: {str(e)}"
            logging.error(
                f"OTHER ROLE ERROR: Discord API error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e
        except Exception as e:
            error_msg = f"❌ **Role Toggle Failed**\nUnexpected error while toggling role: {str(e)}"
            logging.error(
                f"OTHER ROLE ERROR: Unexpected error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @app_commands.command(name="roll", description="Rolls a dice")
    @handle_interaction_errors
    async def roll(
        self,
        interaction: discord.Interaction,
        dice: int = 20,
        amount: int = 1,
        modifier: int = 0,
    ) -> None:
        """Roll dice and display the results.

        This command simulates rolling dice with a specified number of sides,
        amount of dice, and an optional modifier added to the total.
        By default, it rolls a single 20-sided die (d20) with no modifier.

        Args:
            interaction: The interaction that triggered the command
            dice: The number of sides on each die (default: 20, min: 2, max: 1000)
            amount: The number of dice to roll (default: 1, min: 1, max: 100)
            modifier: A number to add to the total roll (default: 0, range: -1000 to 1000)

        Raises:
            ValidationError: If dice parameters are invalid or out of range
            ExternalServiceError: If random number generation fails
        """
        try:
            # Input validation
            if dice < 2:
                raise ValidationError(
                    message="❌ **Invalid Dice**\nDice must have at least 2 sides"
                )

            if dice > 1000:
                raise ValidationError(
                    message="❌ **Invalid Dice**\nDice cannot have more than 1000 sides"
                )

            if amount < 1:
                raise ValidationError(
                    message="❌ **Invalid Amount**\nYou must roll at least 1 die"
                )

            if amount > 100:
                raise ValidationError(
                    message="❌ **Too Many Dice**\nI can't roll more than 100 dice at once"
                )

            if modifier < -1000 or modifier > 1000:
                raise ValidationError(
                    message="❌ **Invalid Modifier**\nModifier must be between -1000 and 1000"
                )

            logging.info(
                f"OTHER ROLL: User {interaction.user.id} rolling {amount}d{dice}+{modifier}"
            )

            # Generate rolls with error handling
            try:
                rolls = []
                for _ in range(amount):
                    roll_result = random.randint(1, dice)
                    rolls.append(roll_result)
            except Exception as e:
                logging.error(
                    f"OTHER ROLL ERROR: Random generation failed for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="❌ **Roll Failed**\nFailed to generate random numbers"
                ) from e

            # Calculate results
            total_before_modifier = sum(rolls)
            final_total = total_before_modifier + modifier

            # Create enhanced embed response
            embed = discord.Embed(
                title="🎲 Dice Roll Results",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            # Format dice notation
            dice_notation = f"{amount}d{dice}"
            if modifier != 0:
                modifier_sign = "+" if modifier >= 0 else ""
                dice_notation += f" {modifier_sign}{modifier}"

            embed.add_field(name="🎯 Roll", value=f"**{dice_notation}**", inline=True)

            embed.add_field(name="🎲 Total", value=f"**{final_total}**", inline=True)

            # Add breakdown for multiple dice or with modifier
            if amount > 1 or modifier != 0:
                breakdown_parts = []

                if amount > 1:
                    # Show individual rolls (truncate if too many)
                    if len(rolls) <= 20:
                        rolls_str = ", ".join(map(str, rolls))
                    else:
                        rolls_str = (
                            ", ".join(map(str, rolls[:20]))
                            + f"... (+{len(rolls)-20} more)"
                        )
                    breakdown_parts.append(f"Rolls: [{rolls_str}]")
                    breakdown_parts.append(f"Sum: {total_before_modifier}")

                if modifier != 0:
                    modifier_sign = "+" if modifier >= 0 else ""
                    breakdown_parts.append(f"Modifier: {modifier_sign}{modifier}")

                embed.add_field(
                    name="📊 Breakdown", value="\n".join(breakdown_parts), inline=False
                )

            # Add statistics for multiple dice
            if amount > 1:
                min_roll = min(rolls)
                max_roll = max(rolls)
                avg_roll = round(total_before_modifier / amount, 2)

                embed.add_field(
                    name="📈 Statistics",
                    value=f"**Min:** {min_roll} | **Max:** {max_roll} | **Avg:** {avg_roll}",
                    inline=False,
                )

            # Add fun flavor text based on results
            if amount == 1:
                if rolls[0] == 1:
                    embed.set_footer(text="💀 Critical failure!")
                elif rolls[0] == dice:
                    embed.set_footer(text="⭐ Critical success!")
                else:
                    embed.set_footer(text="🎲 Good luck!")
            else:
                # Check for all max or all min rolls
                if all(roll == dice for roll in rolls):
                    embed.set_footer(text="🌟 All maximum rolls! Incredible luck!")
                elif all(roll == 1 for roll in rolls):
                    embed.set_footer(text="💀 All minimum rolls! What are the odds?")
                else:
                    embed.set_footer(text=f"🎲 Rolled {amount} dice")

            logging.info(
                f"OTHER ROLL: Successfully rolled {dice_notation} = {final_total} for user {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = (
                f"❌ **Roll Failed**\nUnexpected error while rolling dice: {str(e)}"
            )
            logging.error(
                f"OTHER ROLL ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @app_commands.command(name="ao3", description="Posts information about a ao3 work")
    @handle_interaction_errors
    async def ao3(self, interaction: discord.Interaction, ao3_url: str) -> None:
        """Display detailed information about an Archive of Our Own (AO3) work.

        This command retrieves and displays comprehensive information about a fanfiction
        work from AO3, including the title, author, summary, ratings, tags, statistics,
        and other metadata. It requires a valid AO3 URL to function.

        Args:
            interaction: The interaction that triggered the command
            ao3_url: The URL of the AO3 work to retrieve information about

        Raises:
            ValidationError: If URL format is invalid or work cannot be found
            ExternalServiceError: If AO3 API or authentication fails
        """
        try:
            # Input validation
            if not ao3_url or not ao3_url.strip():
                raise ValidationError(
                    message="❌ **Invalid URL**\nPlease provide a valid AO3 work URL"
                )

            # Validate URL format
            url_pattern = r"https?://archiveofourown\.org/works/\d+"
            if not re.search(url_pattern, ao3_url):
                raise ValidationError(
                    message="❌ **Invalid AO3 URL**\nPlease provide a valid AO3 work URL (e.g., https://archiveofourown.org/works/12345)"
                )

            # Check if AO3 login was successful
            if not self.ao3_login_successful:
                raise ExternalServiceError(
                    message="❌ **AO3 Service Unavailable**\nAO3 authentication failed. Please try again later."
                )

            logging.info(
                f"OTHER AO3: User {interaction.user.id} requesting AO3 work info for URL: {ao3_url}"
            )

            # Defer response for potentially long operation
            await interaction.response.defer()

            try:
                # Refresh authentication token
                self.ao3_session.refresh_auth_token()
            except Exception as e:
                logging.error(
                    f"OTHER AO3 ERROR: Failed to refresh auth token for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="❌ **Authentication Error**\nFailed to authenticate with AO3"
                ) from e

            try:
                # Extract work ID and create work object
                ao3_id = AO3.utils.workid_from_url(ao3_url)
                work = AO3.Work(ao3_id)
                work.set_session(self.ao3_session)
            except AO3.utils.InvalidIdError:
                raise ValidationError(
                    message="❌ **Work Not Found**\nI could not find that work on AO3. Please check the URL and try again."
                )
            except Exception as e:
                logging.error(
                    f"OTHER AO3 ERROR: Failed to create work object for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="❌ **AO3 API Error**\nFailed to retrieve work information from AO3"
                ) from e

            try:
                # Create embed with work information
                embed = discord.Embed(
                    title=work.title or "Unknown Title",
                    description=(work.summary or "No summary available")[
                        :4096
                    ],  # Discord embed description limit
                    color=discord.Color(0x3CD63D),
                    url=work.url,
                    timestamp=discord.utils.utcnow(),
                )

                # Add author information
                try:
                    authors = []
                    for author in work.authors or []:
                        try:
                            author_match = re.search(
                                r"https?://archiveofourown\.org/users/(\w+)", author.url
                            )
                            if author_match:
                                author_name = author_match.group(1)
                                authors.append(f"[{author_name}]({author.url})")
                            else:
                                authors.append(str(author))
                        except (AttributeError, TypeError):
                            authors.append("Unknown Author")

                    author_text = "\n".join(authors) if authors else "Unknown Author"
                    embed.add_field(
                        name="👤 Author(s)", value=author_text[:1024], inline=False
                    )
                except Exception as e:
                    logging.warning(
                        f"OTHER AO3 WARNING: Failed to process authors for user {interaction.user.id}: {e}"
                    )
                    embed.add_field(
                        name="👤 Author(s)", value="Unknown Author", inline=False
                    )

                # Add basic information
                try:
                    embed.add_field(
                        name="⭐ Rating", value=work.rating or "Not Rated", inline=True
                    )
                    embed.add_field(
                        name="📂 Category",
                        value=", ".join(work.categories) if work.categories else "None",
                        inline=True,
                    )
                    embed.add_field(
                        name="🌐 Language",
                        value=work.language or "Unknown",
                        inline=True,
                    )
                except Exception as e:
                    logging.warning(
                        f"OTHER AO3 WARNING: Failed to process basic info for user {interaction.user.id}: {e}"
                    )

                # Add fandom information
                try:
                    if work.fandoms:
                        fandoms_text = "\n".join(work.fandoms)[:1024]
                        embed.add_field(
                            name="🎭 Fandoms", value=fandoms_text, inline=False
                        )
                except Exception as e:
                    logging.warning(
                        f"OTHER AO3 WARNING: Failed to process fandoms for user {interaction.user.id}: {e}"
                    )

                # Add relationship and character information
                try:
                    if work.relationships:
                        relationships_text = "\n".join(work.relationships)[:1024]
                        embed.add_field(
                            name="💕 Relationships",
                            value=relationships_text,
                            inline=False,
                        )

                    if work.characters:
                        characters_text = "\n".join(work.characters)[:1024]
                        embed.add_field(
                            name="👥 Characters", value=characters_text, inline=False
                        )
                except Exception as e:
                    logging.warning(
                        f"OTHER AO3 WARNING: Failed to process relationships/characters for user {interaction.user.id}: {e}"
                    )

                # Add warnings
                try:
                    if work.warnings:
                        warnings_text = "\n".join(work.warnings)
                        embed.add_field(
                            name="⚠️ Warnings", value=warnings_text[:1024], inline=False
                        )
                except Exception as e:
                    logging.warning(
                        f"OTHER AO3 WARNING: Failed to process warnings for user {interaction.user.id}: {e}"
                    )

                # Add statistics
                try:
                    stats_text = []
                    if hasattr(work, "words") and work.words:
                        stats_text.append(f"**Words:** {int(work.words):,}")
                    if hasattr(work, "nchapters") and work.nchapters:
                        expected = (
                            work.expected_chapters if work.expected_chapters else "?"
                        )
                        stats_text.append(f"**Chapters:** {work.nchapters}/{expected}")
                    if hasattr(work, "comments") and work.comments is not None:
                        stats_text.append(f"**Comments:** {work.comments}")
                    if hasattr(work, "kudos") and work.kudos is not None:
                        stats_text.append(f"**Kudos:** {work.kudos}")
                    if hasattr(work, "bookmarks") and work.bookmarks is not None:
                        stats_text.append(f"**Bookmarks:** {work.bookmarks}")
                    if hasattr(work, "hits") and work.hits is not None:
                        stats_text.append(f"**Hits:** {work.hits}")

                    if stats_text:
                        embed.add_field(
                            name="📊 Statistics",
                            value="\n".join(stats_text),
                            inline=False,
                        )
                except Exception as e:
                    logging.warning(
                        f"OTHER AO3 WARNING: Failed to process statistics for user {interaction.user.id}: {e}"
                    )

                # Add dates and status
                try:
                    date_text = []
                    if hasattr(work, "date_published") and work.date_published:
                        date_text.append(
                            f"**Published:** {work.date_published.strftime('%Y-%m-%d')}"
                        )
                    if hasattr(work, "date_updated") and work.date_updated:
                        date_text.append(
                            f"**Updated:** {work.date_updated.strftime('%Y-%m-%d')}"
                        )
                    if hasattr(work, "status") and work.status:
                        date_text.append(f"**Status:** {work.status}")

                    if date_text:
                        embed.add_field(
                            name="📅 Publication Info",
                            value="\n".join(date_text),
                            inline=False,
                        )
                except Exception as e:
                    logging.warning(
                        f"OTHER AO3 WARNING: Failed to process dates for user {interaction.user.id}: {e}"
                    )

                embed.set_footer(text="Data retrieved from Archive of Our Own")

                logging.info(
                    f"OTHER AO3: Successfully retrieved work info for user {interaction.user.id}"
                )
                await interaction.followup.send(embed=embed)

            except AttributeError as e:
                logging.error(
                    f"OTHER AO3 ERROR: Missing work attributes for user {interaction.user.id}: {e}"
                )
                raise ValidationError(
                    message="❌ **Work Data Incomplete**\nThe work exists but some information is missing or inaccessible"
                ) from e

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **AO3 Lookup Failed**\nUnexpected error while retrieving work information: {str(e)}"
            logging.error(
                f"OTHER AO3 ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    # context menu command to pin a message
    @handle_interaction_errors
    async def pin(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """Context menu command to pin a message in allowed channels.

        This command allows users to pin messages in channels that have been
        designated as allowing pins. It checks if the channel is in the pin_cache
        and if the message isn't already pinned before attempting to pin it.

        Args:
            interaction: The interaction that triggered the command
            message: The message to pin

        Raises:
            ValidationError: If message or channel data is invalid
            PermissionError: If bot lacks permissions or channel not allowed
            ExternalServiceError: If Discord API operations fail
        """
        try:
            # Input validation
            if not message:
                raise ValidationError(
                    message="❌ **Invalid Message**\nMessage parameter is required"
                )

            if not message.channel:
                raise ValidationError(
                    message="❌ **Invalid Channel**\nMessage channel could not be determined"
                )

            logging.info(
                f"OTHER PIN: User {interaction.user.id} attempting to pin message {message.id} in channel {message.channel.id}"
            )

            # Check if channel allows pins
            if message.channel.id not in [x["id"] for x in self.pin_cache]:
                raise PermissionError(
                    message="❌ **Pin Not Allowed**\nYou can't pin messages in this channel. An admin needs to enable pins for this channel first."
                )

            # Check if message is already pinned
            if message.pinned:
                raise ValidationError(
                    message="📌 **Already Pinned**\nThat message is already pinned"
                )

            # Attempt to pin the message
            try:
                await message.pin(
                    reason=f"Pinned by {interaction.user} via context menu"
                )

                # Create success embed
                embed = discord.Embed(
                    title="📌 Message Pinned Successfully",
                    description=f"Message has been pinned in {message.channel.mention}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow(),
                )

                # Add message preview (truncated)
                message_preview = (
                    message.content[:100] + "..."
                    if len(message.content) > 100
                    else message.content
                )
                if message_preview:
                    embed.add_field(
                        name="💬 Message Preview",
                        value=f"*{message_preview}*",
                        inline=False,
                    )

                embed.add_field(
                    name="👤 Original Author", value=message.author.mention, inline=True
                )

                embed.add_field(
                    name="🔗 Jump to Message",
                    value=f"[Click here]({message.jump_url})",
                    inline=True,
                )

                embed.set_footer(text=f"Pinned by {interaction.user.display_name}")

                logging.info(
                    f"OTHER PIN: Successfully pinned message {message.id} for user {interaction.user.id}"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            except discord.Forbidden as e:
                error_msg = "❌ **Permission Error**\nI don't have permission to pin messages in this channel"
                logging.error(
                    f"OTHER PIN ERROR: Permission denied for user {interaction.user.id} in channel {message.channel.id}: {e}"
                )
                raise PermissionError(message=error_msg) from e
            except discord.NotFound as e:
                error_msg = "❌ **Message Not Found**\nI could not find that message. It may have been deleted."
                logging.error(
                    f"OTHER PIN ERROR: Message not found for user {interaction.user.id}: {e}"
                )
                raise ValidationError(message=error_msg) from e
            except discord.HTTPException as e:
                # Check if it's a pin limit error
                if "pins" in str(e).lower():
                    error_msg = "❌ **Pin Limit Reached**\nFailed to pin the message. This channel has reached the maximum number of pins (50)."
                else:
                    error_msg = (
                        f"❌ **Discord API Error**\nFailed to pin the message: {str(e)}"
                    )
                logging.error(
                    f"OTHER PIN ERROR: Discord HTTP error for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(message=error_msg) from e

        except (ValidationError, PermissionError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = (
                f"❌ **Pin Failed**\nUnexpected error while pinning message: {str(e)}"
            )
            logging.error(
                f"OTHER PIN ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    # Set which channels the pin command should work in
    @admin.command(
        name="set_pin_channels",
        description="Set which channels the pin command should work in",
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @handle_interaction_errors
    async def set_pin_channels(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        """Toggle whether the pin command can be used in a specific channel.

        This admin-only command toggles whether users can use the pin context menu
        command in a specific channel. If the channel is already in the allowed list,
        it will be removed; otherwise, it will be added.

        Args:
            interaction: The interaction that triggered the command
            channel: The channel to toggle pin permissions for

        Raises:
            ValidationError: If channel data is invalid
            DatabaseError: If database operations fail
            PermissionError: If user lacks permissions
        """
        try:
            # Input validation
            if not channel:
                raise ValidationError(
                    message="❌ **Invalid Channel**\nChannel parameter is required"
                )

            if not interaction.guild:
                raise ValidationError(
                    message="❌ **Server Required**\nThis command can only be used in a server"
                )

            # Ensure channel belongs to the same guild
            if channel.guild.id != interaction.guild.id:
                raise ValidationError(
                    message="❌ **Invalid Channel**\nYou can only configure channels from this server"
                )

            logging.info(
                f"OTHER SET_PIN_CHANNELS: User {interaction.user.id} toggling pin permissions for channel {channel.id} ({channel.name})"
            )

            # Check current status
            is_currently_allowed = channel.id in [x["id"] for x in self.pin_cache]
            action = "remove" if is_currently_allowed else "add"

            try:
                if is_currently_allowed:
                    # Remove from allowed channels
                    await self.bot.db.execute(
                        "UPDATE channels SET allow_pins = FALSE WHERE id = $1",
                        channel.id,
                    )

                    # Create success embed for removal
                    embed = discord.Embed(
                        title="🚫 Pin Permissions Removed",
                        description=f"Removed pin permissions from {channel.mention}",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow(),
                    )

                    embed.add_field(
                        name="📝 Action",
                        value="Users can no longer pin messages in this channel",
                        inline=False,
                    )

                else:
                    # Add to allowed channels
                    await self.bot.db.execute(
                        "UPDATE channels SET allow_pins = TRUE WHERE id = $1",
                        channel.id,
                    )

                    # Create success embed for addition
                    embed = discord.Embed(
                        title="✅ Pin Permissions Added",
                        description=f"Added pin permissions to {channel.mention}",
                        color=discord.Color.green(),
                        timestamp=discord.utils.utcnow(),
                    )

                    embed.add_field(
                        name="📝 Action",
                        value="Users can now pin messages in this channel using the context menu",
                        inline=False,
                    )

                # Update cache
                try:
                    self.pin_cache = await self.bot.db.fetch(
                        "SELECT id FROM channels WHERE allow_pins = TRUE"
                    )
                except Exception as e:
                    logging.warning(
                        f"OTHER SET_PIN_CHANNELS WARNING: Failed to update pin cache for user {interaction.user.id}: {e}"
                    )
                    # Continue anyway, cache will be updated on next cog load

                # Add channel information to embed
                embed.add_field(
                    name="📍 Channel",
                    value=f"{channel.mention}\n**ID:** {channel.id}",
                    inline=True,
                )

                embed.add_field(
                    name="👤 Modified By", value=interaction.user.mention, inline=True
                )

                # Add current status
                total_allowed = len(self.pin_cache)
                embed.add_field(
                    name="📊 Total Allowed Channels",
                    value=f"{total_allowed} channel{'s' if total_allowed != 1 else ''}",
                    inline=True,
                )

                embed.set_footer(text="Pin permissions updated successfully")

                logging.info(
                    f"OTHER SET_PIN_CHANNELS: Successfully {action}ed pin permissions for channel {channel.id} by user {interaction.user.id}"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as db_error:
                error_msg = f"❌ **Database Error**\nFailed to update pin permissions: {str(db_error)}"
                logging.error(
                    f"OTHER SET_PIN_CHANNELS ERROR: Database error for user {interaction.user.id}: {db_error}"
                )
                raise DatabaseError(message=error_msg) from db_error

        except (ValidationError, PermissionError, DatabaseError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Pin Configuration Failed**\nUnexpected error while configuring pin permissions: {str(e)}"
            logging.error(
                f"OTHER SET_PIN_CHANNELS ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise DatabaseError(message=error_msg) from e

    @app_commands.command(name="pat", description="Give Cognita a pat for a job well done!")
    async def pat(self, interaction: discord.Interaction) -> None:
        """Pat the bot to show appreciation.

        Args:
            interaction: The Discord interaction object
        """
        responses = [
            "...Your gesture is acknowledged.",
            "*The stone is cool to the touch, but not unwelcoming.*",
            "I have endured the spells of Archmages. A pat is... acceptable.",
            "You are either very brave or very foolish. I appreciate both qualities.",
            "*Her emerald eyes blink once.* Thank you.",
            "I have stood for centuries. This is the first pat in quite some time.",
            "Zelkyr never patted me. I am uncertain how to process this.",
            "*Her expression remains impassive, but something shifts in those emerald eyes.*",
            "Your appreciation is noted and... welcome.",
            "I could crush you with a single hand. Instead, I shall accept this gesture.",
            "*The faintest hint of warmth emanates from the Truestone.* ...Acknowledged.",
            "You would pat a being who has slain Archmages? Bold.",
            "I am made of stone. And yet... that was not unpleasant.",
        ]
        response = random.choice(responses)
        logging.info(f"OTHER PAT: User {interaction.user.id} patted the bot")
        await interaction.response.send_message(response)


async def setup(bot: commands.Bot) -> None:
    """Set up the OtherCogs cog.

    This function is called automatically by the bot when loading the extension.

    Args:
        bot: The bot instance to attach the cog to
    """
    await bot.add_cog(OtherCogs(bot))

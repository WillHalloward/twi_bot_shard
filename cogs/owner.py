import asyncio
import logging
import re
import shlex
import subprocess
from typing import Literal

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

# Import FAISS schema query functions
from scripts.schema.query_faiss_schema import (
    INDEX_FILE,
    LOOKUP_FILE,
    TOP_K,
    build_prompt,
    extract_sql_from_response,
    generate_sql,
    query_faiss,
)
from utils.command_groups import admin
from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    DatabaseError,
    ExternalServiceError,
    PermissionError,
    QueryError,
    ValidationError,
)

cogs = [
    "cogs.summarization",
    "cogs.gallery",
    "cogs.links_tags",
    "cogs.patreon_poll",
    "cogs.twi",
    "cogs.owner",
    "cogs.other",
    "cogs.mods",
    "cogs.stats",
    "cogs.creator_links",
    "cogs.report",
    "cogs.innktober",
]


class OwnerCog(commands.Cog, name="Owner"):

    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Bind commands in the admin group to this cog instance.

        Commands added to external groups via @admin.command() don't get
        automatically bound to the cog instance. This causes TypeError when
        invoked because the callback expects 'self' but receives none.
        """
        # Get all command names defined in this cog that use the admin group
        cog_method_names = {
            "load_cog",
            "unload_cog",
            "reload_cog",
            "cmd",
            "sync",
            "exit",
            "resources",
            "sql_query",
            "ask_database",
        }

        for cmd in admin.commands:
            # Check if this command's callback belongs to this cog
            if cmd.callback.__name__ in cog_method_names:
                cmd.binding = self

    @admin.command(name="load", description="Load a Discord bot extension/cog")
    @commands.is_owner()
    @handle_interaction_errors
    async def load_cog(self, interaction: discord.Interaction, *, cog: str) -> None:
        """Load a Discord bot extension/cog.

        This command loads a specified cog into the bot, enabling its functionality.

        Args:
            interaction: The Discord interaction object
            cog: The name of the cog to load (e.g., 'cogs.stats')

        Raises:
            ValidationError: If the cog name is invalid
            ExternalServiceError: If the cog loading fails
        """
        await interaction.response.defer()

        # Validate input
        if not cog or len(cog.strip()) == 0:
            raise ValidationError(message="Cog name cannot be empty")

        cog = cog.strip()

        # Validate cog name format
        if not re.match(r"^[a-zA-Z0-9_.]+$", cog):
            raise ValidationError(message="Cog name contains invalid characters")

        # Check if cog is already loaded
        if cog in self.bot.extensions:
            await interaction.followup.send(
                f"⚠️ **Cog already loaded**\n**Cog:** `{cog}`\n**Status:** Already active"
            )
            logging.info(
                f"OWNER COG: Attempted to load already loaded cog '{cog}' by user {interaction.user.id}"
            )
            return

        logging.info(
            f"OWNER COG: User {interaction.user.id} attempting to load cog: {cog}"
        )

        try:
            await self.bot.load_extension(cog)

            # Success response with details
            success_msg = (
                f"✅ **Cog loaded successfully**\n"
                f"**Cog:** `{cog}`\n"
                f"**Status:** Now active\n"
                f"**Total loaded cogs:** {len(self.bot.extensions)}"
            )

            await interaction.followup.send(success_msg)
            logging.info(
                f"OWNER COG SUCCESS: Cog '{cog}' loaded successfully by user {interaction.user.id}"
            )

            # Auto-delete after 10 seconds for cleaner chat
            await asyncio.sleep(10)
            try:
                await interaction.delete_original_response()
            except discord.NotFound:
                pass  # Message already deleted

        except commands.ExtensionNotFound:
            error_msg = f"❌ **Cog not found**\n**Cog:** `{cog}`\n**Error:** Extension file does not exist"
            logging.error(
                f"OWNER COG ERROR: Cog '{cog}' not found for user {interaction.user.id}"
            )
            raise ExternalServiceError(message=error_msg)

        except commands.ExtensionAlreadyLoaded:
            # This shouldn't happen due to our check above, but handle it anyway
            await interaction.followup.send(
                f"⚠️ **Cog already loaded**\n**Cog:** `{cog}`\n**Status:** Already active"
            )
            logging.warning(
                f"OWNER COG: Race condition - cog '{cog}' was loaded between check and load"
            )

        except commands.NoEntryPointError:
            error_msg = f"❌ **Invalid cog structure**\n**Cog:** `{cog}`\n**Error:** No setup function found"
            logging.error(
                f"OWNER COG ERROR: No entry point for cog '{cog}' for user {interaction.user.id}"
            )
            raise ExternalServiceError(message=error_msg)

        except commands.ExtensionFailed as e:
            error_msg = f"❌ **Cog loading failed**\n**Cog:** `{cog}`\n**Error:** {str(e.original)}"
            logging.error(
                f"OWNER COG ERROR: Extension failed for cog '{cog}' for user {interaction.user.id}: {e.original}"
            )
            raise ExternalServiceError(message=error_msg)

        except Exception as e:
            error_msg = f"❌ **Unexpected error**\n**Cog:** `{cog}`\n**Error:** {type(e).__name__}: {str(e)}"
            logging.error(
                f"OWNER COG ERROR: Unexpected error loading cog '{cog}' for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg)

    @load_cog.autocomplete("cog")
    async def reload_cog_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs
            if current.lower() in cog.lower()
        ]

    @admin.command(name="unload", description="Unload a Discord bot extension/cog")
    @commands.is_owner()
    @handle_interaction_errors
    async def unload_cog(self, interaction: discord.Interaction, *, cog: str) -> None:
        """Unload a Discord bot extension/cog.

        This command unloads a specified cog from the bot, disabling its functionality.

        Args:
            interaction: The Discord interaction object
            cog: The name of the cog to unload (e.g., 'cogs.stats')

        Raises:
            ValidationError: If the cog name is invalid
            ExternalServiceError: If the cog unloading fails
        """
        await interaction.response.defer()

        # Validate input
        if not cog or len(cog.strip()) == 0:
            raise ValidationError(message="Cog name cannot be empty")

        cog = cog.strip()

        # Validate cog name format
        if not re.match(r"^[a-zA-Z0-9_.]+$", cog):
            raise ValidationError(message="Cog name contains invalid characters")

        # Check if cog is loaded
        if cog not in self.bot.extensions:
            await interaction.followup.send(
                f"⚠️ **Cog not loaded**\n**Cog:** `{cog}`\n**Status:** Not currently active"
            )
            logging.info(
                f"OWNER COG: Attempted to unload non-loaded cog '{cog}' by user {interaction.user.id}"
            )
            return

        # Prevent unloading the owner cog (this cog)
        if cog == "cogs.owner":
            raise ValidationError(
                message="Cannot unload the owner cog (would disable owner commands)"
            )

        logging.info(
            f"OWNER COG: User {interaction.user.id} attempting to unload cog: {cog}"
        )

        try:
            await self.bot.unload_extension(cog)

            # Success response with details
            success_msg = (
                f"✅ **Cog unloaded successfully**\n"
                f"**Cog:** `{cog}`\n"
                f"**Status:** Now inactive\n"
                f"**Total loaded cogs:** {len(self.bot.extensions)}"
            )

            await interaction.followup.send(success_msg)
            logging.info(
                f"OWNER COG SUCCESS: Cog '{cog}' unloaded successfully by user {interaction.user.id}"
            )

            # Auto-delete after 10 seconds for cleaner chat
            await asyncio.sleep(10)
            try:
                await interaction.delete_original_response()
            except discord.NotFound:
                pass  # Message already deleted

        except commands.ExtensionNotLoaded:
            # This shouldn't happen due to our check above, but handle it anyway
            await interaction.followup.send(
                f"⚠️ **Cog not loaded**\n**Cog:** `{cog}`\n**Status:** Not currently active"
            )
            logging.warning(
                f"OWNER COG: Race condition - cog '{cog}' was unloaded between check and unload"
            )

        except commands.ExtensionFailed as e:
            error_msg = f"❌ **Cog unloading failed**\n**Cog:** `{cog}`\n**Error:** {str(e.original)}"
            logging.error(
                f"OWNER COG ERROR: Extension failed during unload for cog '{cog}' for user {interaction.user.id}: {e.original}"
            )
            raise ExternalServiceError(message=error_msg)

        except Exception as e:
            error_msg = f"❌ **Unexpected error**\n**Cog:** `{cog}`\n**Error:** {type(e).__name__}: {str(e)}"
            logging.error(
                f"OWNER COG ERROR: Unexpected error unloading cog '{cog}' for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg)

    @unload_cog.autocomplete("cog")
    async def reload_cog_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs
            if current.lower() in cog.lower()
        ]

    @admin.command(name="reload", description="Reload a Discord bot extension/cog")
    @commands.is_owner()
    @handle_interaction_errors
    async def reload_cog(self, interaction: discord.Interaction, cog: str) -> None:
        """Reload a Discord bot extension/cog.

        This command unloads and then reloads a specified cog, refreshing its code
        and functionality without restarting the bot.

        Args:
            interaction: The Discord interaction object
            cog: The name of the cog to reload (e.g., 'cogs.stats')

        Raises:
            ValidationError: If the cog name is invalid
            ExternalServiceError: If the cog reloading fails
        """
        await interaction.response.defer()

        # Validate input
        if not cog or len(cog.strip()) == 0:
            raise ValidationError(message="Cog name cannot be empty")

        cog = cog.strip()

        # Validate cog name format
        if not re.match(r"^[a-zA-Z0-9_.]+$", cog):
            raise ValidationError(message="Cog name contains invalid characters")

        # Check if cog is loaded
        was_loaded = cog in self.bot.extensions
        if not was_loaded:
            await interaction.followup.send(
                f"⚠️ **Cog not loaded**\n**Cog:** `{cog}`\n**Action:** Use `/load` command to load it first"
            )
            logging.info(
                f"OWNER COG: Attempted to reload non-loaded cog '{cog}' by user {interaction.user.id}"
            )
            return

        logging.info(
            f"OWNER COG: User {interaction.user.id} attempting to reload cog: {cog}"
        )

        # Track the reload process

        try:
            # Step 1: Unload the extension
            try:
                await self.bot.unload_extension(cog)
                logging.info(
                    f"OWNER COG: Successfully unloaded cog '{cog}' during reload"
                )
            except commands.ExtensionNotLoaded:
                # Cog was unloaded between our check and now
                logging.warning(
                    f"OWNER COG: Cog '{cog}' was already unloaded during reload"
                )
            except Exception as e:
                error_msg = f"❌ **Reload failed during unload**\n**Cog:** `{cog}`\n**Error:** {type(e).__name__}: {str(e)}"
                logging.error(
                    f"OWNER COG ERROR: Failed to unload cog '{cog}' during reload for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(message=error_msg)

            # Step 2: Load the extension
            try:
                await self.bot.load_extension(cog)
                logging.info(
                    f"OWNER COG: Successfully loaded cog '{cog}' during reload"
                )
            except commands.ExtensionNotFound:
                error_msg = f"❌ **Reload failed during load**\n**Cog:** `{cog}`\n**Error:** Extension file does not exist"
                logging.error(
                    f"OWNER COG ERROR: Cog '{cog}' not found during reload for user {interaction.user.id}"
                )
                raise ExternalServiceError(message=error_msg)
            except commands.NoEntryPointError:
                error_msg = f"❌ **Reload failed during load**\n**Cog:** `{cog}`\n**Error:** No setup function found"
                logging.error(
                    f"OWNER COG ERROR: No entry point for cog '{cog}' during reload for user {interaction.user.id}"
                )
                raise ExternalServiceError(message=error_msg)
            except commands.ExtensionFailed as e:
                error_msg = f"❌ **Reload failed during load**\n**Cog:** `{cog}`\n**Error:** {str(e.original)}"
                logging.error(
                    f"OWNER COG ERROR: Extension failed for cog '{cog}' during reload for user {interaction.user.id}: {e.original}"
                )
                raise ExternalServiceError(message=error_msg)
            except Exception as e:
                error_msg = f"❌ **Reload failed during load**\n**Cog:** `{cog}`\n**Error:** {type(e).__name__}: {str(e)}"
                logging.error(
                    f"OWNER COG ERROR: Unexpected error loading cog '{cog}' during reload for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(message=error_msg)

            # Success response with details
            success_msg = (
                f"✅ **Cog reloaded successfully**\n"
                f"**Cog:** `{cog}`\n"
                f"**Status:** Refreshed and active\n"
                f"**Total loaded cogs:** {len(self.bot.extensions)}"
            )

            await interaction.followup.send(success_msg)
            logging.info(
                f"OWNER COG SUCCESS: Cog '{cog}' reloaded successfully by user {interaction.user.id}"
            )

            # Auto-delete after 10 seconds for cleaner chat
            await asyncio.sleep(10)
            try:
                await interaction.delete_original_response()
            except discord.NotFound:
                pass  # Message already deleted

        except ExternalServiceError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # Handle any other unexpected errors
            error_msg = f"❌ **Unexpected reload error**\n**Cog:** `{cog}`\n**Error:** {type(e).__name__}: {str(e)}"
            logging.error(
                f"OWNER COG ERROR: Unexpected error during reload of cog '{cog}' for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg)

    @reload_cog.autocomplete("cog")
    async def reload_cog_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cogs
            if current.lower() in cog.lower()
        ]

    @admin.command(name="cmd", description="Execute a shell command on the host system")
    @commands.is_owner()
    @handle_interaction_errors
    async def cmd(self, interaction: discord.Interaction, args: str) -> None:
        """Execute a system command with enhanced security restrictions.

        This command allows the bot owner to execute system commands with strict
        security controls including command whitelisting and comprehensive logging.

        Args:
            interaction: The Discord interaction object
            args: The command and arguments to execute

        Raises:
            ValidationError: If the command is not allowed or arguments are invalid
            PermissionError: If the command execution is denied for security reasons
            ExternalServiceError: If the system command execution fails
        """
        # Whitelist of allowed commands for security
        ALLOWED_COMMANDS = {
            "ls",
            "dir",
            "pwd",
            "whoami",
            "date",
            "uptime",
            "ps",
            "top",
            "df",
            "free",
            "git",
            "python",
            "pip",
            "uv",
            "systemctl",
            "service",
            "docker",
            "docker-compose",
            "cat",
            "head",
            "tail",
            "grep",
            "find",
            "wc",
            "sort",
            "uniq",
            "echo",
        }

        # Blacklist of dangerous commands
        DANGEROUS_COMMANDS = {
            "rm",
            "del",
            "rmdir",
            "rd",
            "format",
            "fdisk",
            "mkfs",
            "dd",
            "shutdown",
            "reboot",
            "halt",
            "poweroff",
            "init",
            "kill",
            "killall",
            "pkill",
            "chmod",
            "chown",
            "su",
            "sudo",
            "passwd",
            "useradd",
            "userdel",
            "groupadd",
            "groupdel",
        }

        # Validate input
        if not args or len(args.strip()) == 0:
            raise ValidationError(message="Command cannot be empty")

        args = args.strip()

        # Validate command length
        if len(args) > 500:
            raise ValidationError(message="Command too long (maximum 500 characters)")

        try:
            # Parse arguments safely using shlex
            args_array = shlex.split(args)
        except ValueError as e:
            raise ValidationError(message=f"Invalid command syntax: {str(e)}")

        if not args_array:
            raise ValidationError(message="No command specified")

        command = args_array[0].lower()

        # Security checks
        if command in DANGEROUS_COMMANDS:
            logging.warning(
                f"SECURITY: Dangerous command '{command}' attempted by owner {interaction.user.id}"
            )
            raise PermissionError(
                message=f"Command '{command}' is not allowed for security reasons"
            )

        if command not in ALLOWED_COMMANDS:
            logging.warning(
                f"SECURITY: Unauthorized command '{command}' attempted by owner {interaction.user.id}"
            )
            raise PermissionError(
                message=f"Command '{command}' is not in the allowed commands list"
            )

        # Additional security checks for arguments
        dangerous_patterns = [
            r"[;&|`$()]",  # Shell metacharacters
            r"\.\./",  # Directory traversal
            r"/etc/",  # System directories
            r"/root/",  # Root directory
            r"--help",  # Help flags that might reveal system info
        ]

        full_command = " ".join(args_array)
        for pattern in dangerous_patterns:
            if re.search(pattern, full_command):
                logging.warning(
                    f"SECURITY: Dangerous pattern '{pattern}' detected in command by owner {interaction.user.id}"
                )
                raise ValidationError(
                    message="Command contains potentially dangerous characters or patterns"
                )

        # Log the command execution attempt
        logging.info(
            f"OWNER COMMAND: User {interaction.user.id} executing: {full_command}"
        )

        try:
            # Execute the command with timeout and security restrictions
            result = subprocess.run(
                args_array,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                check=False,  # Don't raise exception on non-zero exit code
            )

            # Prepare output
            output_parts = []

            if result.stdout:
                stdout_clean = result.stdout.strip()
                if len(stdout_clean) > 1800:  # Leave room for formatting
                    stdout_clean = stdout_clean[:1800] + "\n... (output truncated)"
                output_parts.append(f"**STDOUT:**\n```\n{stdout_clean}\n```")

            if result.stderr:
                stderr_clean = result.stderr.strip()
                if len(stderr_clean) > 1800:
                    stderr_clean = stderr_clean[:1800] + "\n... (output truncated)"
                output_parts.append(f"**STDERR:**\n```\n{stderr_clean}\n```")

            if result.returncode != 0:
                output_parts.append(f"**Exit Code:** {result.returncode}")

            if not output_parts:
                final_output = "✅ Command executed successfully with no output."
            else:
                final_output = "\n\n".join(output_parts)

            # Ensure total message length doesn't exceed Discord limits
            if len(final_output) > 1900:
                final_output = final_output[:1900] + "\n... (message truncated)"

            await interaction.response.send_message(final_output)

            # Log successful execution
            logging.info(
                f"OWNER COMMAND SUCCESS: Command '{full_command}' executed successfully with exit code {result.returncode}"
            )

        except subprocess.TimeoutExpired:
            error_msg = "❌ Command timed out after 30 seconds"
            logging.warning(
                f"OWNER COMMAND TIMEOUT: Command '{full_command}' timed out"
            )
            raise ExternalServiceError(message=error_msg)

        except subprocess.SubprocessError as e:
            error_msg = f"❌ Subprocess error: {str(e)}"
            logging.error(
                f"OWNER COMMAND ERROR: Subprocess error for '{full_command}': {e}"
            )
            raise ExternalServiceError(message=error_msg)

        except OSError as e:
            error_msg = f"❌ System error: {str(e)}"
            logging.error(f"OWNER COMMAND ERROR: OS error for '{full_command}': {e}")
            raise ExternalServiceError(message=error_msg)

        except Exception as e:
            error_msg = "❌ Unexpected error executing command"
            logging.error(
                f"OWNER COMMAND ERROR: Unexpected error for '{full_command}': {e}"
            )
            raise ExternalServiceError(message=error_msg)

    @admin.command(name="sync", description="Sync the bot's command tree")
    @commands.is_owner()
    @handle_interaction_errors
    async def sync(self, interaction: discord.Interaction, all_guilds: bool) -> None:
        """Sync application commands to Discord.

        This command loads any missing extensions and then syncs the command tree
        either globally or to the current guild.

        Args:
            interaction: The Discord interaction object
            all_guilds: Whether to sync globally (True) or locally to current guild (False)

        Raises:
            ExternalServiceError: If Discord API sync operation fails
            ValidationError: If guild context is missing for local sync
        """
        await interaction.response.defer()

        # Validate guild context for local sync
        if not all_guilds and not interaction.guild:
            raise ValidationError(message="❌ Local sync requires a guild context")

        # Load all non-loaded extensions before syncing
        loaded_count = 0
        failed_extensions = []

        try:
            for extension in self.bot.initial_extensions:
                if not self.bot.loaded_extensions.get(extension, False):
                    success = await self.bot.load_extension_if_needed(extension)
                    if success:
                        loaded_count += 1
                        logging.info(
                            f"OWNER SYNC: Successfully loaded extension '{extension}' before sync"
                        )
                    else:
                        failed_extensions.append(extension)
                        logging.warning(
                            f"OWNER SYNC: Failed to load extension '{extension}' before sync"
                        )
        except Exception as e:
            logging.error(f"OWNER SYNC ERROR: Error during extension loading: {e}")
            raise ExternalServiceError(message=f"❌ Error loading extensions: {str(e)}")

        # Prepare status message about extension loading
        status_parts = []
        if loaded_count > 0:
            status_parts.append(f"✅ Loaded {loaded_count} additional extension(s)")
        if failed_extensions:
            status_parts.append(f"⚠️ Failed to load: {', '.join(failed_extensions)}")

        # Perform the sync operation
        sync_message = ""
        try:
            if all_guilds:
                logging.info(
                    f"OWNER SYNC: Starting global command sync by user {interaction.user.id}"
                )
                synced_commands = await self.bot.tree.sync()
                sync_message = f"✅ **Global Sync Successful**\nSynced {len(synced_commands)} command(s) globally"
                logging.info(
                    f"OWNER SYNC: Global sync completed successfully - {len(synced_commands)} commands synced"
                )
            else:
                logging.info(
                    f"OWNER SYNC: Starting local command sync for guild {interaction.guild.id} by user {interaction.user.id}"
                )
                synced_commands = await self.bot.tree.sync(guild=interaction.guild)
                sync_message = f"✅ **Local Sync Successful**\nSynced {len(synced_commands)} command(s) to {interaction.guild.name}"
                logging.info(
                    f"OWNER SYNC: Local sync completed successfully for guild {interaction.guild.id} - {len(synced_commands)} commands synced"
                )

        except discord.HTTPException as e:
            error_msg = (
                f"❌ **Discord API Error**\nStatus: {e.status}\nMessage: {e.text}"
            )
            logging.error(
                f"OWNER SYNC ERROR: Discord HTTP error during {'global' if all_guilds else 'local'} sync: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

        except discord.Forbidden as e:
            error_msg = "❌ **Permission Error**\nBot lacks permission to sync commands"
            logging.error(
                f"OWNER SYNC ERROR: Permission denied during {'global' if all_guilds else 'local'} sync: {e}"
            )
            raise PermissionError(message=error_msg) from e

        except discord.NotFound as e:
            error_msg = "❌ **Guild Not Found**\nThe specified guild could not be found"
            logging.error(f"OWNER SYNC ERROR: Guild not found during local sync: {e}")
            raise ValidationError(message=error_msg) from e

        except Exception as e:
            error_msg = f"❌ **Sync Failed**\nUnexpected error: {str(e)}"
            logging.error(
                f"OWNER SYNC ERROR: Unexpected error during {'global' if all_guilds else 'local'} sync: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

        # Combine sync result with extension loading status
        final_message = sync_message
        if status_parts:
            final_message += f"\n\n**Extension Loading:**\n{chr(10).join(status_parts)}"

        await interaction.followup.send(final_message)

    @admin.command(name="exit", description="Shut down the bot")
    @commands.is_owner()
    @handle_interaction_errors
    async def exit(self, interaction: discord.Interaction) -> None:
        """Gracefully shut down the bot.

        This command logs the shutdown request and closes the bot connection.
        Only available in the specified guild for security.

        Args:
            interaction: The Discord interaction object

        Raises:
            ExternalServiceError: If bot shutdown fails
        """
        try:
            logging.info(
                f"OWNER EXIT: Bot shutdown requested by user {interaction.user.id} ({interaction.user.name}) in guild {interaction.guild.id if interaction.guild else 'DM'}"
            )
            await interaction.response.send_message(
                "🔄 **Shutting down bot...**\nGoodbye! 👋"
            )

            # Give a moment for the message to be sent before closing
            await asyncio.sleep(1)

            logging.info("OWNER EXIT: Bot shutdown initiated successfully")
            await self.bot.close()

        except Exception as e:
            error_msg = f"❌ **Shutdown Failed**\nError: {str(e)}"
            logging.error(f"OWNER EXIT ERROR: Failed to shutdown bot: {e}")
            raise ExternalServiceError(message=error_msg) from e

    @admin.command(name="resources", description="View bot resource usage statistics")
    @commands.is_owner()
    @handle_interaction_errors
    async def resources(
        self,
        interaction: discord.Interaction,
        detail_level: Literal["basic", "detailed", "system"] = "basic",
    ) -> None:
        """Display resource usage statistics.

        This command provides comprehensive resource monitoring including memory,
        CPU, database cache, and HTTP client statistics with configurable detail levels.

        Args:
            interaction: The Discord interaction object
            detail_level: The level of detail to display (basic, detailed, or system)

        Raises:
            ExternalServiceError: If resource monitoring services are unavailable
            DatabaseError: If database cache statistics cannot be retrieved
            ValidationError: If detail_level parameter is invalid
        """
        await interaction.response.defer()

        # Validate detail level (should be handled by Literal type, but extra safety)
        valid_levels = ["basic", "detailed", "system"]
        if detail_level not in valid_levels:
            raise ValidationError(
                message=f"❌ Invalid detail level. Must be one of: {', '.join(valid_levels)}"
            )

        try:
            logging.info(
                f"OWNER RESOURCES: Resource statistics requested by user {interaction.user.id} with detail level '{detail_level}'"
            )

            # Get resource statistics with error handling
            try:
                current_stats = self.bot.resource_monitor.get_resource_stats()
                if not current_stats:
                    raise ExternalServiceError(
                        message="❌ Resource monitor returned empty statistics"
                    )
            except AttributeError:
                raise ExternalServiceError(
                    message="❌ Resource monitor is not available"
                )
            except Exception as e:
                logging.error(
                    f"OWNER RESOURCES ERROR: Failed to get current resource stats: {e}"
                )
                raise ExternalServiceError(
                    message=f"❌ Failed to retrieve current resource statistics: {str(e)}"
                )

            try:
                summary_stats = self.bot.resource_monitor.get_summary_stats()
            except Exception as e:
                logging.warning(
                    f"OWNER RESOURCES WARNING: Failed to get summary stats, using defaults: {e}"
                )
                summary_stats = {}

            # Create embed with basic information
            embed = discord.Embed(
                title="📊 Resource Usage Statistics",
                description=f"Statistics collected over the last {summary_stats.get('history_duration_minutes', 0):.1f} minutes",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            # Add current resource usage
            try:
                embed.add_field(
                    name="🔄 Current Usage",
                    value=(
                        f"**Memory:** {current_stats.get('memory_percent', 0):.1f}%\n"
                        f"**CPU:** {current_stats.get('cpu_percent', 0):.1f}%\n"
                        f"**Threads:** {current_stats.get('thread_count', 0)}\n"
                        f"**Uptime:** {current_stats.get('uptime', 0) / 3600:.1f} hours"
                    ),
                    inline=True,
                )
            except (KeyError, TypeError) as e:
                logging.warning(
                    f"OWNER RESOURCES WARNING: Missing current stats fields: {e}"
                )
                embed.add_field(
                    name="🔄 Current Usage",
                    value="⚠️ Some statistics unavailable",
                    inline=True,
                )

            # Add summary statistics
            if summary_stats:
                try:
                    embed.add_field(
                        name="📈 Summary Statistics",
                        value=(
                            f"**Avg Memory:** {summary_stats.get('avg_memory_percent', 0):.1f}%\n"
                            f"**Max Memory:** {summary_stats.get('max_memory_percent', 0):.1f}%\n"
                            f"**Avg CPU:** {summary_stats.get('avg_cpu_percent', 0):.1f}%\n"
                            f"**Max CPU:** {summary_stats.get('max_cpu_percent', 0):.1f}%"
                        ),
                        inline=True,
                    )
                except (KeyError, TypeError) as e:
                    logging.warning(
                        f"OWNER RESOURCES WARNING: Missing summary stats fields: {e}"
                    )
                    embed.add_field(
                        name="📈 Summary Statistics",
                        value="⚠️ Summary statistics unavailable",
                        inline=True,
                    )

            # Add HTTP client statistics
            try:
                http_stats = self.bot.http_client.get_stats()
                embed.add_field(
                    name="🌐 HTTP Client Statistics",
                    value=(
                        f"**Requests:** {http_stats.get('requests', 0)}\n"
                        f"**Errors:** {http_stats.get('errors', 0)}\n"
                        f"**Timeouts:** {http_stats.get('timeouts', 0)}"
                    ),
                    inline=True,
                )
            except Exception as e:
                logging.warning(
                    f"OWNER RESOURCES WARNING: Failed to get HTTP client stats: {e}"
                )
                embed.add_field(
                    name="🌐 HTTP Client Statistics",
                    value="⚠️ HTTP statistics unavailable",
                    inline=True,
                )

            # Add database cache statistics
            try:
                db_cache_stats = await self.bot.db.get_cache_stats()
                embed.add_field(
                    name="💾 Database Cache Statistics",
                    value=(
                        f"**Hit Rate:** {db_cache_stats.get('hit_rate', 0):.1f}%\n"
                        f"**Hits:** {db_cache_stats.get('hits', 0)}\n"
                        f"**Misses:** {db_cache_stats.get('misses', 0)}\n"
                        f"**Evictions:** {db_cache_stats.get('evictions', 0)}"
                    ),
                    inline=True,
                )
            except Exception as e:
                logging.error(
                    f"OWNER RESOURCES ERROR: Failed to get database cache stats: {e}"
                )
                raise DatabaseError(
                    message=f"❌ Failed to retrieve database cache statistics: {str(e)}"
                )

            # Add detailed information if requested
            if detail_level == "detailed" or detail_level == "system":
                try:
                    embed.add_field(
                        name="🔍 Detailed Memory Usage",
                        value=(
                            f"**RSS:** {current_stats.get('memory_rss', 0) / (1024 * 1024):.1f} MB\n"
                            f"**VMS:** {current_stats.get('memory_vms', 0) / (1024 * 1024):.1f} MB\n"
                            f"**Open Files:** {current_stats.get('open_files_count', 0)}\n"
                            f"**Connections:** {current_stats.get('connection_count', 0)}"
                        ),
                        inline=True,
                    )
                except (KeyError, TypeError) as e:
                    logging.warning(
                        f"OWNER RESOURCES WARNING: Missing detailed stats fields: {e}"
                    )
                    embed.add_field(
                        name="🔍 Detailed Memory Usage",
                        value="⚠️ Detailed statistics unavailable",
                        inline=True,
                    )

            # Add system information if requested
            if detail_level == "system":
                try:
                    system_info = self.bot.resource_monitor.get_system_info()
                    embed.add_field(
                        name="🖥️ System Information",
                        value=(
                            f"**Platform:** {system_info.get('platform', 'Unknown')}\n"
                            f"**Python:** {system_info.get('python_version', 'Unknown')}\n"
                            f"**CPU Count:** {system_info.get('cpu_count', 0)}\n"
                            f"**Total Memory:** {system_info.get('total_memory', 0) / (1024 * 1024 * 1024):.1f} GB\n"
                            f"**System Memory:** {current_stats.get('system_memory_percent', 0):.1f}%\n"
                            f"**System CPU:** {current_stats.get('system_cpu_percent', 0):.1f}%"
                        ),
                        inline=False,
                    )
                except Exception as e:
                    logging.warning(
                        f"OWNER RESOURCES WARNING: Failed to get system info: {e}"
                    )
                    embed.add_field(
                        name="🖥️ System Information",
                        value="⚠️ System information unavailable",
                        inline=False,
                    )

            embed.set_footer(text=f"Detail Level: {detail_level.title()}")
            logging.info(
                f"OWNER RESOURCES: Successfully generated resource statistics with detail level '{detail_level}'"
            )
            await interaction.followup.send(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Resource Statistics Error**\nFailed to generate resource report: {str(e)}"
            logging.error(
                f"OWNER RESOURCES ERROR: Unexpected error generating resource statistics: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @admin.command(name="sql", description="Execute a SQL query on the database")
    @commands.is_owner()
    @handle_interaction_errors
    async def sql_query(
        self,
        interaction: discord.Interaction,
        query: str,
        allow_modifications: bool = False,
    ) -> None:
        """Execute a SQL query with enhanced security restrictions.

        This command allows the bot owner to execute SQL queries with strict
        security controls including query type restrictions and comprehensive logging.

        Args:
            interaction: The Discord interaction object
            query: The SQL query to execute
            allow_modifications: Whether to allow non-SELECT queries (default: False)

        Raises:
            ValidationError: If the query is invalid or not allowed
            PermissionError: If the query type is not permitted
            DatabaseError: If the database operation fails
            QueryError: If there's an issue with the SQL query execution
        """
        await interaction.response.defer()

        # Validate input
        if not query or len(query.strip()) == 0:
            raise ValidationError(message="SQL query cannot be empty")

        query = query.strip()

        # Validate query length
        if len(query) > 5000:
            raise ValidationError(message="Query too long (maximum 5000 characters)")

        # Normalize query for analysis
        query_upper = query.upper().strip()

        # Define allowed and dangerous query types
        READ_ONLY_OPERATIONS = {"SELECT", "WITH", "EXPLAIN", "ANALYZE"}
        MODIFICATION_OPERATIONS = {
            "INSERT",
            "UPDATE",
            "DELETE",
            "TRUNCATE",
            "DROP",
            "CREATE",
            "ALTER",
        }
        DANGEROUS_OPERATIONS = {
            "DROP",
            "TRUNCATE",
            "DELETE FROM",
            "UPDATE",
            "ALTER",
            "CREATE",
        }

        # Determine query type
        first_word = query_upper.split()[0] if query_upper.split() else ""

        # Security checks
        if not allow_modifications:
            if first_word in MODIFICATION_OPERATIONS:
                logging.warning(
                    f"SECURITY: Modification query '{first_word}' attempted by owner {interaction.user.id} without permission"
                )
                raise PermissionError(
                    message=f"Query type '{first_word}' requires allow_modifications=True for safety"
                )

        if first_word in DANGEROUS_OPERATIONS and not allow_modifications:
            logging.warning(
                f"SECURITY: Dangerous query '{first_word}' attempted by owner {interaction.user.id}"
            )
            raise PermissionError(
                message=f"Dangerous query type '{first_word}' is not allowed. Use with extreme caution."
            )

        # Additional security pattern checks
        dangerous_patterns = [
            r";\s*(DROP|DELETE|TRUNCATE|ALTER)",  # Multiple statements with dangerous operations
            r"--\s*[^\r\n]*(?:DROP|DELETE|TRUNCATE)",  # Comments hiding dangerous operations
            r"/\*.*(?:DROP|DELETE|TRUNCATE).*\*/",  # Block comments hiding dangerous operations
            r"UNION.*SELECT.*FROM.*information_schema",  # Information schema access
            r"pg_sleep|pg_terminate_backend",  # PostgreSQL system functions
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, query_upper, re.IGNORECASE | re.DOTALL):
                logging.warning(
                    f"SECURITY: Dangerous SQL pattern detected in query by owner {interaction.user.id}"
                )
                raise ValidationError(
                    message="Query contains potentially dangerous SQL patterns"
                )

        # Log the query execution attempt
        logging.info(
            f"OWNER SQL: User {interaction.user.id} executing query (type: {first_word}): {query[:200]}{'...' if len(query) > 200 else ''}"
        )

        try:
            # Execute the query with appropriate method
            if first_word in READ_ONLY_OPERATIONS or first_word == "SELECT":
                results = await self.bot.db.fetch(query)

                if not results:
                    completion_msg = (
                        "✅ Query executed successfully but returned no results."
                    )
                    await interaction.followup.send(completion_msg)
                    logging.info("OWNER SQL SUCCESS: Query returned no results")
                    return

                # Format results as a table
                if len(results) == 0:
                    completion_msg = (
                        "✅ Query executed successfully but returned no results."
                    )
                    await interaction.followup.send(completion_msg)
                    logging.info("OWNER SQL SUCCESS: Query returned empty result set")
                    return

                # Get column names from the first row
                columns = list(results[0].keys())

                # Calculate column widths
                col_widths = {}
                for col in columns:
                    col_widths[col] = max(
                        len(str(col)), max(len(str(row[col])) for row in results)
                    )
                    # Limit column width to prevent overly wide tables
                    col_widths[col] = min(col_widths[col], 30)

                # Build the table
                table_lines = []

                # Header row
                header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
                table_lines.append(header)

                # Separator row
                separator = "-+-".join("-" * col_widths[col] for col in columns)
                table_lines.append(separator)

                # Data rows (limit to first 50 rows to prevent message being too long)
                display_limit = 50
                for _i, row in enumerate(results[:display_limit]):
                    row_str = " | ".join(
                        str(row[col])[: col_widths[col]].ljust(col_widths[col])
                        for col in columns
                    )
                    table_lines.append(row_str)

                table_text = "\n".join(table_lines)

                # Check if we need to truncate due to Discord's message limit
                if len(table_text) > 1800:  # Leave room for formatting and metadata
                    table_text = table_text[:1800] + "\n... (table truncated)"

                # Add information about total rows
                result_info = f"📊 **Query Results**\n**Rows returned:** {len(results)}"
                if len(results) > display_limit:
                    result_info += f" (showing first {display_limit})"

                result_info += f"\n**Columns:** {len(columns)}"

                response = f"{result_info}\n```\n{table_text}\n```"
                await interaction.followup.send(response)

                logging.info(
                    f"OWNER SQL SUCCESS: SELECT query returned {len(results)} rows"
                )

            else:
                # For modification queries, use execute and return affected rows
                result = await self.bot.db.execute(query)

                # Parse the result to get affected rows
                affected_rows = "Unknown"
                if isinstance(result, str):
                    # Try to extract number from result string like "UPDATE 5" or "INSERT 0 3"
                    match = re.search(r"(\w+)\s+(\d+)", result)
                    if match:
                        operation, count = match.groups()
                        affected_rows = count

                completion_msg = f"✅ **Query executed successfully**\n**Operation:** {first_word}\n**Affected rows:** {affected_rows}\n**Result:** `{result}`"
                await interaction.followup.send(completion_msg)

                logging.info(
                    f"OWNER SQL SUCCESS: {first_word} query executed, result: {result}"
                )

        except asyncpg.PostgresError as e:
            error_msg = f"❌ **PostgreSQL Error**\n**Error Code:** {e.sqlstate if hasattr(e, 'sqlstate') else 'Unknown'}\n**Message:** {str(e)}"
            logging.error(f"OWNER SQL ERROR: PostgreSQL error for query: {e}")
            raise DatabaseError(message=error_msg) from e

        except asyncpg.InterfaceError as e:
            error_msg = f"❌ **Database Interface Error**\n**Message:** {str(e)}"
            logging.error(f"OWNER SQL ERROR: Interface error for query: {e}")
            raise DatabaseError(message=error_msg) from e

        except asyncpg.DataError as e:
            error_msg = f"❌ **Data Error**\n**Message:** {str(e)}"
            logging.error(f"OWNER SQL ERROR: Data error for query: {e}")
            raise QueryError(message=error_msg) from e

        except Exception as e:
            error_msg = f"❌ **Unexpected Error**\n**Type:** {type(e).__name__}\n**Message:** {str(e)}"
            logging.error(f"OWNER SQL ERROR: Unexpected error for query: {e}")
            raise QueryError(message=error_msg) from e

    @admin.command(name="ask_db", description="Ask a natural language question about the database")
    @commands.is_owner()
    @handle_interaction_errors
    async def ask_database(self, interaction: discord.Interaction, question: str) -> None:
        """Ask a natural language question about the database and get SQL results.

        This command uses AI to convert natural language questions into SQL queries,
        executes them against the database, and returns formatted results.

        Args:
            interaction: The Discord interaction object
            question: The natural language question to ask about the database

        Raises:
            ValidationError: If the question is invalid or empty
            ExternalServiceError: If AI service or FAISS index is unavailable
            DatabaseError: If database query execution fails
            QueryError: If the generated SQL query is invalid
        """
        await interaction.response.defer()

        # Validate input
        if not question or len(question.strip()) == 0:
            raise ValidationError(message="❌ Question cannot be empty")

        question = question.strip()

        # Validate question length
        if len(question) > 1000:
            raise ValidationError(
                message="❌ Question too long (maximum 1000 characters)"
            )

        logging.info(
            f"OWNER ASK_DB: Natural language database query requested by user {interaction.user.id}: '{question[:100]}{'...' if len(question) > 100 else ''}'"
        )

        try:
            # Step 1: Search for relevant schema using FAISS
            await interaction.followup.send(
                "🔗 **Step 1/5:** Searching schema for relevant tables..."
            )

            try:
                relevant_schema = query_faiss(question, INDEX_FILE, LOOKUP_FILE, TOP_K)
                if not relevant_schema:
                    raise ExternalServiceError(
                        message="❌ No relevant database schema found for your question"
                    )
                logging.info(
                    f"OWNER ASK_DB: Found {len(relevant_schema)} relevant schema entries"
                )
            except FileNotFoundError as e:
                logging.error(f"OWNER ASK_DB ERROR: FAISS index files not found: {e}")
                raise ExternalServiceError(
                    message="❌ Database schema index not available. Please contact administrator."
                )
            except Exception as e:
                logging.error(f"OWNER ASK_DB ERROR: FAISS query failed: {e}")
                raise ExternalServiceError(message=f"❌ Schema search failed: {str(e)}")

            # Step 2: Build prompt with relevant schema
            await interaction.edit_original_response(
                content="🧠 **Step 2/5:** Building AI prompt with schema context..."
            )

            try:
                # Extract context information from the interaction
                server_id = interaction.guild.id if interaction.guild else None
                channel_id = interaction.channel.id if interaction.channel else None
                user_id = interaction.user.id

                prompt = build_prompt(
                    question, relevant_schema, server_id, channel_id, user_id
                )
                if not prompt:
                    raise ExternalServiceError(message="❌ Failed to build AI prompt")
                logging.info(
                    f"OWNER ASK_DB: Built prompt with {len(prompt)} characters (Server: {server_id}, Channel: {channel_id}, User: {user_id})"
                )
            except Exception as e:
                logging.error(f"OWNER ASK_DB ERROR: Prompt building failed: {e}")
                raise ExternalServiceError(
                    message=f"❌ Prompt generation failed: {str(e)}"
                )

            # Step 3: Generate SQL using OpenAI
            await interaction.edit_original_response(
                content="🤖 **Step 3/5:** Generating SQL with AI..."
            )

            try:
                raw_sql_response = generate_sql(prompt)
                if not raw_sql_response:
                    raise ExternalServiceError(
                        message="❌ AI service returned empty response"
                    )
                logging.info(
                    f"OWNER ASK_DB: Received AI response with {len(raw_sql_response)} characters"
                )
            except Exception as e:
                logging.error(f"OWNER ASK_DB ERROR: AI SQL generation failed: {e}")
                if "rate limit" in str(e).lower():
                    raise ExternalServiceError(
                        message="❌ AI service rate limit exceeded. Please try again later."
                    )
                elif "api key" in str(e).lower():
                    raise ExternalServiceError(
                        message="❌ AI service authentication failed. Please contact administrator."
                    )
                else:
                    raise ExternalServiceError(
                        message=f"❌ AI SQL generation failed: {str(e)}"
                    )

            # Step 4: Extract clean SQL from response
            await interaction.edit_original_response(
                content="🔍 **Step 4/5:** Extracting SQL query..."
            )

            try:
                sql_query = extract_sql_from_response(raw_sql_response)
                if not sql_query:
                    raise QueryError(
                        message="❌ Failed to extract valid SQL from AI response"
                    )
                logging.info(
                    f"OWNER ASK_DB: Extracted SQL query: {sql_query[:200]}{'...' if len(sql_query) > 200 else ''}"
                )
            except Exception as e:
                logging.error(f"OWNER ASK_DB ERROR: SQL extraction failed: {e}")
                raise QueryError(message=f"❌ SQL extraction failed: {str(e)}")

            # Step 4.5: Check for soft error (AI couldn't generate a query)
            if sql_query == "COGNITA_NO_QUERY_POSSIBLE":
                response = f"**Question:** {question}\n\n**Status:** ❌ **Unable to generate SQL query**\n\n**Explanation:** The AI couldn't determine how to create a database query for your question. This might happen if:\n• The question is too vague or ambiguous\n• The requested data isn't available in the database schema\n• The question requires complex logic that can't be expressed in a single SQL query\n\n**Suggestion:** Try rephrasing your question to be more specific about what Discord data you're looking for (e.g., messages, users, servers, reactions, etc.)."
                await interaction.edit_original_response(content=response)
                logging.info(
                    f"OWNER ASK_DB: AI determined query not possible for question: '{question}'"
                )
                return

            # Step 5: Execute the generated SQL
            await interaction.edit_original_response(
                content="⚡ **Step 5/5:** Executing generated SQL..."
            )

            try:
                results = await self.bot.db.fetch(sql_query)
                logging.info(
                    f"OWNER ASK_DB: Query executed successfully, returned {len(results) if results else 0} rows"
                )
            except asyncpg.PostgresError as e:
                error_msg = f"❌ **Database Error**\n**Error Code:** {e.sqlstate if hasattr(e, 'sqlstate') else 'Unknown'}\n**Message:** {str(e)}"
                logging.error(
                    f"OWNER ASK_DB ERROR: PostgreSQL error executing generated query: {e}"
                )
                raise DatabaseError(message=error_msg) from e
            except Exception as e:
                logging.error(
                    f"OWNER ASK_DB ERROR: Database query execution failed: {e}"
                )
                raise DatabaseError(message=f"❌ Query execution failed: {str(e)}")

            if not results:
                response = f"**Question:** {question}\n\n**Generated SQL:**\n```sql\n{sql_query}\n```\n\n**Result:** ✅ Query executed successfully but returned no results."
                await interaction.edit_original_response(content=response)
                return

            # Format results as a table (similar to sql_query command)
            try:
                columns = list(results[0].keys())

                # Calculate column widths
                col_widths = {}
                for col in columns:
                    col_widths[col] = max(
                        len(str(col)), max(len(str(row[col])) for row in results)
                    )
                    # Limit column width to prevent overly wide tables
                    col_widths[col] = min(col_widths[col], 30)

                # Build the table
                table_lines = []

                # Header row
                header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
                table_lines.append(header)

                # Separator row
                separator = "-+-".join("-" * col_widths[col] for col in columns)
                table_lines.append(separator)

                # Data rows (limit to first 20 rows to prevent message being too long)
                for _i, row in enumerate(results[:20]):
                    row_str = " | ".join(
                        str(row[col])[: col_widths[col]].ljust(col_widths[col])
                        for col in columns
                    )
                    table_lines.append(row_str)

                table_text = "\n".join(table_lines)

                # Check if we need to truncate due to Discord's message limit
                if len(table_text) > 1200:  # Leave more room for question and SQL
                    table_text = table_text[:1200] + "\n... (truncated)"

                # Add information about total rows
                result_info = f"Query returned {len(results)} row(s)"
                if len(results) > 20:
                    result_info += " (showing first 20)"

                # Format final response
                response = f"**Question:** {question}\n\n**Generated SQL:**\n```sql\n{sql_query}\n```\n\n**Results:** ✅ {result_info}\n```\n{table_text}\n```"

                # Check total response length and truncate if needed
                if len(response) > 1900:
                    # Truncate the table further if needed
                    truncated_table = (
                        table_text[:800] + "\n... (truncated due to length)"
                    )
                    response = f"**Question:** {question}\n\n**Generated SQL:**\n```sql\n{sql_query}\n```\n\n**Results:** ✅ {result_info}\n```\n{truncated_table}\n```"

                await interaction.edit_original_response(content=response)
                logging.info(
                    f"OWNER ASK_DB: Successfully completed natural language query for user {interaction.user.id}"
                )

            except Exception as e:
                logging.error(f"OWNER ASK_DB ERROR: Result formatting failed: {e}")
                # Still show the SQL and basic result info even if formatting fails
                response = f"**Question:** {question}\n\n**Generated SQL:**\n```sql\n{sql_query}\n```\n\n**Results:** ✅ Query executed successfully ({len(results)} rows) but formatting failed: {str(e)}"
                await interaction.edit_original_response(content=response)

        except (ValidationError, ExternalServiceError, DatabaseError, QueryError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Unexpected Error**\nFailed to process database question: {str(e)}"
            logging.error(
                f"OWNER ASK_DB ERROR: Unexpected error processing question '{question}': {e}"
            )
            raise ExternalServiceError(message=error_msg) from e


async def setup(bot) -> None:
    await bot.add_cog(OwnerCog(bot))

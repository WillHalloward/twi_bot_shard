"""Main entry point for the Twi Bot Shard application.

This module initializes the Discord bot, sets up logging, establishes database connections,
and manages the bot's lifecycle. It serves as the central orchestrator for all bot functionality.

The module defines the Cognita bot class, which extends discord.ext.commands.Bot with
additional functionality specific to this application, such as database access, service
container management, and repository access.
"""

import asyncio
import datetime
import json
import logging
import logging.handlers
import ssl
import sys
import time
import traceback
from collections.abc import Sequence
from itertools import cycle

import asyncpg
import discord
from discord.ext import commands

import config
from utils.command_groups import admin, mod, gallery_admin
from utils.error_handling import setup_global_exception_handler
from utils.http_client import HTTPClient
from utils.permissions import setup_permissions
from utils.resource_monitor import ResourceMonitor
from utils.secret_manager import setup_secret_manager

# Define type aliases for complex types
type DiscordID = int
type CommandName = str
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.creator_links import CreatorLink
from models.tables.gallery import GalleryMementos
from utils.db import Database
from utils.repositories import register_repositories
from utils.repository_factory import RepositoryFactory
from utils.service_container import ServiceContainer
from utils.sqlalchemy_db import async_session_maker

status = cycle(
    [
        "Killing the mages of Wistram",
        "Cleaning up a mess",
        "Hiding corpses",
        "Mending Pirateaba's broken hands",
        "Hoarding knowledge",
        "Dusting off priceless artifacts",
        "Praying for Mating Rituals 4",
        "Plotting demise of nosy half-elfs",
        "Humming while dusting the graves",
        "Harmonizing the tombstones",
        "Writing songs to ward off the departed",
    ]
)


class Cognita(commands.Bot):
    """Main bot class that extends discord.ext.commands.Bot with additional functionality.

    This class manages the bot's lifecycle, including extension loading, database connections,
    service container management, and repository access. It serves as the central point
    for accessing all bot functionality.

    Attributes:
        initial_extensions (Sequence[str]): List of cog extensions to load on startup
        pg_con (asyncpg.Pool): PostgreSQL connection pool (kept for backward compatibility)
        db (Database): Database utility for executing SQL queries
        web_client (ClientSession): aiohttp client session for making HTTP requests
        session_maker: SQLAlchemy session maker for ORM operations
        container (ServiceContainer): Service container for dependency injection
        repo_factory (RepositoryFactory): Factory for creating repositories
    """

    def __init__(
        self,
        *args,
        initial_extensions: Sequence[str],
        critical_extensions: Sequence[str] = None,
        db_pool: asyncpg.Pool,
        http_client: HTTPClient,
        **kwargs,
    ) -> None:
        """Initialize the Cognita bot.

        Args:
            *args: Variable length argument list to pass to the parent class
            initial_extensions: List of cog extensions to load on startup
            critical_extensions: List of cog extensions that are critical and must be loaded at startup
            db_pool: PostgreSQL connection pool
            http_client: HTTP client with connection pooling
            **kwargs: Arbitrary keyword arguments to pass to the parent class
        """
        super().__init__(*args, **kwargs)
        self.initial_extensions: Sequence[str] = initial_extensions

        # Determine critical extensions (cogs that must be loaded at startup)
        # If not specified, consider all extensions as critical
        self.critical_extensions: Sequence[str] = (
            critical_extensions or initial_extensions
        )

        # Track non-critical extensions for lazy loading
        self.non_critical_extensions: Sequence[str] = [
            ext for ext in initial_extensions if ext not in self.critical_extensions
        ]

        # Track loaded extensions
        self.loaded_extensions: dict[str, bool] = dict.fromkeys(
            initial_extensions, False
        )

        self.pg_con: asyncpg.Pool = db_pool  # Keep for backward compatibility
        self.db: Database = Database(db_pool)  # New database utility
        self.http_client: HTTPClient = http_client
        self.web_client = (
            None  # For backward compatibility, will be set to http_client.get_session()
        )
        self.session_maker = async_session_maker  # SQLAlchemy session maker

        # Track startup time
        self.startup_times: dict[str, float] = {}

        # Initialize resource monitor with improved settings
        self.logger = logging.getLogger("bot")
        self.resource_monitor = ResourceMonitor(
            check_interval=300,  # Check every 5 minutes
            memory_threshold=85.0,
            cpu_threshold=80.0,
            memory_leak_threshold=52428800,  # 50MB threshold to reduce false positives
            enable_memory_leak_detection=True,
            logger=self.logger.getChild("resource_monitor"),
        )

        # Initialize service container
        self.container: ServiceContainer = ServiceContainer()

        # Register common services
        self.container.register("bot", self)
        self.container.register("db", self.db)
        self.container.register("http_client", http_client)
        self.container.register("resource_monitor", self.resource_monitor)
        self.container.register_factory("db_session", self.get_db_session)

        # Initialize repository factory
        self.repo_factory: RepositoryFactory = RepositoryFactory(
            self.container, self.get_db_session
        )

    async def get_db_session(self) -> AsyncSession:
        """Get a new SQLAlchemy database session.

        Returns:
            AsyncSession: A new SQLAlchemy async session for database operations
        """
        return self.session_maker()

    async def setup_hook(self) -> None:
        """Set up the bot before it starts running.

        This method is called automatically by discord.py before the bot starts.
        It performs the following tasks:
        1. Initializes the web client session for backward compatibility
        2. Starts the resource monitoring
        3. Starts the status rotation loop
        4. Registers repositories for database models
        5. Sets up the secret manager for secure credential handling
        6. Loads critical extensions (cogs)
        7. Sets up global exception handlers
        8. Initializes database optimizations
        9. Sets up error telemetry
        10. Initializes the permission system

        The method optimizes startup performance by:
        1. Parallelizing independent initialization tasks
        2. Lazy loading non-critical extensions
        3. Monitoring startup time for performance analysis

        Raises:
            Various exceptions may be raised during setup, but they are caught and logged
        """
        # Start overall startup time tracking
        overall_start_time = time.time()
        self.startup_times["overall_start"] = overall_start_time
        self.logger.info("Bot startup initiated")

        # Create tasks for parallel initialization
        init_tasks = []

        # Task 1: Initialize web_client for backward compatibility
        async def init_web_client() -> None:
            start_time = time.time()
            self.web_client = await self.http_client.get_session()
            self.startup_times["web_client_init"] = time.time() - start_time
            self.logger.info(
                f"Web client initialized in {self.startup_times['web_client_init']:.2f}s"
            )

        init_tasks.append(init_web_client())

        # Task 2: Start resource monitoring
        async def init_resource_monitoring() -> None:
            start_time = time.time()
            await self.resource_monitor.start_monitoring()
            self.startup_times["resource_monitoring_init"] = time.time() - start_time
            self.logger.info(
                f"Resource monitoring started in {self.startup_times['resource_monitoring_init']:.2f}s"
            )

        init_tasks.append(init_resource_monitoring())

        # Task 3: Start status rotation loop
        self.bg_task = self.loop.create_task(self.start_status_loop())

        # Task 4: Start periodic cleanup loop
        self.cleanup_task = self.loop.create_task(self.periodic_cleanup())

        # Task 5: Register repositories
        start_time = time.time()
        self.register_repositories()
        self.startup_times["repositories_init"] = time.time() - start_time
        self.logger.info(
            f"Repositories registered in {self.startup_times['repositories_init']:.2f}s"
        )

        # Wait for all parallel initialization tasks to complete
        await asyncio.gather(*init_tasks)

        # Task 6: Set up secret manager
        try:
            start_time = time.time()
            # Initialize the secret manager with the encryption key from config
            secret_manager = await setup_secret_manager(
                self, config.secret_encryption_key
            )
            # Register the secret manager in the service container
            self.container.register("secret_manager", secret_manager)
            self.startup_times["secret_manager_init"] = time.time() - start_time
            self.logger.info(
                f"Secret manager initialized in {self.startup_times['secret_manager_init']:.2f}s"
            )
        except Exception as e:
            error_details = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            self.logger.error(
                f"Failed to initialize secret manager: {e}\n{error_details}"
            )
            # Continue without secret manager, but log the error

        # Register shared command groups before loading extensions
        start_time = time.time()
        self.tree.add_command(admin)
        self.tree.add_command(mod)
        self.tree.add_command(gallery_admin)
        self.startup_times["command_groups_init"] = time.time() - start_time
        self.logger.info(
            f"Registered shared command groups in {self.startup_times['command_groups_init']:.2f}s"
        )

        # Task 6: Load critical extensions
        await self.load_extensions()

        # Task 7: Set up global exception handlers
        start_time = time.time()
        setup_global_exception_handler(self)
        self.startup_times["exception_handler_init"] = time.time() - start_time
        self.logger.info(
            f"Global exception handler set up in {self.startup_times['exception_handler_init']:.2f}s"
        )

        # Unsubscribe stats listeners if the stats cog is loaded
        if self.loaded_extensions.get("cogs.stats", False):
            start_time = time.time()
            self.unsubscribe_stats_listeners()
            self.startup_times["unsubscribe_stats"] = time.time() - start_time
            self.logger.info(
                f"Stats listeners unsubscribed in {self.startup_times['unsubscribe_stats']:.2f}s"
            )

        # Task 8 & 9: Initialize database optimizations and error telemetry in parallel
        db_tasks = []

        # Database optimizations
        async def init_db_optimizations() -> None:
            start_time = time.time()
            try:
                # Use a longer timeout (10 minutes) for database optimizations
                await self.db.execute_script(
                    "database/db_optimizations.sql", timeout=600.0
                )
                self.startup_times["db_optimizations"] = time.time() - start_time
                self.logger.info(
                    f"Database optimizations applied in {self.startup_times['db_optimizations']:.2f}s"
                )
            except Exception as e:
                error_details = "".join(
                    traceback.format_exception(type(e), e, e.__traceback__)
                )
                self.logger.error(
                    f"Failed to apply database optimizations: {e}\n{error_details}"
                )

        db_tasks.append(init_db_optimizations())

        # Error telemetry
        async def init_error_telemetry() -> None:
            start_time = time.time()
            try:
                # Use a longer timeout (5 minutes) for error telemetry table initialization
                await self.db.execute_script(
                    "database/error_telemetry.sql", timeout=300.0
                )
                self.startup_times["error_telemetry"] = time.time() - start_time
                self.logger.info(
                    f"Error telemetry table initialized in {self.startup_times['error_telemetry']:.2f}s"
                )
            except Exception as e:
                error_details = "".join(
                    traceback.format_exception(type(e), e, e.__traceback__)
                )
                self.logger.error(
                    f"Failed to initialize error telemetry table: {e}\n{error_details}"
                )

        db_tasks.append(init_error_telemetry())

        # Wait for database tasks to complete
        await asyncio.gather(*db_tasks)

        # Task 10: Initialize permission system
        try:
            # Set up the permission system
            start_time = time.time()
            await setup_permissions(self)
            self.startup_times["permissions_init"] = time.time() - start_time
            self.logger.info(
                f"Permission system initialized in {self.startup_times['permissions_init']:.2f}s"
            )
        except Exception as e:
            error_details = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            self.logger.error(
                f"Failed to initialize permission system: {e}\n{error_details}"
            )

        # Record overall startup time
        self.startup_times["overall_time"] = time.time() - overall_start_time
        self.logger.info(
            f"Bot startup completed in {self.startup_times['overall_time']:.2f}s"
        )

        # Log startup time summary
        self.log_startup_time_summary()

        # Check if environment is production and run comprehensive save
        if config.ENVIRONMENT == config.Environment.PRODUCTION:
            self.logger.info(
                "Production environment detected - starting comprehensive save operation"
            )
            try:
                from cogs.stats_utils import perform_comprehensive_save

                # Define a simple progress callback for logging
                async def log_progress(
                    guilds_processed,
                    total_guilds,
                    channels_processed,
                    messages_saved,
                    errors_encountered,
                    elapsed_time,
                    current_guild_name,
                ) -> None:
                    self.logger.info(
                        f"Comprehensive save progress: {guilds_processed}/{total_guilds} guilds, "
                        f"{channels_processed} channels, {messages_saved} messages saved, "
                        f"{errors_encountered} errors, elapsed: {elapsed_time}, "
                        f"current guild: {current_guild_name}"
                    )

                # Define a completion callback for logging
                async def log_completion(results) -> None:
                    self.logger.info(
                        f"Comprehensive save completed: {results['guilds_processed']} guilds processed, "
                        f"{results['channels_processed']} channels processed, "
                        f"{results['messages_saved']} messages saved, "
                        f"{results['errors_encountered']} errors encountered, "
                        f"total time: {results['total_time']}"
                    )

                # Run the comprehensive save operation
                start_time = time.time()
                await perform_comprehensive_save(
                    self,
                    progress_callback=log_progress,
                    completion_callback=log_completion,
                )
                comprehensive_save_time = time.time() - start_time
                self.startup_times["comprehensive_save"] = comprehensive_save_time

                self.logger.info(
                    f"Production comprehensive save completed in {comprehensive_save_time:.2f}s"
                )

            except Exception as e:
                error_details = "".join(
                    traceback.format_exception(type(e), e, e.__traceback__)
                )
                self.logger.error(
                    f"Failed to run comprehensive save in production: {e}\n{error_details}"
                )

    def register_repositories(self) -> None:
        """Register repositories for all database models.

        This method registers all repositories using the register_repositories function
        and then verifies that critical repositories are available by attempting to
        retrieve them from the repository factory.

        Raises:
            ValueError: If a required repository cannot be found
        """
        # Register repositories using the register_repositories function
        register_repositories(self.repo_factory)

        # Ensure repositories are available
        self.repo_factory.get_repository(GalleryMementos)
        self.repo_factory.get_repository(CreatorLink)

    async def load_extensions(self) -> None:
        """Load critical extensions (cogs) at startup.

        This method attempts to load each critical extension and logs any errors that occur
        during the loading process. It does not stop if one extension fails to load.
        Non-critical extensions are loaded lazily when needed.

        Raises:
            No exceptions are raised directly, but errors are logged
        """
        start_time = time.time()
        self.startup_times["load_extensions_start"] = start_time

        self.logger.info(f"Loading {len(self.critical_extensions)} critical extensions")

        for extension in self.critical_extensions:
            ext_start_time = time.time()
            try:
                await self.load_extension(extension)
                self.loaded_extensions[extension] = True
                ext_load_time = time.time() - ext_start_time
                self.startup_times[f"load_extension_{extension}"] = ext_load_time
                self.logger.info(
                    f"Loaded critical extension {extension} in {ext_load_time:.2f}s"
                )
            except Exception as e:
                self.logger.exception(
                    f"Failed to load critical extension {extension} - {e}"
                )

        total_time = time.time() - start_time
        self.startup_times["load_extensions_total"] = total_time
        self.logger.info(f"Loaded all critical extensions in {total_time:.2f}s")

        # Log which extensions will be loaded lazily
        if self.non_critical_extensions:
            self.logger.info(
                f"The following extensions will be loaded lazily: {', '.join(self.non_critical_extensions)}"
            )

    async def load_extension_if_needed(self, extension: str) -> bool:
        """Load an extension if it's not already loaded.

        Args:
            extension: The extension to load

        Returns:
            bool: True if the extension was loaded or already loaded, False if it failed to load

        Raises:
            No exceptions are raised directly, but errors are logged
        """
        if extension not in self.initial_extensions:
            self.logger.warning(f"Attempted to load unknown extension: {extension}")
            return False

        if self.loaded_extensions.get(extension, False):
            return True

        try:
            start_time = time.time()
            await self.load_extension(extension)
            self.loaded_extensions[extension] = True
            load_time = time.time() - start_time
            self.logger.info(f"Lazily loaded extension {extension} in {load_time:.2f}s")
            return True
        except Exception as e:
            self.logger.exception(f"Failed to lazily load extension {extension} - {e}")
            return False

    def log_startup_time_summary(self) -> None:
        """Log a summary of startup times for performance analysis.

        This method creates a formatted summary of all startup time metrics
        and logs it at INFO level. The summary includes overall startup time
        and individual component initialization times.
        """
        # Create a formatted summary
        summary = [
            "=== Startup Time Summary ===",
            f"Overall startup time: {self.startup_times.get('overall_time', 0):.2f}s",
        ]

        # Add individual component times
        components = [
            ("web_client_init", "Web client initialization"),
            ("resource_monitoring_init", "Resource monitoring initialization"),
            ("repositories_init", "Repository registration"),
            ("secret_manager_init", "Secret manager initialization"),
            ("load_extensions_total", "Critical extensions loading"),
            ("exception_handler_init", "Exception handler setup"),
            ("db_optimizations", "Database optimizations"),
            ("error_telemetry", "Error telemetry setup"),
            ("permissions_init", "Permission system initialization"),
        ]

        for key, label in components:
            if key in self.startup_times:
                summary.append(f"{label}: {self.startup_times[key]:.2f}s")

        # Add extension loading times if available
        extension_times = [
            (k, v)
            for k, v in self.startup_times.items()
            if k.startswith("load_extension_")
        ]
        if extension_times:
            summary.append("\n=== Extension Loading Times ===")
            for key, value in sorted(extension_times, key=lambda x: x[1], reverse=True):
                ext_name = key.replace("load_extension_", "")
                summary.append(f"{ext_name}: {value:.2f}s")

        # Log the summary
        self.logger.info("\n".join(summary))

        # Store startup times in database for historical analysis
        asyncio.create_task(self._store_startup_times())

    async def _store_startup_times(self) -> None:
        """Store startup time metrics in the database for historical analysis.

        This method runs as a background task to avoid blocking the startup process.
        It stores the startup time metrics in a database table for later analysis.
        """
        try:
            # Ensure the bot_metrics table exists
            await self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_metrics (
                    id          SERIAL PRIMARY KEY,
                    timestamp   TIMESTAMP NOT NULL DEFAULT NOW(),
                    metric_type VARCHAR NOT NULL,
                    metric_data JSON
                )
                """
            )

            # Convert startup times to JSON
            startup_data = json.dumps(self.startup_times)

            # Store in database
            await self.db.execute(
                """
                INSERT INTO bot_metrics(
                    timestamp, 
                    metric_type, 
                    metric_data
                )
                VALUES($1, $2, $3)
                """,
                datetime.datetime.now(),
                "startup_time",
                startup_data,
            )
            self.logger.debug("Startup time metrics stored in database")
        except Exception as e:
            error_details = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            self.logger.error(
                f"Failed to store startup time metrics: {e}\n{error_details}"
            )

    def unsubscribe_stats_listeners(self) -> None:
        """Unsubscribe event listeners from the stats cog.

        This method removes specific event listeners from the stats cog to prevent
        duplicate event handling. This is necessary because the stats cog registers
        its own event listeners, but we need to control when they are active.
        """
        stats_cog = self.get_cog("stats")
        if stats_cog is None:
            self.logger.warning("Stats cog not found, cannot unsubscribe listeners")
            return

        self.remove_listener(stats_cog.save_listener, "on_message")
        self.remove_listener(stats_cog.message_deleted, "on_raw_message_delete")
        self.remove_listener(stats_cog.message_edited, "on_raw_message_edit")
        self.remove_listener(stats_cog.reaction_add, "on_raw_reaction_add")
        self.remove_listener(stats_cog.reaction_remove, "on_raw_reaction_remove")

    async def on_ready(self) -> None:
        """Event handler that is called when the bot is ready and connected to Discord.

        This method logs information about the bot's identity once it has successfully
        connected to Discord.
        """
        logging.info(f"Logged in as {self.user.name} (ID: {self.user.id})")

    # Error handling is now managed by setup_global_exception_handler

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: discord.app_commands.Command | discord.app_commands.ContextMenu,
    ) -> None:
        """Event handler that is called when an application command completes successfully.

        This method updates the command history in the database with information about
        the completed command, including its run time and completion status.

        Args:
            interaction: The interaction that triggered the command
            command: The command that was executed

        Note:
            This method expects 'start_time' and 'id' to be present in interaction.extras,
            which are set in the on_interaction method.
        """
        end_date = datetime.datetime.now()
        if "start_time" in interaction.extras:
            run_time = end_date - interaction.extras["start_time"]
            if "id" in interaction.extras:
                try:
                    await self.db.execute(
                        """
                        UPDATE command_history 
                        SET 
                            run_time=$1, 
                            finished_successfully=TRUE,
                            end_date=$2 
                        WHERE serial=$3
                        """,
                        run_time,
                        end_date,
                        interaction.extras["id"],
                    )
                except Exception as e:
                    error_details = "".join(
                        traceback.format_exception(type(e), e, e.__traceback__)
                    )
                    logging.error(
                        f"Error updating command history: {e}\n{error_details}"
                    )
            else:
                # Log detailed information about the interaction
                interaction_details = f"Command: {command.name if command else 'Unknown'}, User: {interaction.user.id}, Guild: {interaction.guild.id if interaction.guild else 'None'}"
                logging.error(
                    f"No command history ID in extra dict. Interaction details: {interaction_details}"
                )
        else:
            # Log detailed information about the interaction
            interaction_details = f"Command: {command.name if command else 'Unknown'}, User: {interaction.user.id}, Guild: {interaction.guild.id if interaction.guild else 'None'}"
            logging.error(
                f"No start time in extra dict. Interaction details: {interaction_details}"
            )

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Event handler that is called when an interaction is created.

        This method records information about the interaction in the command_history table,
        including the user, guild, command name, and arguments. It also sets up tracking
        information in interaction.extras for use in on_app_command_completion.

        Args:
            interaction: The interaction that was created

        Note:
            This method sets 'start_time' and 'id' in interaction.extras, which are used
            by on_app_command_completion to update the command history record.
        """
        user_id = interaction.user.id  # get id of the user who performed the command
        guild_id = (
            interaction.guild.id if interaction.guild else None
        )  # get the id of the guild
        if interaction.command is not None:
            command_name = interaction.command.name  # get the name of the command
        else:
            command_name = None
        # check if the channel is a thread or channel:
        if interaction.channel.type == discord.ChannelType.text:
            channel_id = interaction.channel.id  # get the id of the channel
        else:
            channel_id = None
        slash_command = isinstance(interaction.command, discord.app_commands.Command)
        started_successfully = not interaction.command_failed
        command_args = json.dumps(
            interaction.data.get("options", [])
        )  # Convert options to JSON string
        start_date = datetime.datetime.now()

        sql_query = """
            INSERT INTO command_history(
                start_date, 
                user_id, 
                command_name, 
                channel_id, 
                guild_id, 
                slash_command, 
                args, 
                started_successfully
            )
            VALUES($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING serial
            """
        try:
            serial = await self.db.fetchval(
                sql_query,
                start_date,
                user_id,
                command_name,
                channel_id,
                guild_id,
                slash_command,
                command_args,
                started_successfully,
            )

            interaction.extras["id"] = serial
            interaction.extras["start_time"] = start_date
        except Exception as e:
            error_details = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            logging.error(f"Error recording command history: {e}\n{error_details}")
            # Still set start_time and id (as None) so we don't get errors in on_app_command_completion
            interaction.extras["start_time"] = start_date
            interaction.extras["id"] = None

    async def start_status_loop(self) -> None:
        """Start a background task that rotates the bot's status message.

        This method creates an infinite loop that changes the bot's status message
        every 10 seconds, cycling through the messages defined in the status cycle.
        The loop continues until the bot is closed.
        """
        await self.wait_until_ready()
        while not self.is_closed():
            await self.change_presence(activity=discord.Game(next(status)))
            await asyncio.sleep(10)

    async def periodic_cleanup(self) -> None:
        """Perform periodic cleanup tasks to maintain bot health.
        Now uses a smarter approach that doesn't interfere with active operations.
        """
        while not self.is_closed():
            await asyncio.sleep(1800)  # Every 30 minutes

            try:
                # Force garbage collection
                import gc

                collected = gc.collect()
                self.logger.info(f"Periodic cleanup: collected {collected} objects")

                # Only recreate the shared session if it's been idle
                # The webhook operations now use fresh sessions, so this won't cause conflicts
                if hasattr(self.http_client, "_session") and self.http_client._session:
                    # Check if the session has any active connections
                    connector = self.http_client._session.connector
                    if connector and hasattr(connector, "_conns"):
                        active_connections = sum(
                            len(conns) for conns in connector._conns.values()
                        )
                        if (
                            active_connections == 0
                        ):  # Only recreate if no active connections
                            old_session = self.http_client._session
                            self.http_client._session = None
                            await old_session.close()
                            self.logger.info(
                                "HTTP session recreated for cleanup (no active connections)"
                            )
                        else:
                            self.logger.debug(
                                f"Skipping session recreation: {active_connections} active connections"
                            )

                # Log current resource usage after cleanup
                if hasattr(self, "resource_monitor"):
                    stats = self.resource_monitor.get_resource_stats()
                    self.logger.info(
                        f"Post-cleanup stats: Memory: {stats['memory_percent']:.1f}%, "
                        f"Connections: {stats['connection_count']}"
                    )

            except Exception as e:
                self.logger.error(f"Error during periodic cleanup: {e}")

    async def close(self) -> None:
        """Close the bot and clean up resources.

        This method is called when the bot is shutting down. It stops the resource monitoring,
        closes the HTTP client, and performs any other necessary cleanup before calling the
        parent class's close method.
        """
        # Stop resource monitoring
        if hasattr(self, "resource_monitor") and self.resource_monitor:
            await self.resource_monitor.stop_monitoring()
            self.logger.info("Resource monitoring stopped")

        # Close the HTTP client
        if hasattr(self, "http_client") and self.http_client:
            await self.http_client.close()
            self.logger.info("HTTP client closed")

        # Call the parent class's close method
        await super().close()


async def main() -> None:
    """Main entry point for the application.

    This function performs the following tasks:
    1. Sets up logging configuration
    2. Establishes database connection with SSL
    3. Creates and configures the bot instance
    4. Sets up auto-kill functionality if enabled
    5. Starts the bot

    The function uses asyncio to manage asynchronous operations and ensures proper
    resource cleanup through context managers.
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(config.logging_level)

    # Configure discord logger
    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(config.logging_level)

    # Clear any existing handlers to prevent duplicate logging
    root_logger.handlers.clear()
    discord_logger.handlers.clear()

    # Create handler for file logging
    import os

    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join("logs", f"{config.logfile}.log"),
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024,
        backupCount=10,
    )

    # Create console handler for stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.logging_level)

    # Create formatter that includes detailed information
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message} :{lineno}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )
    handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to root logger only
    # Child loggers (like discord_logger) will inherit handlers from root
    root_logger.addHandler(handler)
    root_logger.addHandler(console_handler)

    root_logger.info("Logging started...")

    # Log the KILL_AFTER setting
    if config.kill_after > 0:
        root_logger.info(
            f"Bot will automatically exit after {config.kill_after} seconds"
        )

    # Configure SSL based on environment (Railway vs GCP)
    # Railway uses simple SSL, GCP uses custom certificates
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Railway environment - use simple SSL requirement
        ssl_config = "require"
        root_logger.info("Using Railway SSL configuration (ssl='require')")
    else:
        # GCP Cloud SQL - use custom SSL certificates
        context = ssl.create_default_context()
        context.check_hostname = False
        context.load_verify_locations("ssl-cert/server-ca.pem")
        context.load_cert_chain("ssl-cert/client-cert.pem", "ssl-cert/client-key.pem")
        ssl_config = context
        root_logger.info("Using GCP Cloud SQL SSL configuration (custom certificates)")

    # Create HTTP client with connection pooling and aggressive cleanup
    http_client = HTTPClient(
        timeout=30,
        max_connections=50,  # Reduce from 100
        max_keepalive_connections=10,  # Reduce from 30
        keepalive_timeout=30,  # Reduce from 60
        logger=root_logger.getChild("http_client"),
    )

    async with asyncpg.create_pool(
        database=config.database,
        user=config.DB_user,
        password=config.DB_password,
        host=config.host,
        ssl=ssl_config,
        command_timeout=300,
        min_size=5,  # Minimum number of connections
        max_size=20,  # Maximum number of connections
        max_inactive_connection_lifetime=180.0,  # Reduce from 300 to 180 seconds (3 minutes)
        max_cached_statement_lifetime=300.0,  # Add statement cache lifetime
        timeout=30.0,  # Connection timeout
    ) as pool:
        # Define all cogs
        cogs = [
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
            "cogs.summarization",
            "cogs.settings",
            "cogs.interactive_help",
        ]

        # Define critical cogs that must be loaded at startup
        # These are cogs that provide essential functionality or are required by other cogs
        base_critical_cogs = [
            "cogs.owner",  # Owner commands for bot management
            "cogs.mods",  # Moderation commands
            "cogs.stats",  # Core statistics tracking
            "cogs.settings",  # Bot settings management
            "cogs.interactive_help",  # Interactive help system
        ]

        # In production (live) mode, load all cogs at startup for better performance
        # In testing mode, use lazy loading to speed up testing and development
        if config.ENVIRONMENT == config.Environment.PRODUCTION:
            critical_cogs = cogs  # Load all cogs at startup in production
            root_logger.info("Production mode: Loading all cogs at startup")
        else:
            critical_cogs = (
                base_critical_cogs  # Use lazy loading in development/testing
            )
            root_logger.info(
                "Development/Testing mode: Using lazy loading for non-critical cogs"
            )

        # Non-critical cogs will be loaded lazily when needed
        root_logger.info(f"Critical cogs: {', '.join(critical_cogs)}")
        root_logger.info(
            f"Non-critical cogs: {', '.join([cog for cog in cogs if cog not in critical_cogs])}"
        )

        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        async with Cognita(
            commands.when_mentioned_or("!"),
            db_pool=pool,
            http_client=http_client,
            initial_extensions=cogs,
            critical_extensions=critical_cogs,
            intents=intents,
            help_command=None,
        ) as bot:
            # Set up auto-kill task if enabled
            if config.kill_after > 0:

                async def kill_bot_after_delay() -> None:
                    """Background task that automatically kills the bot after a specified delay.

                    This function waits for the number of seconds specified in config.kill_after,
                    then logs a message and closes the bot. This is useful for testing and
                    development environments where the bot should not run indefinitely.
                    """
                    await asyncio.sleep(config.kill_after)
                    root_logger.info(
                        f"Auto-kill triggered after {config.kill_after} seconds"
                    )
                    await bot.close()

                # Schedule the kill task
                bot.loop.create_task(kill_bot_after_delay())
            await bot.start(config.bot_token)


asyncio.run(main())

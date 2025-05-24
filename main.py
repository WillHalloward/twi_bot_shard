import asyncio
import json
import logging
import logging.handlers
import ssl
import traceback
from itertools import cycle
from collections.abc import Sequence
from typing import TypeAlias, Dict, Type
import datetime
import asyncpg
import discord
from aiohttp import ClientSession
from discord.ext import commands

import config
from utils.error_handling import handle_global_command_error
import sys

# Define type aliases for complex types
DiscordID: TypeAlias = int
CommandName: TypeAlias = str
from utils.db import Database
from utils.sqlalchemy_db import async_session_maker
from sqlalchemy.ext.asyncio import AsyncSession
from utils.service_container import ServiceContainer
from utils.repository_factory import RepositoryFactory
from models.tables.gallery import GalleryMementos
from models.tables.creator_links import CreatorLink

status = cycle(["Killing the mages of Wistram",
                "Cleaning up a mess",
                "Hiding corpses",
                "Mending Pirateaba's broken hands",
                "Hoarding knowledge",
                "Dusting off priceless artifacts",
                "Praying for Mating Rituals 4",
                "Plotting demise of nosy half-elfs",
                "Humming while dusting the graves",
                "Harmonizing the tombstones",
                "Writing songs to ward off the departed"])


class Cognita(commands.Bot):
    def __init__(
            self,
            *args,
            initial_extensions: Sequence[str],
            db_pool: asyncpg.Pool,
            web_client: ClientSession,
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.initial_extensions = initial_extensions
        self.pg_con = db_pool  # Keep for backward compatibility
        self.db = Database(db_pool)  # New database utility
        self.web_client = web_client
        self.session_maker = async_session_maker  # SQLAlchemy session maker

        # Initialize service container
        self.container = ServiceContainer()

        # Register common services
        self.container.register("bot", self)
        self.container.register("db", self.db)
        self.container.register("web_client", web_client)
        self.container.register_factory("db_session", self.get_db_session)

        # Initialize repository factory
        self.repo_factory = RepositoryFactory(self.container, self.get_db_session)

    async def get_db_session(self) -> AsyncSession:
        """Get a new database session."""
        return self.session_maker()

    async def setup_hook(self) -> None:
        self.bg_task = self.loop.create_task(self.start_status_loop())

        # Register repositories
        self.register_repositories()

        await self.load_extensions()
        self.unsubscribe_stats_listeners()

        # Register global error handler
        self.tree.error(self.on_app_command_error)
        self.add_listener(self.on_command_error, "on_command_error")

        # Initialize database optimizations
        try:
            # Use a longer timeout (10 minutes) for database optimizations
            await self.db.execute_script("database/db_optimizations.sql", timeout=600.0)
            logging.info("Database optimizations applied successfully")
        except Exception as e:
            error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            logging.error(f"Failed to apply database optimizations: {e}\n{error_details}")

        # Initialize error telemetry table
        try:
            # Use a longer timeout (5 minutes) for error telemetry table initialization
            await self.db.execute_script("database/error_telemetry.sql", timeout=300.0)
            logging.info("Error telemetry table initialized successfully")
        except Exception as e:
            error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            logging.error(f"Failed to initialize error telemetry table: {e}\n{error_details}")

    def register_repositories(self):
        """Register repositories for all models."""
        # Register repositories for models
        # For now, we'll use the generic repository for all models
        self.repo_factory.get_repository(GalleryMementos)
        self.repo_factory.get_repository(CreatorLink)

        # More repositories can be registered here as needed

    async def load_extensions(self):
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception as e:
                logging.exception(f"Failed to load cog {extension} - {e}")

    def unsubscribe_stats_listeners(self):
        stats_cog = self.get_cog("stats")
        self.remove_listener(stats_cog.save_listener, "on_message")
        self.remove_listener(stats_cog.message_deleted, "on_raw_message_delete")
        self.remove_listener(stats_cog.message_edited, "on_raw_message_edit")
        self.remove_listener(stats_cog.reaction_add, "on_raw_reaction_add")
        self.remove_listener(stats_cog.reaction_remove, "on_raw_reaction_remove")

    async def on_ready(self):
        logging.info(f"Logged in as {self.user.name} (ID: {self.user.id})")

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Global error handler for command errors."""
        await handle_global_command_error(ctx, error)

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Global error handler for application command errors."""
        # Extract the original exception if it's wrapped
        if hasattr(error, 'original'):
            error = error.original

        # Get command name
        command_name = "unknown"
        if interaction.command:
            command_name = interaction.command.name

        # Log the error
        error_details = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        logging.error(f"Application command error in {command_name}: {error}\n{error_details}")

        # Send error message to user
        try:
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred while processing your command.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while processing your command.", ephemeral=True)
        except Exception as e:
            error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            logging.error(f"Failed to send error message to user: {e}\n{error_details}")

        # Record error telemetry
        try:
            await self.db.execute(
                """
                INSERT INTO error_telemetry(
                    error_type, command_name, user_id, error_message, 
                    guild_id, channel_id, timestamp
                )
                VALUES($1, $2, $3, $4, $5, $6, $7)
                """,
                type(error).__name__,
                command_name,
                interaction.user.id,
                str(error),
                interaction.guild.id if interaction.guild else None,
                interaction.channel.id if interaction.channel else None,
                datetime.datetime.now()
            )
        except Exception as e:
            error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            logging.error(f"Failed to record error telemetry: {e}\n{error_details}")

    async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command | discord.app_commands.ContextMenu):
        end_date = datetime.datetime.now()
        if 'start_time' in interaction.extras:
            run_time = end_date - interaction.extras['start_time']
            if 'id' in interaction.extras:
                try:
                    await self.db.execute("""
                        UPDATE command_history 
                        SET 
                            run_time=$1, 
                            finished_successfully=TRUE,
                            end_date=$2 
                        WHERE serial=$3
                        """, run_time, end_date, interaction.extras['id'])
                except Exception as e:
                    error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                    logging.error(f"Error updating command history: {e}\n{error_details}")
            else:
                # Log detailed information about the interaction
                interaction_details = f"Command: {command.name if command else 'Unknown'}, User: {interaction.user.id}, Guild: {interaction.guild.id if interaction.guild else 'None'}"
                logging.error(f"No command history ID in extra dict. Interaction details: {interaction_details}")
        else:
            # Log detailed information about the interaction
            interaction_details = f"Command: {command.name if command else 'Unknown'}, User: {interaction.user.id}, Guild: {interaction.guild.id if interaction.guild else 'None'}"
            logging.error(f"No start time in extra dict. Interaction details: {interaction_details}")


    async def on_interaction(self, interaction: discord.Interaction):
        user_id = interaction.user.id  # get id of the user who performed the command
        guild_id = interaction.guild.id if interaction.guild else None  # get the id of the guild
        if interaction.command is not None:
            command_name = interaction.command.name   # get the name of the command
        else:
            command_name = None
        #check if the channel is a thread or channel:
        if interaction.channel.type == discord.ChannelType.text:
            channel_id = interaction.channel.id # get the id of the channel
        else:
            channel_id = None
        slash_command = isinstance(interaction.command, discord.app_commands.Command)
        started_successfully = not interaction.command_failed
        command_args = json.dumps(interaction.data.get('options', []))  # Convert options to JSON string
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
            serial = await self.db.fetchval(sql_query,
                                            start_date,
                                            user_id,
                                            command_name,
                                            channel_id,
                                            guild_id,
                                            slash_command,
                                            command_args,
                                            started_successfully)

            interaction.extras['id'] = serial
            interaction.extras['start_time'] = start_date
        except Exception as e:
            error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            logging.error(f"Error recording command history: {e}\n{error_details}")
            # Still set start_time and id (as None) so we don't get errors in on_app_command_completion
            interaction.extras['start_time'] = start_date
            interaction.extras['id'] = None

    async def start_status_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            await self.change_presence(activity=discord.Game(next(status)))
            await asyncio.sleep(10)


async def main():
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(config.logging_level)

    # Configure discord logger
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(config.logging_level)

    # Clear any existing handlers to prevent duplicate logging
    root_logger.handlers.clear()
    discord_logger.handlers.clear()

    # Create handler for file logging
    import os
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join("logs", f'{config.logfile}.log'),
        encoding='utf-8',
        maxBytes=32 * 1024 * 1024,
        backupCount=10
    )

    # Create console handler for stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.logging_level)

    # Create formatter that includes detailed information
    formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message} :{lineno}', datefmt='%Y-%m-%d %H:%M:%S', style='{')
    handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to root logger only
    # Child loggers (like discord_logger) will inherit handlers from root
    root_logger.addHandler(handler)
    root_logger.addHandler(console_handler)

    root_logger.info("Logging started...")

    # Log the KILL_AFTER setting
    if config.kill_after > 0:
        root_logger.info(f"Bot will automatically exit after {config.kill_after} seconds")

    context = ssl.create_default_context()
    context.check_hostname = False
    context.load_verify_locations(f"ssl-cert/server-ca.pem")
    context.load_cert_chain(f"ssl-cert/client-cert.pem", f"ssl-cert/client-key.pem")

    async with ClientSession() as our_client, asyncpg.create_pool(
            database=config.database,
            user=config.DB_user,
            password=config.DB_password,
            host=config.host,
            ssl=context,
            command_timeout=300,
            min_size=5,           # Minimum number of connections
            max_size=20,          # Maximum number of connections
            max_inactive_connection_lifetime=300.0,  # Close inactive connections after 5 minutes
            timeout=30.0          # Connection timeout
        ) as pool:
        cogs = ['cogs.gallery', 'cogs.links_tags', 'cogs.patreon_poll', 'cogs.twi', 'cogs.owner', 'cogs.other', 'cogs.mods', 'cogs.stats', 'cogs.creator_links', 'cogs.report', 'cogs.summarization', 'cogs.settings']
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        async with Cognita(
                commands.when_mentioned_or("!"),
                db_pool=pool,
                web_client=our_client,
                initial_extensions=cogs,
                intents=intents
        ) as bot:
            # Set up auto-kill task if enabled
            if config.kill_after > 0:
                async def kill_bot_after_delay():
                    await asyncio.sleep(config.kill_after)
                    root_logger.info(f"Auto-kill triggered after {config.kill_after} seconds")
                    await bot.close()
                    exit(1)

                # Schedule the kill task
                bot.loop.create_task(kill_bot_after_delay())
            await bot.start(config.bot_token)


asyncio.run(main())

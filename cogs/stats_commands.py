"""
Command methods for the stats system.

This module contains all the command methods for saving different types of data
to the database. These commands are typically owner-only and used for data management.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import asyncpg
import discord
from discord.ext import commands

from utils.error_handling import handle_command_errors
from utils.exceptions import DatabaseError, QueryError, ValidationError
from utils.permissions import admin_or_me_check_wrapper
from .stats_utils import save_message

if TYPE_CHECKING:
    from discord.ext.commands import Context


class StatsCommandsMixin:
    """Mixin class containing all stats-related command methods."""

    @commands.command(name="save_users", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_users(self, ctx: "Context") -> None:
        """
        Save all guild members to the database.

        This command processes all members from all guilds the bot is in,
        adding new users to the users table and updating server memberships.

        Args:
            ctx: The command context

        Raises:
            DatabaseError: If database operations fail
            QueryError: If there's an issue with SQL queries
        """
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass  # Message already deleted
        except discord.Forbidden:
            self.logger.warning("No permission to delete command message")

        total_users_added = 0
        total_memberships_added = 0
        guilds_processed = 0

        try:
            for guild in self.bot.guilds:
                self.logger.info(f"Processing guild: {guild.name} ({guild.id})")
                members_list = guild.members

                if not members_list:
                    self.logger.warning(f"No members found in guild {guild.name}")
                    continue

                # Get all member IDs for this batch
                member_ids = [member.id for member in members_list]

                try:
                    # Query only the relevant user IDs in a single query
                    existing_user_ids = await self.bot.db.fetch(
                        "SELECT user_id FROM users WHERE user_id = ANY($1)", member_ids
                    )
                    existing_user_ids_set = {
                        row["user_id"] for row in existing_user_ids
                    }

                    # Query only the relevant membership IDs in a single query
                    existing_memberships = await self.bot.db.fetch(
                        "SELECT user_id FROM server_membership WHERE user_id = ANY($1) AND server_id = $2",
                        member_ids,
                        guild.id,
                    )
                    existing_memberships_set = {
                        row["user_id"] for row in existing_memberships
                    }
                except asyncpg.PostgresError as e:
                    raise DatabaseError(
                        f"Failed to query existing users/memberships for guild {guild.name}"
                    ) from e

                # Prepare batch operations
                users_to_add = []
                memberships_to_add = []

                for member in members_list:
                    if member.id not in existing_user_ids_set:
                        users_to_add.append(
                            (
                                member.id,
                                member.created_at.replace(tzinfo=None),
                                member.bot,
                                member.name,
                            )
                        )
                        memberships_to_add.append((member.id, member.guild.id))
                        self.logger.debug(
                            f"Queued new user: {member.name} ({member.id})"
                        )
                    elif member.id not in existing_memberships_set:
                        memberships_to_add.append((member.id, member.guild.id))
                        self.logger.debug(
                            f"Queued membership for existing user: {member.name} ({member.id})"
                        )

                # Execute batch operations
                try:
                    if users_to_add:
                        await self.bot.db.execute_many(
                            "INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4)",
                            users_to_add,
                        )
                        total_users_added += len(users_to_add)
                        self.logger.info(
                            f"Added {len(users_to_add)} new users from guild {guild.name}"
                        )

                    if memberships_to_add:
                        await self.bot.db.execute_many(
                            "INSERT INTO server_membership(user_id, server_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                            memberships_to_add,
                        )
                        total_memberships_added += len(memberships_to_add)
                        self.logger.info(
                            f"Added {len(memberships_to_add)} memberships from guild {guild.name}"
                        )

                except asyncpg.PostgresError as e:
                    raise DatabaseError(
                        f"Failed to insert users/memberships for guild {guild.name}"
                    ) from e

                guilds_processed += 1

        except DatabaseError:
            # Re-raise database errors as-is
            raise
        except Exception as e:
            raise QueryError(f"Unexpected error during user saving process") from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **User saving completed successfully!**\n"
            f"**Guilds processed:** {guilds_processed}\n"
            f"**New users added:** {total_users_added}\n"
            f"**Memberships added:** {total_memberships_added}"
        )

    @commands.command(name="save_servers", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_servers(self, ctx: "Context") -> None:
        """
        Save all guild information to the database.

        This command processes all guilds the bot is in,
        adding new servers to the servers table.

        Args:
            ctx: The command context

        Raises:
            DatabaseError: If database operations fail
            QueryError: If there's an issue with SQL queries
        """
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass  # Message already deleted
        except discord.Forbidden:
            self.logger.warning("No permission to delete command message")

        servers_processed = 0
        servers_added = 0

        try:
            for guild in self.bot.guilds:
                self.logger.info(f"Processing server: {guild.name} ({guild.id})")

                try:
                    result = await self.bot.db.execute(
                        "INSERT INTO servers(server_id, server_name, creation_date) VALUES ($1,$2,$3)"
                        " ON CONFLICT (server_id) DO UPDATE SET server_name = $2",
                        guild.id,
                        guild.name,
                        guild.created_at.replace(tzinfo=None),
                    )

                    # Check if a new row was inserted
                    if "INSERT" in result:
                        servers_added += 1
                        self.logger.info(f"Added new server: {guild.name}")
                    else:
                        self.logger.debug(f"Updated existing server: {guild.name}")

                except asyncpg.PostgresError as e:
                    raise DatabaseError(
                        f"Failed to save server '{guild.name}' ({guild.id})"
                    ) from e

                servers_processed += 1

        except DatabaseError:
            # Re-raise database errors as-is
            raise
        except Exception as e:
            raise QueryError(f"Unexpected error during server saving process") from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **Server saving completed successfully!**\n"
            f"**Servers processed:** {servers_processed}\n"
            f"**New servers added:** {servers_added}\n"
            f"**Existing servers updated:** {servers_processed - servers_added}"
        )

    @commands.command(name="save_channels", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_channels(self, ctx: "Context") -> None:
        """
        Save all text channels to the database.

        This command processes all text channels from all guilds the bot is in,
        adding new channels to the channels table.

        Args:
            ctx: The command context

        Raises:
            DatabaseError: If database operations fail
            QueryError: If there's an issue with SQL queries
        """
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass  # Message already deleted
        except discord.Forbidden:
            self.logger.warning("No permission to delete command message")

        guilds_processed = 0
        channels_processed = 0
        channels_added = 0
        channels_updated = 0

        try:
            for guild in self.bot.guilds:
                self.logger.info(
                    f"Processing channels for guild: {guild.name} ({guild.id})"
                )
                guild_channels_processed = 0

                for channel in guild.text_channels:
                    try:
                        result = await self.bot.db.execute(
                            "INSERT INTO "
                            "channels(id, name, category_id, created_at, guild_id, position, topic, is_nsfw) "
                            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) "
                            "ON CONFLICT (id) DO UPDATE SET "
                            "name = $2, category_id = $3, position = $6, topic = $7, is_nsfw = $8",
                            channel.id,
                            channel.name,
                            channel.category_id,
                            channel.created_at.replace(tzinfo=None),
                            channel.guild.id,
                            channel.position,
                            channel.topic,
                            channel.is_nsfw(),
                        )

                        # Check if a new row was inserted
                        if "INSERT" in result:
                            channels_added += 1
                            self.logger.debug(f"Added new channel: {channel.name}")
                        else:
                            channels_updated += 1
                            self.logger.debug(
                                f"Updated existing channel: {channel.name}"
                            )

                    except asyncpg.PostgresError as e:
                        raise DatabaseError(
                            f"Failed to save channel '{channel.name}' ({channel.id}) in guild {guild.name}"
                        ) from e

                    channels_processed += 1
                    guild_channels_processed += 1

                self.logger.info(
                    f"Processed {guild_channels_processed} channels from guild {guild.name}"
                )
                guilds_processed += 1

        except DatabaseError:
            # Re-raise database errors as-is
            raise
        except Exception as e:
            raise QueryError(f"Unexpected error during channel saving process") from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **Channel saving completed successfully!**\n"
            f"**Guilds processed:** {guilds_processed}\n"
            f"**Channels processed:** {channels_processed}\n"
            f"**New channels added:** {channels_added}\n"
            f"**Existing channels updated:** {channels_updated}"
        )

    @commands.command(name="save_categories", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_categories(self, ctx: "Context") -> None:
        """
        Save all channel categories to the database.

        This command processes all channel categories from all guilds the bot is in,
        adding new categories to the categories table.

        Args:
            ctx: The command context

        Raises:
            DatabaseError: If database operations fail
            QueryError: If there's an issue with SQL queries
        """
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass  # Message already deleted
        except discord.Forbidden:
            self.logger.warning("No permission to delete command message")

        guilds_processed = 0
        categories_processed = 0
        categories_added = 0
        categories_updated = 0

        try:
            for guild in self.bot.guilds:
                self.logger.info(
                    f"Processing categories for guild: {guild.name} ({guild.id})"
                )
                guild_categories_processed = 0

                for category in guild.categories:
                    try:
                        result = await self.bot.db.execute(
                            "INSERT INTO "
                            "categories(id, name, created_at, guild_id, position, is_nsfw) "
                            "VALUES ($1,$2,$3,$4,$5,$6) "
                            "ON CONFLICT (id) DO UPDATE SET "
                            "name = $2, position = $5, is_nsfw = $6",
                            category.id,
                            category.name,
                            category.created_at.replace(tzinfo=None),
                            category.guild.id,
                            category.position,
                            category.is_nsfw(),
                        )

                        if "INSERT" in result:
                            categories_added += 1
                            self.logger.debug(
                                f"Added new category: {category.name} ({category.id})"
                            )
                        else:
                            categories_updated += 1
                            self.logger.debug(
                                f"Updated existing category: {category.name} ({category.id})"
                            )

                    except asyncpg.PostgresError as e:
                        self.logger.error(
                            f"Failed to save category '{category.name}' ({category.id}) in guild {guild.name}: {e}"
                        )
                        # Continue processing other categories instead of failing completely
                        continue

                    guild_categories_processed += 1
                    categories_processed += 1

                self.logger.info(
                    f"Processed {guild_categories_processed} categories from guild {guild.name}"
                )
                guilds_processed += 1

        except Exception as e:
            raise QueryError(f"Unexpected error during category saving process") from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **Category saving completed successfully!**\n"
            f"**Guilds processed:** {guilds_processed}\n"
            f"**Categories processed:** {categories_processed}\n"
            f"**New categories added:** {categories_added}\n"
            f"**Existing categories updated:** {categories_updated}"
        )

    @commands.command(name="save_threads", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_threads(self, ctx: "Context") -> None:
        """
        Save all threads to the database.

        This command processes all threads from all guilds the bot is in,
        adding new threads to the threads table.

        Args:
            ctx: The command context

        Raises:
            DatabaseError: If database operations fail
            QueryError: If there's an issue with SQL queries
        """
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass  # Message already deleted
        except discord.Forbidden:
            self.logger.warning("No permission to delete command message")

        guilds_processed = 0
        threads_processed = 0
        threads_added = 0
        threads_updated = 0

        try:
            for guild in self.bot.guilds:
                self.logger.info(
                    f"Processing threads for guild: {guild.name} ({guild.id})"
                )
                guild_threads_processed = 0

                for thread in guild.threads:
                    try:
                        result = await self.bot.db.execute(
                            "INSERT INTO "
                            "threads(id, guild_id, parent_id, owner_id, slowmode_delay, archived, locked, archiver_id, auto_archive_duration, is_private, name, deleted) "
                            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) "
                            "ON CONFLICT (id) DO UPDATE SET "
                            "slowmode_delay = $5, archived = $6, locked = $7, archiver_id = $8, auto_archive_duration = $9, name = $11, deleted = $12",
                            thread.id,
                            thread.guild.id,
                            thread.parent_id,
                            thread.owner_id,
                            thread.slowmode_delay,
                            thread.archived,
                            thread.locked,
                            thread.archiver_id,
                            thread.auto_archive_duration,
                            thread.is_private(),
                            thread.name,
                            False,
                        )

                        if "INSERT" in result:
                            threads_added += 1
                            self.logger.debug(
                                f"Added new thread: {thread.name} ({thread.id})"
                            )
                        else:
                            threads_updated += 1
                            self.logger.debug(
                                f"Updated existing thread: {thread.name} ({thread.id})"
                            )

                    except asyncpg.PostgresError as e:
                        self.logger.error(
                            f"Failed to save thread '{thread.name}' ({thread.id}) in guild {guild.name}: {e}"
                        )
                        # Continue processing other threads instead of failing completely
                        continue

                    guild_threads_processed += 1
                    threads_processed += 1

                self.logger.info(
                    f"Processed {guild_threads_processed} threads from guild {guild.name}"
                )
                guilds_processed += 1

        except Exception as e:
            raise QueryError(f"Unexpected error during thread saving process") from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **Thread saving completed successfully!**\n"
            f"**Guilds processed:** {guilds_processed}\n"
            f"**Threads processed:** {threads_processed}\n"
            f"**New threads added:** {threads_added}\n"
            f"**Existing threads updated:** {threads_updated}"
        )

    @commands.command(name="save", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save(self, ctx: "Context") -> None:
        """
        Perform a comprehensive save of all message history from accessible channels and threads.

        This is a long-running command that processes all guilds, channels, and threads
        the bot has access to, saving message history to the database.

        Args:
            ctx: The command context

        Raises:
            DatabaseError: If database operations fail
            QueryError: If there's an issue with SQL queries
            ValidationError: If Discord API operations fail
        """
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass  # Message already deleted
        except discord.Forbidden:
            self.logger.warning("No permission to delete command message")

        # Initialize progress tracking
        start_time = datetime.now()
        total_guilds = len(self.bot.guilds)
        guilds_processed = 0
        total_channels_processed = 0
        total_threads_processed = 0
        total_messages_saved = 0
        errors_encountered = 0

        self.logger.info(
            f"Starting comprehensive save operation for {total_guilds} guilds"
        )

        # Send initial progress message
        progress_msg = await ctx.send(
            f"🔄 **Starting comprehensive message save operation**\n"
            f"**Guilds to process:** {total_guilds}\n"
            f"**Started at:** {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"*This may take a very long time. Progress updates will be provided...*"
        )

        try:
            for guild_index, guild in enumerate(self.bot.guilds, 1):
                guild_start_time = datetime.now()
                guild_channels_processed = 0
                guild_threads_processed = 0
                guild_messages_saved = 0

                self.logger.info(
                    f"Processing guild {guild_index}/{total_guilds}: {guild.name} ({guild.id})"
                )

                try:
                    # Get all text channels with read permissions
                    accessible_channels = [
                        channel
                        for channel in guild.text_channels
                        if channel.permissions_for(
                            channel.guild.me
                        ).read_message_history
                    ]

                    if not accessible_channels:
                        self.logger.info(
                            f"No accessible channels found in guild {guild.name}"
                        )
                    else:
                        # Process channels and save messages
                        for channel in accessible_channels:
                            try:
                                self.logger.debug(
                                    f"Processing channel: {channel.name} ({channel.id})"
                                )

                                # Get last message timestamp from database
                                last_message_time = await self.bot.db.fetchval(
                                    "SELECT MAX(created_at) FROM messages WHERE channel_id = $1",
                                    channel.id,
                                )

                                # Set after parameter for history iteration
                                after = (
                                    last_message_time
                                    if last_message_time
                                    else datetime.strptime("2015-01-01", "%Y-%m-%d")
                                )

                                # Process messages in batches
                                async for message in channel.history(
                                    limit=None, after=after, oldest_first=True
                                ):
                                    try:
                                        await save_message(self.bot, message)
                                        guild_messages_saved += 1
                                        total_messages_saved += 1
                                    except Exception as e:
                                        self.logger.error(
                                            f"Error saving message {message.id}: {e}"
                                        )
                                        errors_encountered += 1

                                guild_channels_processed += 1
                                total_channels_processed += 1

                            except Exception as e:
                                self.logger.error(
                                    f"Error processing channel {channel.name}: {e}"
                                )
                                errors_encountered += 1

                    guilds_processed += 1

                    # Update progress every 5 guilds
                    if guild_index % 5 == 0 or guild_index == total_guilds:
                        elapsed_time = datetime.now() - start_time
                        try:
                            await progress_msg.edit(
                                content=f"🔄 **Message save operation in progress**\n"
                                f"**Guilds processed:** {guilds_processed}/{total_guilds}\n"
                                f"**Channels processed:** {total_channels_processed}\n"
                                f"**Messages saved:** {total_messages_saved:,}\n"
                                f"**Errors encountered:** {errors_encountered}\n"
                                f"**Elapsed time:** {str(elapsed_time).split('.')[0]}\n"
                                f"**Current guild:** {guild.name}"
                            )
                        except discord.HTTPException:
                            # If we can't edit the message, continue anyway
                            pass

                except Exception as e:
                    self.logger.error(f"Error processing guild {guild.name}: {e}")
                    errors_encountered += 1

        except Exception as e:
            raise QueryError(
                f"Unexpected error during comprehensive save operation"
            ) from e

        # Send completion message
        end_time = datetime.now()
        total_time = end_time - start_time

        try:
            await progress_msg.edit(
                content=f"✅ **Comprehensive save operation completed!**\n"
                f"**Guilds processed:** {guilds_processed}/{total_guilds}\n"
                f"**Channels processed:** {total_channels_processed}\n"
                f"**Threads processed:** {total_threads_processed}\n"
                f"**Messages saved:** {total_messages_saved:,}\n"
                f"**Errors encountered:** {errors_encountered}\n"
                f"**Total time:** {str(total_time).split('.')[0]}\n"
                f"**Completed at:** {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
        except discord.HTTPException:
            # Send a new message if editing fails
            await ctx.send(
                f"✅ **Comprehensive save operation completed!**\n"
                f"**Messages saved:** {total_messages_saved:,}\n"
                f"**Total time:** {str(total_time).split('.')[0]}"
            )

        # Notify bot owner of completion
        try:
            owner = self.bot.get_user(self.bot.owner_id)
            if owner:
                await owner.send(
                    f"🎉 **Comprehensive save operation completed!**\n"
                    f"**Server:** {ctx.guild.name if ctx.guild else 'DM'}\n"
                    f"**Guilds processed:** {guilds_processed}/{total_guilds}\n"
                    f"**Channels processed:** {total_channels_processed}\n"
                    f"**Messages saved:** {total_messages_saved:,}\n"
                    f"**Total time:** {str(total_time).split('.')[0]}\n"
                    f"**Errors:** {errors_encountered}"
                )
                self.logger.info("Completion notification sent to bot owner")
            else:
                self.logger.warning(
                    "Could not find bot owner to send completion notification"
                )
        except Exception as e:
            self.logger.error(f"Failed to send completion notification to owner: {e}")

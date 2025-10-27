"""Command methods for the stats system.

This module contains all the command methods for saving different types of data
to the database. These commands are typically owner-only and used for data management.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import asyncpg
import discord
from discord.ext import commands

from utils.error_handling import handle_command_errors
from utils.exceptions import DatabaseError, QueryError

from .stats_utils import perform_comprehensive_save, save_message

if TYPE_CHECKING:
    from discord.ext.commands import Context


class StatsCommandsMixin:
    """Mixin class containing all stats-related command methods."""

    @commands.command(name="save_users", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_users(self, ctx: "Context") -> None:
        """Save all guild members to the database.

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
            raise QueryError("Unexpected error during user saving process") from e

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
        """Save all guild information to the database.

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
            raise QueryError("Unexpected error during server saving process") from e

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
        """Save all text channels to the database.

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
            raise QueryError("Unexpected error during channel saving process") from e

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
        """Save all channel categories to the database.

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
            raise QueryError("Unexpected error during category saving process") from e

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
        """Save all threads to the database.

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
            raise QueryError("Unexpected error during thread saving process") from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **Thread saving completed successfully!**\n"
            f"**Guilds processed:** {guilds_processed}\n"
            f"**Threads processed:** {threads_processed}\n"
            f"**New threads added:** {threads_added}\n"
            f"**Existing threads updated:** {threads_updated}"
        )

    @commands.command(name="save_emotes", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_emotes(self, ctx: "Context") -> None:
        """Save all custom emotes to the database.

        This command processes all custom emotes from all guilds the bot is in,
        adding new emotes to the emotes table.

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
        emotes_processed = 0
        emotes_added = 0
        emotes_updated = 0

        try:
            for guild in self.bot.guilds:
                self.logger.info(
                    f"Processing emotes for guild: {guild.name} ({guild.id})"
                )
                guild_emotes_processed = 0

                for emotes in guild.emojis:
                    try:
                        emote = self.bot.get_emoji(emotes.id)
                        if emote is None:
                            self.logger.warning(
                                f"Could not retrieve emote {emotes.id} from guild {guild.name}"
                            )
                            continue

                        result = await self.bot.db.execute(
                            """ 
                            INSERT INTO emotes(guild_id, emote_id, name, animated, managed) 
                            VALUES ($1,$2,$3,$4,$5)
                            ON CONFLICT (emote_id) 
                            DO UPDATE SET name = $3, animated = $4, managed = $5 
                            WHERE emotes.name != $3 OR emotes.animated != $4 OR emotes.managed != $5
                            """,
                            guild.id,
                            emote.id,
                            emote.name,
                            emote.animated,
                            emote.managed,
                        )

                        if "INSERT" in result:
                            emotes_added += 1
                            self.logger.debug(
                                f"Added new emote: {emote.name} ({emote.id})"
                            )
                        else:
                            emotes_updated += 1
                            self.logger.debug(
                                f"Updated existing emote: {emote.name} ({emote.id})"
                            )

                    except asyncpg.PostgresError as e:
                        self.logger.error(
                            f"Failed to save emote {emotes.id} in guild {guild.name}: {e}"
                        )
                        # Continue processing other emotes instead of failing completely
                        continue

                    guild_emotes_processed += 1
                    emotes_processed += 1

                self.logger.info(
                    f"Processed {guild_emotes_processed} emotes from guild {guild.name}"
                )
                guilds_processed += 1

        except Exception as e:
            raise QueryError("Unexpected error during emote saving process") from e

        # Send comprehensive completion message
        completion_message = (
            f"✅ **Emote saving completed successfully!**\n"
            f"**Guilds processed:** {guilds_processed}\n"
            f"**Emotes processed:** {emotes_processed}\n"
            f"**New emotes added:** {emotes_added}\n"
            f"**Existing emotes updated:** {emotes_updated}"
        )

        await ctx.send(completion_message)

        # Also notify the owner if this is part of a larger save operation
        try:
            owner = self.bot.get_user(self.bot.owner_id)
            if owner is not None:
                await owner.send(
                    f"Emote saving completed: {emotes_processed} emotes processed from {guilds_processed} guilds"
                )
            else:
                self.logger.warning(
                    "Could not find bot owner to send completion notification"
                )
        except Exception as e:
            self.logger.error(f"Failed to send completion notification to owner: {e}")

    @commands.command(name="save_roles", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_roles(self, ctx: "Context") -> None:
        """Save all roles and role memberships to the database.

        This command processes all roles from all guilds the bot is in,
        adding new roles to the roles table and updating role memberships.

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
        roles_processed = 0
        roles_added = 0
        roles_updated = 0
        memberships_processed = 0
        memberships_added = 0

        try:
            for guild in self.bot.guilds:
                self.logger.info(
                    f"Processing roles for guild: {guild.name} ({guild.id})"
                )
                guild_roles_processed = 0
                guild_memberships_processed = 0

                for role in guild.roles:
                    if role.is_default():
                        self.logger.debug(
                            f"Skipping default role in guild {guild.name}"
                        )
                        continue

                    try:
                        # Save or update the role
                        result = await self.bot.db.execute(
                            "INSERT INTO "
                            "roles(id, name, color, created_at, hoisted, managed, position, guild_id) "
                            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) "
                            "ON CONFLICT (id) DO UPDATE SET "
                            "name = $2, color = $3, hoisted = $5, managed = $6, position = $7",
                            role.id,
                            role.name,
                            str(role.color),
                            role.created_at.replace(tzinfo=None),
                            role.hoist,
                            role.managed,
                            role.position,
                            guild.id,
                        )

                        if "INSERT" in result:
                            roles_added += 1
                            self.logger.debug(
                                f"Added new role: {role.name} ({role.id})"
                            )
                        else:
                            roles_updated += 1
                            self.logger.debug(
                                f"Updated existing role: {role.name} ({role.id})"
                            )

                    except asyncpg.PostgresError as e:
                        self.logger.error(
                            f"Failed to save role '{role.name}' ({role.id}) in guild {guild.name}: {e}"
                        )
                        # Continue processing other roles instead of failing completely
                        continue

                    guild_roles_processed += 1
                    roles_processed += 1

                    # Process role memberships
                    for member in role.members:
                        try:
                            await self.bot.db.execute(
                                "INSERT INTO role_membership(user_id, role_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
                                member.id,
                                role.id,
                            )
                            memberships_added += 1
                            guild_memberships_processed += 1
                            memberships_processed += 1
                            self.logger.debug(
                                f"Added membership: {member.name} -> {role.name}"
                            )

                        except asyncpg.PostgresError as e:
                            self.logger.error(
                                f"Failed to save role membership for {member.name} in role {role.name}: {e}"
                            )
                            # Continue processing other memberships
                            continue

                self.logger.info(
                    f"Processed {guild_roles_processed} roles and {guild_memberships_processed} memberships from guild {guild.name}"
                )
                guilds_processed += 1

        except Exception as e:
            raise QueryError("Unexpected error during role saving process") from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **Role saving completed successfully!**\n"
            f"**Guilds processed:** {guilds_processed}\n"
            f"**Roles processed:** {roles_processed}\n"
            f"**New roles added:** {roles_added}\n"
            f"**Existing roles updated:** {roles_updated}\n"
            f"**Role memberships processed:** {memberships_processed}\n"
            f"**New memberships added:** {memberships_added}"
        )

    @commands.command(name="update_role_color", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def update_role_color(self, ctx: "Context") -> None:
        """Update role colors in the database.

        This command updates the color field for all roles in the database
        to match their current Discord color values.

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
        roles_processed = 0
        roles_updated = 0

        try:
            for guild in self.bot.guilds:
                self.logger.info(
                    f"Updating role colors for guild: {guild.name} ({guild.id})"
                )
                guild_roles_processed = 0

                for role in guild.roles:
                    if role.is_default():
                        self.logger.debug(
                            f"Skipping default role in guild {guild.name}"
                        )
                        continue

                    try:
                        result = await self.bot.db.execute(
                            "UPDATE roles SET color = $1 WHERE id = $2",
                            str(role.color),
                            role.id,
                        )

                        # Check if any rows were updated
                        if "UPDATE" in result and "0" not in result:
                            roles_updated += 1
                            self.logger.debug(
                                f"Updated color for role: {role.name} ({role.id}) to {role.color}"
                            )
                        else:
                            self.logger.debug(
                                f"No update needed for role: {role.name} ({role.id})"
                            )

                    except asyncpg.PostgresError as e:
                        self.logger.error(
                            f"Failed to update color for role '{role.name}' ({role.id}) in guild {guild.name}: {e}"
                        )
                        # Continue processing other roles instead of failing completely
                        continue

                    guild_roles_processed += 1
                    roles_processed += 1

                self.logger.info(
                    f"Processed {guild_roles_processed} role colors from guild {guild.name}"
                )
                guilds_processed += 1

        except Exception as e:
            raise QueryError("Unexpected error during role color update process") from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **Role color update completed successfully!**\n"
            f"**Guilds processed:** {guilds_processed}\n"
            f"**Roles processed:** {roles_processed}\n"
            f"**Role colors updated:** {roles_updated}"
        )

    @commands.command(name="save_users_from_join_leave", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_users_from_join_leave(self, ctx: "Context") -> None:
        """Save users from join/leave records to the users table.

        This command processes users from the join_leave table and adds them
        to the users table if they don't already exist.

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

        users_processed = 0
        users_added = 0

        try:
            # Fetch users from join_leave table
            jn_users = await self.bot.db.fetch(
                "SELECT user_id, created_at, user_name FROM join_leave"
            )

            if not jn_users:
                await ctx.send("ℹ️ No users found in join_leave table to process.")
                return

            self.logger.info(f"Processing {len(jn_users)} users from join_leave table")

            for user in jn_users:
                try:
                    result = await self.bot.db.execute(
                        "INSERT INTO "
                        "users(user_id, created_at, bot, username) "
                        "VALUES($1,$2,$3,$4) "
                        "ON CONFLICT (user_id) DO NOTHING",
                        user["user_id"],
                        user["created_at"],
                        False,  # Assume not bot for join/leave records
                        user["user_name"],
                    )

                    if "INSERT" in result:
                        users_added += 1
                        self.logger.debug(
                            f"Added user from join_leave: {user['user_name']} ({user['user_id']})"
                        )
                    else:
                        self.logger.debug(
                            f"User already exists: {user['user_name']} ({user['user_id']})"
                        )

                except asyncpg.PostgresError as e:
                    self.logger.error(
                        f"Failed to save user {user['user_id']} from join_leave: {e}"
                    )
                    # Continue processing other users instead of failing completely
                    continue

                users_processed += 1

        except asyncpg.PostgresError as e:
            raise DatabaseError("Failed to fetch users from join_leave table") from e
        except Exception as e:
            raise QueryError(
                "Unexpected error during join_leave user saving process"
            ) from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **Join/leave user saving completed successfully!**\n"
            f"**Users processed:** {users_processed}\n"
            f"**New users added:** {users_added}\n"
            f"**Existing users skipped:** {users_processed - users_added}"
        )

    @commands.command(name="save_channels_from_messages", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_users_from_messages(self, ctx: "Context") -> None:
        """Save users from message reactions to the users table.

        This command finds reactions to messages that aren't in the messages table
        and attempts to fetch those messages to save user information.

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

        messages_processed = 0
        users_added = 0
        messages_not_found = 0

        try:
            # Fetch message IDs from reactions that don't have corresponding messages
            missing_messages = await self.bot.db.fetch(
                """SELECT reactions.message_id FROM reactions
                   LEFT JOIN messages m on reactions.message_id = m.message_id
                   WHERE m.message_id IS NULL
                   GROUP BY reactions.message_id"""
            )

            if not missing_messages:
                await ctx.send(
                    "ℹ️ No missing messages found in reactions table to process."
                )
                return

            self.logger.info(
                f"Processing {len(missing_messages)} missing messages from reactions"
            )

            for message_record in missing_messages:
                message_id = message_record["message_id"]

                try:
                    # Try to fetch the message from Discord
                    message = await self.bot.get_message(message_id)

                    if message is None:
                        # Try alternative method if get_message fails
                        for guild in self.bot.guilds:
                            for channel in guild.text_channels:
                                try:
                                    message = await channel.fetch_message(message_id)
                                    break
                                except (discord.NotFound, discord.Forbidden):
                                    continue
                            if message:
                                break

                    if message:
                        # Save the user information from the message
                        try:
                            await self.bot.db.execute(
                                "INSERT INTO users(user_id, username, bot) VALUES($1,$2,$3) ON CONFLICT (user_id) DO NOTHING",
                                message.author.id,
                                message.author.name,
                                message.author.bot,
                            )
                            users_added += 1
                            self.logger.debug(
                                f"Added user from message {message_id}: {message.author.name} ({message.author.id})"
                            )

                        except asyncpg.PostgresError as e:
                            self.logger.error(
                                f"Failed to save user from message {message_id}: {e}"
                            )
                            continue
                    else:
                        messages_not_found += 1
                        self.logger.debug(f"Could not fetch message {message_id}")

                except discord.NotFound:
                    messages_not_found += 1
                    self.logger.debug(f"Message {message_id} not found")
                except discord.Forbidden:
                    self.logger.warning(f"No permission to access message {message_id}")
                    continue
                except Exception as e:
                    self.logger.error(
                        f"Unexpected error processing message {message_id}: {e}"
                    )
                    continue

                messages_processed += 1

        except asyncpg.PostgresError as e:
            raise DatabaseError(
                "Failed to fetch missing messages from reactions table"
            ) from e
        except Exception as e:
            raise QueryError(
                "Unexpected error during message user saving process"
            ) from e

        # Send comprehensive completion message
        await ctx.send(
            f"✅ **Message user saving completed successfully!**\n"
            f"**Messages processed:** {messages_processed}\n"
            f"**Users added:** {users_added}\n"
            f"**Messages not found:** {messages_not_found}"
        )

    @commands.command(name="save", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save(self, ctx: "Context") -> None:
        """Perform a comprehensive save of all message history from accessible channels and threads.

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

        # Send initial progress message
        start_time = datetime.now()
        total_guilds = len(self.bot.guilds)
        progress_msg = await ctx.send(
            f"🔄 **Starting comprehensive message save operation**\n"
            f"**Guilds to process:** {total_guilds}\n"
            f"**Started at:** {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"*This may take a very long time. Progress updates will be provided...*"
        )

        # Define progress callback for UI updates
        async def progress_callback(
            guilds_processed,
            total_guilds,
            channels_processed,
            messages_saved,
            errors_encountered,
            elapsed_time,
            current_guild_name,
        ) -> None:
            try:
                await progress_msg.edit(
                    content=f"🔄 **Message save operation in progress**\n"
                    f"**Guilds processed:** {guilds_processed}/{total_guilds}\n"
                    f"**Channels processed:** {channels_processed}\n"
                    f"**Messages saved:** {messages_saved:,}\n"
                    f"**Errors encountered:** {errors_encountered}\n"
                    f"**Elapsed time:** {str(elapsed_time).split('.')[0]}\n"
                    f"**Current guild:** {current_guild_name}"
                )
            except discord.HTTPException:
                # If we can't edit the message, continue anyway
                pass

        # Define completion callback for final UI update and owner notification
        async def completion_callback(results) -> None:
            try:
                await progress_msg.edit(
                    content=f"✅ **Comprehensive save operation completed!**\n"
                    f"**Guilds processed:** {results['guilds_processed']}/{results['total_guilds']}\n"
                    f"**Channels processed:** {results['channels_processed']}\n"
                    f"**Threads processed:** {results['threads_processed']}\n"
                    f"**Messages saved:** {results['messages_saved']:,}\n"
                    f"**Errors encountered:** {results['errors_encountered']}\n"
                    f"**Total time:** {str(results['total_time']).split('.')[0]}\n"
                    f"**Completed at:** {results['end_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )
            except discord.HTTPException:
                # Send a new message if editing fails
                await ctx.send(
                    f"✅ **Comprehensive save operation completed!**\n"
                    f"**Messages saved:** {results['messages_saved']:,}\n"
                    f"**Total time:** {str(results['total_time']).split('.')[0]}"
                )

            # Notify bot owner of completion
            try:
                owner = self.bot.get_user(self.bot.owner_id)
                if owner:
                    await owner.send(
                        f"🎉 **Comprehensive save operation completed!**\n"
                        f"**Server:** {ctx.guild.name if ctx.guild else 'DM'}\n"
                        f"**Guilds processed:** {results['guilds_processed']}/{results['total_guilds']}\n"
                        f"**Channels processed:** {results['channels_processed']}\n"
                        f"**Messages saved:** {results['messages_saved']:,}\n"
                        f"**Total time:** {str(results['total_time']).split('.')[0]}\n"
                        f"**Errors:** {results['errors_encountered']}"
                    )
                    self.logger.info("Completion notification sent to bot owner")
                else:
                    self.logger.warning(
                        "Could not find bot owner to send completion notification"
                    )
            except Exception as e:
                self.logger.error(
                    f"Failed to send completion notification to owner: {e}"
                )

        # Call the standalone save function with callbacks
        try:
            await perform_comprehensive_save(
                self.bot,
                progress_callback=progress_callback,
                completion_callback=completion_callback,
            )
        except Exception as e:
            raise QueryError(
                "Unexpected error during comprehensive save operation"
            ) from e

    @commands.command(name="save_recent", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_recent(self, ctx: "Context", days: int = 30) -> None:
        """Fetch all messages from the last x days and ensure they are in the database.

        This command fetches messages from the specified number of days and saves any
        missing messages to fill gaps in the message history.

        Args:
            ctx: The command context
            days: Number of days to look back (default: 30)

        Raises:
            DatabaseError: If database operations fail
            QueryError: If there's an issue with SQL queries
            ValidationError: If Discord API operations fail
        """
        if days <= 0:
            await ctx.send("❌ Days must be a positive number.")
            return

        if days > 365:
            await ctx.send("❌ Days cannot exceed 365 for safety reasons.")
            return

        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass  # Message already deleted
        except discord.Forbidden:
            self.logger.warning("No permission to delete command message")

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Send initial progress message
        total_guilds = len(self.bot.guilds)
        progress_msg = await ctx.send(
            f"🔄 **Starting recent message save operation**\n"
            f"**Date range:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({days} days)\n"
            f"**Guilds to process:** {total_guilds}\n"
            f"**Started at:** {end_date.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"*Checking for message gaps and filling them...*"
        )

        # Initialize counters
        guilds_processed = 0
        channels_processed = 0
        messages_saved = 0
        errors_encountered = 0

        try:
            for guild in self.bot.guilds:
                datetime.now()
                self.logger.info(f"Processing guild: {guild.name} ({guild.id})")

                try:
                    # Get all text channels with read permissions
                    accessible_channels = [
                        channel
                        for channel in guild.text_channels
                        if channel.permissions_for(guild.me).read_message_history
                    ]

                    for channel in accessible_channels:
                        try:
                            self.logger.debug(
                                f"Processing channel: {channel.name} ({channel.id})"
                            )

                            # Get existing message IDs from database for this channel and date range
                            existing_message_ids = set()
                            existing_messages = await self.bot.db.fetch(
                                """
                                SELECT message_id FROM messages 
                                WHERE channel_id = $1 
                                AND created_at >= $2 
                                AND created_at <= $3
                                """,
                                channel.id,
                                start_date,
                                end_date,
                            )
                            existing_message_ids = {
                                row["message_id"] for row in existing_messages
                            }

                            # Fetch messages from Discord for the date range
                            discord_messages = []
                            async for message in channel.history(
                                limit=None,
                                after=start_date,
                                before=end_date,
                                oldest_first=True,
                            ):
                                discord_messages.append(message)

                            # Find missing messages (exist in Discord but not in database)
                            missing_messages = [
                                msg
                                for msg in discord_messages
                                if msg.id not in existing_message_ids
                            ]

                            # Save missing messages
                            for message in missing_messages:
                                try:
                                    await save_message(self.bot, message)
                                    messages_saved += 1
                                except Exception as e:
                                    self.logger.error(
                                        f"Error saving message {message.id}: {e}"
                                    )
                                    errors_encountered += 1

                            channels_processed += 1

                            # Update progress every 10 channels
                            if channels_processed % 10 == 0:
                                try:
                                    elapsed_time = datetime.now() - end_date
                                    await progress_msg.edit(
                                        content=f"🔄 **Recent message save in progress**\n"
                                        f"**Date range:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({days} days)\n"
                                        f"**Guilds processed:** {guilds_processed}/{total_guilds}\n"
                                        f"**Channels processed:** {channels_processed}\n"
                                        f"**Messages saved:** {messages_saved:,}\n"
                                        f"**Errors encountered:** {errors_encountered}\n"
                                        f"**Elapsed time:** {str(elapsed_time).split('.')[0]}\n"
                                        f"**Current guild:** {guild.name}"
                                    )
                                except discord.HTTPException:
                                    pass  # Continue if we can't edit the message

                        except Exception as e:
                            self.logger.error(
                                f"Error processing channel {channel.name}: {e}"
                            )
                            errors_encountered += 1

                    guilds_processed += 1

                except Exception as e:
                    self.logger.error(f"Error processing guild {guild.name}: {e}")
                    errors_encountered += 1
                    guilds_processed += 1

            # Final completion message
            total_time = datetime.now() - end_date
            await progress_msg.edit(
                content=f"✅ **Recent message save completed!**\n"
                f"**Date range:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({days} days)\n"
                f"**Guilds processed:** {guilds_processed}/{total_guilds}\n"
                f"**Channels processed:** {channels_processed}\n"
                f"**Messages saved:** {messages_saved:,}\n"
                f"**Errors encountered:** {errors_encountered}\n"
                f"**Total time:** {str(total_time).split('.')[0]}\n"
                f"**Completed at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )

            # Notify bot owner of completion
            try:
                owner = self.bot.get_user(self.bot.owner_id)
                if owner:
                    await owner.send(
                        f"🎉 **Recent message save completed!**\n"
                        f"**Server:** {ctx.guild.name if ctx.guild else 'DM'}\n"
                        f"**Date range:** {days} days\n"
                        f"**Channels processed:** {channels_processed}\n"
                        f"**Messages saved:** {messages_saved:,}\n"
                        f"**Total time:** {str(total_time).split('.')[0]}\n"
                        f"**Errors:** {errors_encountered}"
                    )
                    self.logger.info("Completion notification sent to bot owner")
            except Exception as e:
                self.logger.error(
                    f"Failed to send completion notification to owner: {e}"
                )

        except Exception as e:
            raise QueryError(
                "Unexpected error during recent message save operation"
            ) from e

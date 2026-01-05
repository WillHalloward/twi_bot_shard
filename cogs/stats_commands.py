"""Command and query methods for the stats system.

This module contains:
- Owner commands for data management (StatsCommandsMixin)
- User-facing query commands (StatsQueriesMixin)
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

from utils.error_handling import handle_command_errors, handle_interaction_errors
from utils.exceptions import DatabaseError, QueryError, ValidationError

from .stats_listeners import perform_comprehensive_save, save_message

if TYPE_CHECKING:
    from discord import Interaction
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


class StatsQueriesMixin:
    """Mixin class containing all stats-related query commands."""

    @app_commands.command(
        name="messagecount",
        description="Retrieve message count from a channel in the last x hours",
    )
    @handle_interaction_errors
    async def message_count(
        self, interaction: "Interaction", channel: discord.TextChannel, hours: int
    ) -> None:
        """Retrieve message count from a specific channel within a time range.

        Args:
            interaction: The Discord interaction object
            channel: The text channel to count messages from
            hours: Number of hours to look back (must be positive)

        Raises:
            ValidationError: If the hours parameter is invalid
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        # Validate hours parameter
        if hours <= 0:
            raise ValidationError(
                field="hours", message="Hours must be a positive number"
            )

        if hours > 8760:  # More than a year
            raise ValidationError(
                field="hours", message="Hours cannot exceed 8760 (1 year)"
            )

        # Calculate the time threshold
        d_time = datetime.now() - timedelta(hours=hours)

        try:
            # Query the database for message count
            results = await self.bot.db.fetchrow(
                "SELECT count(*) as total FROM messages WHERE created_at > $1 AND channel_id = $2",
                d_time,
                channel.id,
            )

            if results is None:
                raise QueryError("Database query returned no results")

            message_count = results["total"]

            # Log the query for debugging
            self.logger.info(
                f"Message count query: {message_count} messages in {channel.name} ({channel.id}) over last {hours} hours"
            )

            # Create a formatted response
            embed = discord.Embed(
                title="📊 Message Count Statistics",
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            embed.add_field(name="Channel", value=channel.mention, inline=True)

            embed.add_field(
                name="Time Period",
                value=f"Last {hours} hour{'s' if hours != 1 else ''}",
                inline=True,
            )

            embed.add_field(
                name="Message Count",
                value=f"**{message_count:,}** messages",
                inline=True,
            )

            # Calculate average messages per hour
            avg_per_hour = message_count / hours if hours > 0 else 0
            embed.add_field(
                name="Average per Hour",
                value=f"**{avg_per_hour:.1f}** messages/hour",
                inline=True,
            )

            # Add additional context
            embed.add_field(
                name="Query Time",
                value=f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during message count query: {e}") from e

    stats = app_commands.Group(name="stats", description="Statistics commands")

    @stats.command(
        name="channel",
        description="Get comprehensive statistics for a channel",
    )
    @handle_interaction_errors
    async def channel_stats(
        self, interaction: "Interaction", channel: discord.TextChannel, days: int = 7
    ) -> None:
        """Get comprehensive statistics for a specific channel.

        Args:
            interaction: The Discord interaction object
            channel: The text channel to get statistics for
            days: Number of days to look back (default: 7, max: 365)

        Raises:
            ValidationError: If the days parameter is invalid
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        # Validate days parameter
        if days <= 0:
            raise ValidationError(
                field="days", message="Days must be a positive number"
            )

        if days > 365:  # More than a year
            raise ValidationError(
                field="days", message="Days cannot exceed 365 (1 year)"
            )

        # Calculate the time threshold
        d_time = datetime.now() - timedelta(days=days)

        try:
            # Query for comprehensive channel statistics
            stats_query = """
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as unique_users,
                AVG(LENGTH(content)) as avg_message_length,
                COUNT(*) FILTER (WHERE attachments.id IS NOT NULL) as messages_with_attachments,
                COUNT(*) FILTER (WHERE embeds.id IS NOT NULL) as messages_with_embeds
            FROM messages
            LEFT JOIN attachments ON messages.message_id = attachments.message_id
            LEFT JOIN embeds ON messages.message_id = embeds.message_id
            WHERE messages.created_at > $1 AND messages.channel_id = $2
            """

            results = await self.bot.db.fetchrow(stats_query, d_time, channel.id)

            if results is None:
                raise QueryError("Database query returned no results")

            # Query for top users in the channel
            top_users_query = """
            SELECT user_id, COUNT(*) as message_count
            FROM messages
            WHERE created_at > $1 AND channel_id = $2
            GROUP BY user_id
            ORDER BY message_count DESC
            LIMIT 5
            """

            top_users = await self.bot.db.fetch(top_users_query, d_time, channel.id)

            # Create a formatted response
            embed = discord.Embed(
                title=f"📈 Channel Statistics: {channel.name}",
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )

            # Basic statistics
            embed.add_field(
                name="📝 Total Messages",
                value=f"**{results['total_messages']:,}**",
                inline=True,
            )

            embed.add_field(
                name="👥 Unique Users",
                value=f"**{results['unique_users']:,}**",
                inline=True,
            )

            avg_length = results["avg_message_length"] or 0
            embed.add_field(
                name="📏 Avg Message Length",
                value=f"**{avg_length:.1f}** characters",
                inline=True,
            )

            embed.add_field(
                name="📎 Messages with Attachments",
                value=f"**{results['messages_with_attachments']:,}**",
                inline=True,
            )

            embed.add_field(
                name="🎨 Messages with Embeds",
                value=f"**{results['messages_with_embeds']:,}**",
                inline=True,
            )

            # Calculate activity rate
            messages_per_day = results["total_messages"] / days if days > 0 else 0
            embed.add_field(
                name="📊 Activity Rate",
                value=f"**{messages_per_day:.1f}** messages/day",
                inline=True,
            )

            # Top users section
            if top_users:
                top_users_text = ""
                for i, user_data in enumerate(top_users, 1):
                    user = self.bot.get_user(user_data["user_id"])
                    username = (
                        user.display_name if user else f"User {user_data['user_id']}"
                    )
                    top_users_text += (
                        f"{i}. {username}: {user_data['message_count']:,} messages\n"
                    )

                embed.add_field(
                    name="🏆 Top Contributors",
                    value=top_users_text,
                    inline=False,
                )

            embed.add_field(
                name="📅 Time Period",
                value=f"Last {days} day{'s' if days != 1 else ''}\n"
                f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during channel stats query: {e}") from e

    @stats.command(
        name="server",
        description="Get comprehensive statistics for the current server",
    )
    @handle_interaction_errors
    async def server_stats(self, interaction: "Interaction", days: int = 7) -> None:
        """Get comprehensive statistics for the current server.

        Args:
            interaction: The Discord interaction object
            days: Number of days to look back (default: 7, max: 365)

        Raises:
            ValidationError: If the days parameter is invalid
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!", ephemeral=True
            )
            return

        # Validate days parameter
        if days <= 0:
            raise ValidationError(
                field="days", message="Days must be a positive number"
            )

        if days > 365:  # More than a year
            raise ValidationError(
                field="days", message="Days cannot exceed 365 (1 year)"
            )

        # Calculate the time threshold
        d_time = datetime.now() - timedelta(days=days)

        try:
            # Query for comprehensive server statistics
            stats_query = """
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as active_users,
                COUNT(DISTINCT channel_id) as active_channels
            FROM messages
            WHERE created_at > $1 AND server_id = $2
            """

            results = await self.bot.db.fetchrow(
                stats_query, d_time, interaction.guild.id
            )

            # Query for member join/leave statistics
            member_stats_query = """
            SELECT
                COUNT(*) FILTER (WHERE date > $1 AND join_or_leave = 'join') as new_joins,
                COUNT(*) FILTER (WHERE date > $1 AND join_or_leave = 'leave') as leaves
            FROM join_leave
            WHERE server_id = $2
            """

            member_results = await self.bot.db.fetchrow(
                member_stats_query, d_time, interaction.guild.id
            )

            if results is None:
                raise QueryError("Database query returned no results")

            # Create a formatted response
            embed = discord.Embed(
                title=f"🏰 Server Statistics: {interaction.guild.name}",
                color=discord.Color.purple(),
                timestamp=datetime.now(),
            )

            # Basic statistics
            embed.add_field(
                name="📝 Total Messages",
                value=f"**{results['total_messages']:,}**",
                inline=True,
            )

            embed.add_field(
                name="👥 Active Users",
                value=f"**{results['active_users']:,}**",
                inline=True,
            )

            embed.add_field(
                name="📺 Active Channels",
                value=f"**{results['active_channels']:,}**",
                inline=True,
            )

            if member_results:
                embed.add_field(
                    name="📈 New Members",
                    value=f"**{member_results['new_joins'] or 0:,}**",
                    inline=True,
                )

                embed.add_field(
                    name="📉 Members Left",
                    value=f"**{member_results['leaves'] or 0:,}**",
                    inline=True,
                )

                net_growth = (member_results["new_joins"] or 0) - (
                    member_results["leaves"] or 0
                )
                embed.add_field(
                    name="📊 Net Growth",
                    value=f"**{net_growth:+,}**",
                    inline=True,
                )

            # Calculate activity rates
            messages_per_day = results["total_messages"] / days if days > 0 else 0
            embed.add_field(
                name="📈 Message Activity",
                value=f"**{messages_per_day:.1f}** messages/day",
                inline=True,
            )

            # Current server info
            embed.add_field(
                name="👑 Current Members",
                value=f"**{interaction.guild.member_count:,}**",
                inline=True,
            )

            embed.add_field(
                name="📅 Time Period",
                value=f"Last {days} day{'s' if days != 1 else ''}\n"
                f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during server stats query: {e}") from e

    @stats.command(
        name="user",
        description="Get comprehensive statistics for a user",
    )
    @handle_interaction_errors
    async def user_stats(
        self, interaction: "Interaction", user: discord.Member = None, days: int = 7
    ) -> None:
        """Get comprehensive statistics for a specific user.

        Args:
            interaction: The Discord interaction object
            user: The user to get statistics for (defaults to command user)
            days: Number of days to look back (default: 7, max: 365)

        Raises:
            ValidationError: If the days parameter is invalid
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!", ephemeral=True
            )
            return

        # Default to the command user if no user specified
        if user is None:
            user = interaction.user

        # Validate days parameter
        if days <= 0:
            raise ValidationError(
                field="days", message="Days must be a positive number"
            )

        if days > 365:  # More than a year
            raise ValidationError(
                field="days", message="Days cannot exceed 365 (1 year)"
            )

        # Calculate the time threshold
        d_time = datetime.now() - timedelta(days=days)

        try:
            # Query for comprehensive user statistics
            stats_query = """
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT channel_id) as active_channels,
                AVG(LENGTH(content)) as avg_message_length,
                COUNT(*) FILTER (WHERE attachments.id IS NOT NULL) as messages_with_attachments,
                COUNT(*) FILTER (WHERE embeds.id IS NOT NULL) as messages_with_embeds
            FROM messages
            LEFT JOIN attachments ON messages.message_id = attachments.message_id
            LEFT JOIN embeds ON messages.message_id = embeds.message_id
            WHERE messages.created_at > $1 AND messages.user_id = $2 AND messages.server_id = $3
            """

            results = await self.bot.db.fetchrow(
                stats_query, d_time, user.id, interaction.guild.id
            )

            if results is None:
                raise QueryError("Database query returned no results")

            # Query for top channels where user is active
            top_channels_query = """
            SELECT channel_id, COUNT(*) as message_count
            FROM messages
            WHERE created_at > $1 AND user_id = $2 AND server_id = $3
            GROUP BY channel_id
            ORDER BY message_count DESC
            LIMIT 5
            """

            top_channels = await self.bot.db.fetch(
                top_channels_query, d_time, user.id, interaction.guild.id
            )

            # Create a formatted response
            embed = discord.Embed(
                title=f"👤 User Statistics: {user.display_name}",
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            # Set user avatar as thumbnail
            if user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)

            # Basic statistics
            embed.add_field(
                name="📝 Total Messages",
                value=f"**{results['total_messages']:,}**",
                inline=True,
            )

            embed.add_field(
                name="📺 Active Channels",
                value=f"**{results['active_channels']:,}**",
                inline=True,
            )

            avg_length = results["avg_message_length"] or 0
            embed.add_field(
                name="📏 Avg Message Length",
                value=f"**{avg_length:.1f}** characters",
                inline=True,
            )

            embed.add_field(
                name="📎 Messages with Attachments",
                value=f"**{results['messages_with_attachments']:,}**",
                inline=True,
            )

            embed.add_field(
                name="🎨 Messages with Embeds",
                value=f"**{results['messages_with_embeds']:,}**",
                inline=True,
            )

            # Calculate activity rate
            messages_per_day = results["total_messages"] / days if days > 0 else 0
            embed.add_field(
                name="📊 Activity Rate",
                value=f"**{messages_per_day:.1f}** messages/day",
                inline=True,
            )

            # Top channels section
            if top_channels:
                top_channels_text = ""
                for i, channel_data in enumerate(top_channels, 1):
                    channel = interaction.guild.get_channel(channel_data["channel_id"])
                    channel_name = (
                        channel.name
                        if channel
                        else f"Channel {channel_data['channel_id']}"
                    )
                    top_channels_text += f"{i}. #{channel_name}: {channel_data['message_count']:,} messages\n"

                embed.add_field(
                    name="🏆 Most Active Channels",
                    value=top_channels_text,
                    inline=False,
                )

            embed.add_field(
                name="📅 Time Period",
                value=f"Last {days} day{'s' if days != 1 else ''}\n"
                f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during user stats query: {e}") from e

    @stats.command(
        name="role",
        description="Get comprehensive statistics for a role",
    )
    @handle_interaction_errors
    async def role_stats(
        self, interaction: "Interaction", role: discord.Role, days: int = 7
    ) -> None:
        """Get comprehensive statistics for a specific role.

        Args:
            interaction: The Discord interaction object
            role: The role to get statistics for
            days: Number of days to look back (default: 7, max: 365)

        Raises:
            ValidationError: If the days parameter is invalid
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!", ephemeral=True
            )
            return

        # Validate days parameter
        if days <= 0:
            raise ValidationError(
                field="days", message="Days must be a positive number"
            )

        if days > 365:  # More than a year
            raise ValidationError(
                field="days", message="Days cannot exceed 365 (1 year)"
            )

        # Calculate the time threshold
        d_time = datetime.now() - timedelta(days=days)

        # Get all user IDs with this role
        role_member_ids = [member.id for member in role.members]

        if not role_member_ids:
            embed = discord.Embed(
                title=f"🎭 Role Statistics: {role.name}",
                description="❌ No members found with this role.",
                color=discord.Color.red(),
                timestamp=datetime.now(),
            )
            await interaction.response.send_message(embed=embed)
            return

        try:
            # Query for comprehensive role statistics
            # Use ANY() to match against the list of user IDs
            stats_query = """
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as active_members,
                COUNT(DISTINCT channel_id) as active_channels,
                AVG(LENGTH(content)) as avg_message_length
            FROM messages
            WHERE created_at > $1 AND user_id = ANY($2) AND server_id = $3
            """

            results = await self.bot.db.fetchrow(
                stats_query, d_time, role_member_ids, interaction.guild.id
            )

            if results is None:
                raise QueryError("Database query returned no results")

            # Query for top contributors within the role
            top_contributors_query = """
            SELECT user_id, COUNT(*) as message_count
            FROM messages
            WHERE created_at > $1 AND user_id = ANY($2) AND server_id = $3
            GROUP BY user_id
            ORDER BY message_count DESC
            LIMIT 5
            """

            top_contributors = await self.bot.db.fetch(
                top_contributors_query, d_time, role_member_ids, interaction.guild.id
            )

            # Create a formatted response
            role_color = (
                discord.Color(role.color.value)
                if role.color.value != 0
                else discord.Color.orange()
            )
            embed = discord.Embed(
                title=f"🎭 Role Statistics: {role.name}",
                color=role_color,
                timestamp=datetime.now(),
            )

            # Basic statistics
            embed.add_field(
                name="👥 Total Members",
                value=f"**{len(role_member_ids):,}**",
                inline=True,
            )

            embed.add_field(
                name="👤 Active Members",
                value=f"**{results['active_members']:,}**",
                inline=True,
            )

            embed.add_field(
                name="📝 Total Messages",
                value=f"**{results['total_messages']:,}**",
                inline=True,
            )

            embed.add_field(
                name="📺 Active Channels",
                value=f"**{results['active_channels']:,}**",
                inline=True,
            )

            avg_length = results["avg_message_length"] or 0
            embed.add_field(
                name="📏 Avg Message Length",
                value=f"**{avg_length:.1f}** characters",
                inline=True,
            )

            # Calculate activity rate
            messages_per_day = results["total_messages"] / days if days > 0 else 0
            embed.add_field(
                name="📊 Activity Rate",
                value=f"**{messages_per_day:.1f}** messages/day",
                inline=True,
            )

            # Top contributors section
            if top_contributors:
                top_contributors_text = ""
                for i, contributor_data in enumerate(top_contributors, 1):
                    user = self.bot.get_user(contributor_data["user_id"])
                    username = (
                        user.display_name
                        if user
                        else f"User {contributor_data['user_id']}"
                    )
                    top_contributors_text += f"{i}. {username}: {contributor_data['message_count']:,} messages\n"

                embed.add_field(
                    name="🏆 Top Contributors",
                    value=top_contributors_text,
                    inline=False,
                )

            embed.add_field(
                name="📅 Time Period",
                value=f"Last {days} day{'s' if days != 1 else ''}\n"
                f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during role stats query: {e}") from e

    @stats.command(
        name="category",
        description="Get comprehensive statistics for a category",
    )
    @handle_interaction_errors
    async def category_stats(
        self,
        interaction: "Interaction",
        category: discord.CategoryChannel,
        days: int = 7,
    ) -> None:
        """Get comprehensive statistics for a specific category.

        Args:
            interaction: The Discord interaction object
            category: The category to get statistics for
            days: Number of days to look back (default: 7, max: 365)

        Raises:
            ValidationError: If the days parameter is invalid
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!", ephemeral=True
            )
            return

        # Validate days parameter
        if days <= 0:
            raise ValidationError(
                field="days", message="Days must be a positive number"
            )

        if days > 365:  # More than a year
            raise ValidationError(
                field="days", message="Days cannot exceed 365 (1 year)"
            )

        # Calculate the time threshold
        d_time = datetime.now() - timedelta(days=days)

        # Get all channel IDs in this category
        category_channel_ids = [
            channel.id
            for channel in category.channels
            if isinstance(channel, discord.TextChannel)
        ]

        if not category_channel_ids:
            embed = discord.Embed(
                title=f"📁 Category Statistics: {category.name}",
                description="❌ No text channels found in this category.",
                color=discord.Color.red(),
                timestamp=datetime.now(),
            )
            await interaction.response.send_message(embed=embed)
            return

        try:
            # Query for comprehensive category statistics
            stats_query = """
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(DISTINCT channel_id) as active_channels,
                AVG(LENGTH(content)) as avg_message_length,
                COUNT(*) FILTER (WHERE attachments.id IS NOT NULL) as messages_with_attachments,
                COUNT(*) FILTER (WHERE embeds.id IS NOT NULL) as messages_with_embeds
            FROM messages
            LEFT JOIN attachments ON messages.message_id = attachments.message_id
            LEFT JOIN embeds ON messages.message_id = embeds.message_id
            WHERE messages.created_at > $1 AND messages.channel_id = ANY($2)
            """

            results = await self.bot.db.fetchrow(
                stats_query, d_time, category_channel_ids
            )

            if results is None:
                raise QueryError("Database query returned no results")

            # Query for top channels in the category
            top_channels_query = """
            SELECT channel_id, COUNT(*) as message_count
            FROM messages
            WHERE created_at > $1 AND channel_id = ANY($2)
            GROUP BY channel_id
            ORDER BY message_count DESC
            LIMIT 5
            """

            top_channels = await self.bot.db.fetch(
                top_channels_query, d_time, category_channel_ids
            )

            # Create a formatted response
            embed = discord.Embed(
                title=f"📁 Category Statistics: {category.name}",
                color=discord.Color.gold(),
                timestamp=datetime.now(),
            )

            # Basic statistics
            embed.add_field(
                name="📺 Total Channels",
                value=f"**{len(category_channel_ids):,}**",
                inline=True,
            )

            embed.add_field(
                name="📺 Active Channels",
                value=f"**{results['active_channels']:,}**",
                inline=True,
            )

            embed.add_field(
                name="📝 Total Messages",
                value=f"**{results['total_messages']:,}**",
                inline=True,
            )

            embed.add_field(
                name="👥 Unique Users",
                value=f"**{results['unique_users']:,}**",
                inline=True,
            )

            avg_length = results["avg_message_length"] or 0
            embed.add_field(
                name="📏 Avg Message Length",
                value=f"**{avg_length:.1f}** characters",
                inline=True,
            )

            # Calculate activity rate
            messages_per_day = results["total_messages"] / days if days > 0 else 0
            embed.add_field(
                name="📊 Activity Rate",
                value=f"**{messages_per_day:.1f}** messages/day",
                inline=True,
            )

            embed.add_field(
                name="📎 Messages with Attachments",
                value=f"**{results['messages_with_attachments']:,}**",
                inline=True,
            )

            embed.add_field(
                name="🎨 Messages with Embeds",
                value=f"**{results['messages_with_embeds']:,}**",
                inline=True,
            )

            # Top channels section
            if top_channels:
                top_channels_text = ""
                for i, channel_data in enumerate(top_channels, 1):
                    channel = interaction.guild.get_channel(channel_data["channel_id"])
                    channel_name = (
                        channel.name
                        if channel
                        else f"Channel {channel_data['channel_id']}"
                    )
                    top_channels_text += f"{i}. #{channel_name}: {channel_data['message_count']:,} messages\n"

                embed.add_field(
                    name="🏆 Most Active Channels",
                    value=top_channels_text,
                    inline=False,
                )

            embed.add_field(
                name="📅 Time Period",
                value=f"Last {days} day{'s' if days != 1 else ''}\n"
                f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(
                f"Unexpected error during category stats query: {e}"
            ) from e

    @stats.command(
        name="thread",
        description="Get comprehensive statistics for a thread",
    )
    @handle_interaction_errors
    async def thread_stats(
        self, interaction: "Interaction", thread: discord.Thread, days: int = 7
    ) -> None:
        """Get comprehensive statistics for a specific thread.

        Args:
            interaction: The Discord interaction object
            thread: The thread to get statistics for
            days: Number of days to look back (default: 7, max: 365)

        Raises:
            ValidationError: If the days parameter is invalid
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        # Validate days parameter
        if days <= 0:
            raise ValidationError(
                field="days", message="Days must be a positive number"
            )

        if days > 365:  # More than a year
            raise ValidationError(
                field="days", message="Days cannot exceed 365 (1 year)"
            )

        # Calculate the time threshold
        d_time = datetime.now() - timedelta(days=days)

        try:
            # Query for comprehensive thread statistics
            stats_query = """
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as unique_users,
                AVG(LENGTH(content)) as avg_message_length,
                COUNT(*) FILTER (WHERE attachments.id IS NOT NULL) as messages_with_attachments,
                COUNT(*) FILTER (WHERE embeds.id IS NOT NULL) as messages_with_embeds
            FROM messages
            LEFT JOIN attachments ON messages.message_id = attachments.message_id
            LEFT JOIN embeds ON messages.message_id = embeds.message_id
            WHERE messages.created_at > $1 AND messages.channel_id = $2
            """

            results = await self.bot.db.fetchrow(stats_query, d_time, thread.id)

            if results is None:
                raise QueryError("Database query returned no results")

            # Query for top users in the thread
            top_users_query = """
            SELECT user_id, COUNT(*) as message_count
            FROM messages
            WHERE created_at > $1 AND channel_id = $2
            GROUP BY user_id
            ORDER BY message_count DESC
            LIMIT 5
            """

            top_users = await self.bot.db.fetch(top_users_query, d_time, thread.id)

            # Create a formatted response
            embed = discord.Embed(
                title=f"🧵 Thread Statistics: {thread.name}",
                color=discord.Color.teal(),
                timestamp=datetime.now(),
            )

            # Basic statistics
            embed.add_field(
                name="📝 Total Messages",
                value=f"**{results['total_messages']:,}**",
                inline=True,
            )

            embed.add_field(
                name="👥 Unique Users",
                value=f"**{results['unique_users']:,}**",
                inline=True,
            )

            avg_length = results["avg_message_length"] or 0
            embed.add_field(
                name="📏 Avg Message Length",
                value=f"**{avg_length:.1f}** characters",
                inline=True,
            )

            embed.add_field(
                name="📎 Messages with Attachments",
                value=f"**{results['messages_with_attachments']:,}**",
                inline=True,
            )

            embed.add_field(
                name="🎨 Messages with Embeds",
                value=f"**{results['messages_with_embeds']:,}**",
                inline=True,
            )

            # Calculate activity rate
            messages_per_day = results["total_messages"] / days if days > 0 else 0
            embed.add_field(
                name="📊 Activity Rate",
                value=f"**{messages_per_day:.1f}** messages/day",
                inline=True,
            )

            # Thread-specific information
            embed.add_field(
                name="🏷️ Thread Info",
                value=f"**Parent:** <#{thread.parent_id}>\n**Archived:** {'Yes' if thread.archived else 'No'}",
                inline=True,
            )

            if thread.owner:
                embed.add_field(
                    name="👤 Thread Owner",
                    value=f"{thread.owner.mention}",
                    inline=True,
                )

            # Top users section
            if top_users:
                top_users_text = ""
                for i, user_data in enumerate(top_users, 1):
                    user = self.bot.get_user(user_data["user_id"])
                    username = (
                        user.display_name if user else f"User {user_data['user_id']}"
                    )
                    top_users_text += (
                        f"{i}. {username}: {user_data['message_count']:,} messages\n"
                    )

                embed.add_field(
                    name="🏆 Top Contributors",
                    value=top_users_text,
                    inline=False,
                )

            embed.add_field(
                name="📅 Time Period",
                value=f"Last {days} day{'s' if days != 1 else ''}\n"
                f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during thread stats query: {e}") from e

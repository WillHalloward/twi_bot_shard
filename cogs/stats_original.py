import asyncio
import logging
from datetime import datetime, timedelta

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ext.commands import Cog

import config
from utils.error_handling import handle_command_errors, handle_interaction_errors
from utils.exceptions import (
    DatabaseError,
    QueryError,
    ValidationError,
)


async def save_reaction(self, reaction: discord.Reaction) -> None:
    try:
        # Get all users who reacted
        users = [user async for user in reaction.users()]

        if not users:
            return

        current_time = datetime.now().replace(tzinfo=None)

        # Prepare batch data based on emoji type using pattern matching
        match reaction.emoji:
            case str() as emoji_str:
                # String emoji (Unicode emoji)
                reaction_data = [
                    (
                        emoji_str,
                        reaction.message.id,
                        user.id,
                        None,
                        False,
                        None,
                        None,
                        current_time,
                        False,
                    )
                    for user in users
                ]

                # Execute batch insert
                await self.bot.db.execute_many(
                    """
                    INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                    ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                    """,
                    reaction_data,
                )

            case _ if reaction.is_custom_emoji():
                # Custom emoji
                reaction_data = [
                    (
                        None,
                        reaction.message.id,
                        user.id,
                        reaction.emoji.name,
                        reaction.emoji.animated,
                        reaction.emoji.id,
                        f"https://cdn.discordapp.com/emojis/{reaction.emoji.id}.{'gif' if reaction.emoji.animated else 'png'}",
                        current_time,
                        reaction.is_custom_emoji(),
                    )
                    for user in users
                ]

                # Execute batch insert
                await self.bot.db.execute_many(
                    """
                    INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                    ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                    """,
                    reaction_data,
                )

            case _:
                # Fallback for other emoji types
                reaction_data = [
                    (
                        reaction.emoji.name,
                        reaction.message.id,
                        user.id,
                        reaction.emoji.name,
                        None,
                        None,
                        None,
                        current_time,
                        reaction.emoji.is_custom_emoji(),
                    )
                    for user in users
                ]

                # Execute batch insert
                await self.bot.db.execute_many(
                    """
                    INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                    ON CONFLICT (message_id, user_id, unicode_emoji) DO UPDATE SET removed = FALSE
                    """,
                    reaction_data,
                )

    except Exception as e:
        logging.error(f"Failed to batch insert reactions into db: {e}")


async def save_message(self, message) -> None:
    # Prepare data for batch operations
    mentions = []
    for mention in message.mentions:
        mentions.append((message.id, mention.id))

    role_mentions = []
    for role_mention in message.role_mentions:
        role_mentions.append((message.id, role_mention.id))

    # Process reactions if any
    if message.reactions:
        for reaction in message.reactions:
            await save_reaction(self, reaction)

    try:
        nick = message.author.nick
    except AttributeError:
        nick = ""

    try:
        reference = message.reference.message_id
    except AttributeError:
        reference = None

    # Prepare statements if not already prepared
    if not hasattr(self, "save_message_stmt"):
        self.save_message_stmt = await self.bot.db.prepare_statement(
            "save_message",
            "INSERT INTO messages(message_id, created_at, content, user_name, server_name, server_id, channel_id, "
            "channel_name, user_id, user_nick, jump_url, is_bot, deleted, reference) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",
        )

    if not hasattr(self, "save_user_stmt"):
        self.save_user_stmt = await self.bot.db.prepare_statement(
            "save_user",
            "INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4)",
        )

    if not hasattr(self, "save_user_mention_stmt"):
        self.save_user_mention_stmt = await self.bot.db.prepare_statement(
            "save_user_mention",
            "INSERT INTO mentions(message_id, user_mention) VALUES ($1,$2)",
        )

    if not hasattr(self, "save_role_mention_stmt"):
        self.save_role_mention_stmt = await self.bot.db.prepare_statement(
            "save_role_mention",
            "INSERT INTO mentions(message_id, role_mention) VALUES ($1,$2)",
        )

    # Use transaction for related operations
    try:
        async with await self.bot.db.transaction():
            # Insert message using prepared statement
            await self.save_message_stmt.execute(
                message.id,
                message.created_at.replace(tzinfo=None),
                message.content,
                message.author.name,
                message.guild.name,
                message.guild.id,
                message.channel.id,
                message.channel.name,
                message.author.id,
                nick,
                message.jump_url,
                message.author.bot,
                False,
                reference,
            )

            # Batch insert mentions if any
            if mentions:
                await self.bot.db.execute_many(
                    "INSERT INTO mentions(message_id, user_mention) VALUES ($1,$2)",
                    mentions,
                )

            # Batch insert role mentions if any
            if role_mentions:
                await self.bot.db.execute_many(
                    "INSERT INTO mentions(message_id, role_mention) VALUES ($1,$2)",
                    role_mentions,
                )
    except asyncpg.exceptions.UniqueViolationError:
        logging.error(f"{message.id} already in DB")
    except asyncpg.exceptions.ForeignKeyViolationError as e:
        logging.error(f"{e}")
        # If user doesn't exist, create it and then insert the message
        try:
            async with await self.bot.db.transaction():
                # Insert user using prepared statement
                await self.save_user_stmt.execute(
                    message.author.id,
                    message.author.created_at.replace(tzinfo=None),
                    message.author.bot,
                    message.author.name,
                )

                # Insert message using prepared statement
                await self.save_message_stmt.execute(
                    message.id,
                    message.created_at.replace(tzinfo=None),
                    message.content,
                    message.author.name,
                    message.guild.name,
                    message.guild.id,
                    message.channel.id,
                    message.channel.name,
                    message.author.id,
                    nick,
                    message.jump_url,
                    message.author.bot,
                    False,
                    reference,
                )

                # Batch insert mentions if any
                if mentions:
                    await self.bot.db.execute_many(
                        "INSERT INTO mentions(message_id, user_mention) VALUES ($1,$2)",
                        mentions,
                    )

                # Batch insert role mentions if any
                if role_mentions:
                    await self.bot.db.execute_many(
                        "INSERT INTO mentions(message_id, role_mention) VALUES ($1,$2)",
                        role_mentions,
                    )
        except Exception as e:
            logging.error(f"Error saving message after user creation: {e}")


class StatsCogs(commands.Cog, name="stats"):

    def __init__(self, bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("cogs.stats")
        if config.logfile != "test":
            self.stats_loop.start()

    @commands.command(name="save_users", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_users(self, ctx) -> None:
        """Save all guild members to the database.

        This command processes all members from all guilds the bot is in,
        adding new users to the users table and updating server memberships.

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
    async def save_servers(self, ctx) -> None:
        """Save all guild information to the database.

        This command processes all guilds the bot is in,
        adding new servers to the servers table.

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
    async def save_channels(self, ctx) -> None:
        """Save all text channels to the database.

        This command processes all text channels from all guilds the bot is in,
        adding new channels to the channels table.

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

                        if "INSERT" in result:
                            channels_added += 1
                            self.logger.debug(
                                f"Added new channel: {channel.name} ({channel.id})"
                            )
                        else:
                            channels_updated += 1
                            self.logger.debug(
                                f"Updated existing channel: {channel.name} ({channel.id})"
                            )

                    except asyncpg.PostgresError as e:
                        self.logger.error(
                            f"Failed to save channel '{channel.name}' ({channel.id}) in guild {guild.name}: {e}"
                        )
                        # Continue processing other channels instead of failing completely
                        continue

                    guild_channels_processed += 1
                    channels_processed += 1

                self.logger.info(
                    f"Processed {guild_channels_processed} channels from guild {guild.name}"
                )
                guilds_processed += 1

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

    @commands.command(name="save_emotes", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_emotes(self, ctx) -> None:
        """Save all custom emotes to the database.

        This command processes all custom emotes from all guilds the bot is in,
        adding new emotes to the emotes table.

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

    @commands.command(name="save_categories", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_categories(self, ctx) -> None:
        """Save all channel categories to the database.

        This command processes all channel categories from all guilds the bot is in,
        adding new categories to the categories table.

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
    async def save_threads(self, ctx) -> None:
        """Save all threads to the database.

        This command processes all threads from all guilds the bot is in,
        adding new threads to the threads table.

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

    @commands.command(name="save_roles", hidden=True)
    @commands.is_owner()
    @handle_command_errors
    async def save_roles(self, ctx) -> None:
        """Save all roles and role memberships to the database.

        This command processes all roles from all guilds the bot is in,
        adding new roles to the roles table and updating role memberships.

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
    async def update_role_color(self, ctx) -> None:
        """Update role colors in the database.

        This command updates the color field for all roles in the database
        to match their current Discord color values.

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
    async def save_users_from_join_leave(self, ctx) -> None:
        """Save users from join/leave records to the users table.

        This command processes users from the join_leave table and adds them
        to the users table if they don't already exist.

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
    async def save_users_from_messages(self, ctx) -> None:
        """Save users from message reactions to the users table.

        This command finds reactions to messages that aren't in the messages table
        and attempts to fetch those messages to save user information.

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
    async def save(self, ctx) -> None:
        """Perform a comprehensive save of all message history from accessible channels and threads.

        This is a long-running command that processes all guilds, channels, and threads
        the bot has access to, saving message history to the database. It also enables
        ongoing message tracking listeners at completion.

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
                        # Get channel IDs
                        channel_ids = [channel.id for channel in accessible_channels]

                        try:
                            # Batch query for last messages in all channels
                            last_messages = await self.bot.db.fetch(
                                """
                                SELECT m.channel_id, m.created_at
                                FROM messages m
                                INNER JOIN (
                                    SELECT channel_id, MAX(created_at) AS max_created_at
                                    FROM messages
                                    WHERE channel_id = ANY($1)
                                    GROUP BY channel_id
                                ) sub ON m.channel_id = sub.channel_id AND m.created_at = sub.max_created_at
                                """,
                                channel_ids,
                            )
                        except asyncpg.PostgresError as e:
                            self.logger.error(
                                f"Database error querying last messages for guild {guild.name}: {e}"
                            )
                            errors_encountered += 1
                            continue

                        # Create a dictionary for quick lookup
                        last_message_dict = {
                            row["channel_id"]: row["created_at"]
                            for row in last_messages
                        }

                        # Default date for channels with no messages
                        default_date = datetime.strptime("2015-01-01", "%Y-%m-%d")

                        # Process each channel with the pre-fetched data
                        for channel in accessible_channels:
                            try:
                                self.logger.debug(
                                    f"Processing channel: {channel.name} ({channel.id})"
                                )

                                # Get the last message date or use default
                                first = last_message_dict.get(channel.id, default_date)
                                self.logger.debug(
                                    f"Last message in {channel.name} at {first}"
                                )

                                count = 0
                                try:
                                    async for message in channel.history(
                                        limit=None, after=first, oldest_first=True
                                    ):
                                        try:
                                            await save_message(self, message)
                                            count += 1
                                            guild_messages_saved += 1
                                            total_messages_saved += 1
                                        except Exception as e:
                                            self.logger.error(
                                                f"Error saving message {message.id} in channel {channel.name}: {e}"
                                            )
                                            errors_encountered += 1
                                            continue
                                except discord.Forbidden:
                                    self.logger.warning(
                                        f"No permission to read history in channel {channel.name}"
                                    )
                                    errors_encountered += 1
                                    continue
                                except discord.HTTPException as e:
                                    self.logger.error(
                                        f"Discord API error reading channel {channel.name}: {e}"
                                    )
                                    errors_encountered += 1
                                    continue

                                self.logger.info(
                                    f"Channel {channel.name} completed: {count} messages saved"
                                )
                                guild_channels_processed += 1
                                total_channels_processed += 1

                            except Exception as e:
                                self.logger.error(
                                    f"Unexpected error processing channel {channel.name}: {e}"
                                )
                                errors_encountered += 1
                                continue

                    # Process threads
                    self.logger.info(
                        f"Starting thread processing for guild {guild.name}"
                    )

                    # Get all threads with read permissions
                    accessible_threads = [
                        thread
                        for thread in guild.threads
                        if thread.permissions_for(thread.guild.me).read_message_history
                    ]

                    if not accessible_threads:
                        self.logger.info(
                            f"No accessible threads found in guild {guild.name}"
                        )
                    else:
                        # Get thread IDs
                        thread_ids = [thread.id for thread in accessible_threads]

                        try:
                            # Batch query for last messages in all threads
                            last_thread_messages = await self.bot.db.fetch(
                                """
                                SELECT m.channel_id, m.created_at
                                FROM messages m
                                INNER JOIN (
                                    SELECT channel_id, MAX(created_at) AS max_created_at
                                    FROM messages
                                    WHERE channel_id = ANY($1)
                                    GROUP BY channel_id
                                ) sub ON m.channel_id = sub.channel_id AND m.created_at = sub.max_created_at
                                """,
                                thread_ids,
                            )
                        except asyncpg.PostgresError as e:
                            self.logger.error(
                                f"Database error querying last thread messages for guild {guild.name}: {e}"
                            )
                            errors_encountered += 1
                            # Continue with threads processing even if query fails
                            last_thread_messages = []

                        # Create a dictionary for quick lookup
                        last_thread_message_dict = {
                            row["channel_id"]: row["created_at"]
                            for row in last_thread_messages
                        }

                        # Default date for threads with no messages
                        default_date = datetime.strptime("2015-01-01", "%Y-%m-%d")

                        # Process each thread with the pre-fetched data
                        for thread in accessible_threads:
                            try:
                                self.logger.debug(
                                    f"Processing thread: {thread.name} ({thread.id})"
                                )

                                # Get the last message date or use default
                                first = last_thread_message_dict.get(
                                    thread.id, default_date
                                )
                                self.logger.debug(
                                    f"Last message in thread {thread.name} at {first}"
                                )

                                count = 0
                                try:
                                    async for message in thread.history(
                                        limit=None, after=first, oldest_first=True
                                    ):
                                        try:
                                            await save_message(self, message)
                                            count += 1
                                            guild_messages_saved += 1
                                            total_messages_saved += 1
                                            # Small delay to prevent rate limiting
                                            await asyncio.sleep(0.05)
                                        except Exception as e:
                                            self.logger.error(
                                                f"Error saving message {message.id} in thread {thread.name}: {e}"
                                            )
                                            errors_encountered += 1
                                            continue
                                except discord.Forbidden:
                                    self.logger.warning(
                                        f"No permission to read history in thread {thread.name}"
                                    )
                                    errors_encountered += 1
                                    continue
                                except discord.HTTPException as e:
                                    self.logger.error(
                                        f"Discord API error reading thread {thread.name}: {e}"
                                    )
                                    errors_encountered += 1
                                    continue

                                self.logger.info(
                                    f"Thread {thread.name} completed: {count} messages saved"
                                )
                                guild_threads_processed += 1
                                total_threads_processed += 1

                            except Exception as e:
                                self.logger.error(
                                    f"Unexpected error processing thread {thread.name}: {e}"
                                )
                                errors_encountered += 1
                                continue

                    # Guild processing completed
                    guild_duration = datetime.now() - guild_start_time
                    guilds_processed += 1

                    self.logger.info(
                        f"Guild {guild.name} completed: "
                        f"{guild_channels_processed} channels, {guild_threads_processed} threads, "
                        f"{guild_messages_saved} messages saved in {guild_duration}"
                    )

                    # Send progress update every few guilds or if it's the last guild
                    if guild_index % 3 == 0 or guild_index == total_guilds:
                        elapsed_time = datetime.now() - start_time
                        try:
                            await progress_msg.edit(
                                content=f"🔄 **Message save operation in progress**\n"
                                f"**Progress:** {guilds_processed}/{total_guilds} guilds processed\n"
                                f"**Channels processed:** {total_channels_processed}\n"
                                f"**Threads processed:** {total_threads_processed}\n"
                                f"**Messages saved:** {total_messages_saved:,}\n"
                                f"**Errors encountered:** {errors_encountered}\n"
                                f"**Elapsed time:** {elapsed_time}\n"
                                f"*Currently processing: {guild.name}*"
                            )
                        except discord.HTTPException:
                            # If we can't edit the message, continue anyway
                            pass

                except Exception as e:
                    self.logger.error(
                        f"Critical error processing guild {guild.name}: {e}"
                    )
                    errors_encountered += 1
                    continue

        except Exception as e:
            self.logger.error(f"Critical error during save operation: {e}")
            raise DatabaseError("Save operation failed with critical error") from e

        # Save operation completed
        total_duration = datetime.now() - start_time
        self.logger.info(f"Save operation completed in {total_duration}")

        # Enable event listeners for ongoing message tracking
        try:
            listeners_enabled = 0
            if self.save_listener not in self.bot.extra_events.get("on_message", []):
                self.bot.add_listener(self.save_listener, name="on_message")
                listeners_enabled += 1
            if self.message_deleted not in self.bot.extra_events.get(
                "on_raw_message_delete", []
            ):
                self.bot.add_listener(
                    self.message_deleted, name="on_raw_message_delete"
                )
                listeners_enabled += 1
            if self.message_edited not in self.bot.extra_events.get(
                "on_raw_message_edit", []
            ):
                self.bot.add_listener(self.message_edited, name="on_raw_message_edit")
                listeners_enabled += 1
            if self.reaction_add not in self.bot.extra_events.get(
                "on_raw_reaction_add", []
            ):
                self.bot.add_listener(self.reaction_add, name="on_raw_reaction_add")
                listeners_enabled += 1
            if self.reaction_remove not in self.bot.extra_events.get(
                "on_raw_reaction_remove", []
            ):
                self.bot.add_listener(
                    self.reaction_remove, name="on_raw_reaction_remove"
                )
                listeners_enabled += 1

            self.logger.info(
                f"Enabled {listeners_enabled} event listeners for ongoing message tracking"
            )
        except Exception as e:
            self.logger.error(f"Error enabling event listeners: {e}")
            errors_encountered += 1

        # Send comprehensive completion message
        completion_message = (
            f"✅ **Comprehensive message save operation completed!**\n"
            f"**Total duration:** {total_duration}\n"
            f"**Guilds processed:** {guilds_processed}/{total_guilds}\n"
            f"**Channels processed:** {total_channels_processed}\n"
            f"**Threads processed:** {total_threads_processed}\n"
            f"**Messages saved:** {total_messages_saved:,}\n"
            f"**Errors encountered:** {errors_encountered}\n"
            f"**Event listeners enabled:** ✅\n"
            f"**Completed at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

        try:
            await progress_msg.edit(content=completion_message)
        except discord.HTTPException:
            # If we can't edit, send a new message
            await ctx.send(completion_message)

        # Notify the bot owner
        try:
            owner = self.bot.get_user(self.bot.owner_id)
            if owner is not None:
                await owner.send(
                    f"🎉 **Save command completed successfully!**\n"
                    f"**Messages saved:** {total_messages_saved:,}\n"
                    f"**Duration:** {total_duration}\n"
                    f"**Errors:** {errors_encountered}"
                )
                self.logger.info("Completion notification sent to bot owner")
            else:
                self.logger.warning(
                    "Could not find bot owner to send completion notification"
                )
        except Exception as e:
            self.logger.error(f"Failed to send completion notification to owner: {e}")

    @Cog.listener("on_message")
    async def save_listener(self, message) -> None:
        if not isinstance(message.channel, discord.channel.DMChannel):
            try:
                await save_message(self, message)
            except Exception as e:
                logging.error(f"Error: {e} on message save")

    @Cog.listener("on_raw_message_edit")
    async def message_edited(self, message) -> None:
        try:
            if (
                "content" in message.data
                and "edited_timestamp" in message.data
                and message.data["edited_timestamp"] is not None
            ):
                logging.debug(f"message edited {message}")
                old_content = await self.bot.db.fetchval(
                    "SELECT content FROM messages where message_id = $1 LIMIT 1",
                    int(message.data["id"]),
                )
                logging.debug(old_content)
                await self.bot.db.execute(
                    "INSERT INTO message_edit(id, old_content, new_content, edit_timestamp) VALUES ($1,$2,$3,$4)",
                    int(message.data["id"]),
                    old_content,
                    message.data["content"],
                    datetime.fromisoformat(message.data["edited_timestamp"]).replace(
                        tzinfo=None
                    ),
                )
                logging.debug("post insert")
                await self.bot.db.execute(
                    "UPDATE messages set content = $1 WHERE message_id = $2",
                    message.data["content"],
                    int(message.data["id"]),
                )
                logging.debug("post update")
        except:
            logging.exception(f"message_edited - {message.data}")

    @Cog.listener("on_raw_message_delete")
    async def message_deleted(self, message) -> None:

        await self.bot.db.execute(
            "UPDATE public.messages SET deleted = true WHERE message_id = $1",
            message.message_id,
        )

    @Cog.listener("on_raw_reaction_add")
    async def reaction_add(self, reaction) -> None:
        try:
            current_time = datetime.now().replace(tzinfo=None)

            # Use transaction for consistency
            async with await self.bot.db.transaction():
                if reaction.emoji.is_custom_emoji():
                    await self.bot.db.execute(
                        """
                        INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                        ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                        """,
                        None,
                        reaction.message_id,
                        reaction.user_id,
                        reaction.emoji.name,
                        reaction.emoji.animated,
                        reaction.emoji.id,
                        f"https://cdn.discordapp.com/emojis/{reaction.emoji.id}.{'gif' if reaction.emoji.animated else 'png'}",
                        current_time,
                        reaction.emoji.is_custom_emoji(),
                    )
                elif isinstance(reaction.emoji, str):
                    await self.bot.db.execute(
                        """
                        INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                        ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                        """,
                        reaction.emoji,
                        reaction.message_id,
                        reaction.user_id,
                        None,
                        False,
                        None,
                        None,
                        current_time,
                        False,
                    )
                else:
                    await self.bot.db.execute(
                        """
                        INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                        ON CONFLICT (message_id, user_id, unicode_emoji) DO UPDATE SET removed = FALSE
                        """,
                        reaction.emoji.name,
                        reaction.message_id,
                        reaction.user_id,
                        reaction.emoji.name,
                        None,
                        None,
                        None,
                        current_time,
                        reaction.emoji.is_custom_emoji(),
                    )
        except Exception as e:
            logging.exception(f"Error: {e} on reaction add")

    @Cog.listener("on_raw_reaction_remove")
    async def reaction_remove(self, reaction) -> None:
        try:
            # Use transaction for consistency
            async with await self.bot.db.transaction():
                if reaction.emoji.is_custom_emoji():
                    await self.bot.db.execute(
                        """
                        UPDATE reactions
                        SET removed = TRUE 
                        WHERE message_id = $1 AND user_id = $2 AND emoji_id = $3
                        """,
                        reaction.message_id,
                        reaction.user_id,
                        reaction.emoji.id,
                    )
                else:
                    await self.bot.db.execute(
                        """
                        UPDATE reactions
                        SET removed = TRUE 
                        WHERE message_id = $1 AND user_id = $2 AND unicode_emoji = $3
                        """,
                        reaction.message_id,
                        reaction.user_id,
                        reaction.emoji.name,
                    )

                # Log the removal for analytics
                await self.bot.db.execute(
                    """
                    INSERT INTO updates(updated_table, action, before, after, date, primary_key) 
                    VALUES($1, $2, $3, $4, $5, $6)
                    """,
                    "reactions",
                    "REACTION_REMOVED",
                    f"message_id:{reaction.message_id},user_id:{reaction.user_id}",
                    "removed=TRUE",
                    datetime.now().replace(tzinfo=None),
                    f"{reaction.message_id}:{reaction.user_id}",
                )
        except Exception as e:
            logging.error(f"Error: {e} on reaction remove")

    @Cog.listener("on_member_join")
    async def member_join(self, member) -> None:
        await self.bot.db.execute(
            "INSERT INTO join_leave VALUES($1,$2,$3,$4,$5,$6)",
            member.id,
            datetime.now(),
            "join",
            member.guild.name,
            member.guild.id,
            member.created_at.replace(tzinfo=None),
        )
        try:
            await self.bot.db.execute(
                "INSERT INTO "
                "users(user_id, created_at, bot, username) "
                "VALUES($1,$2,$3,$4) ON CONFLICT (user_id) DO UPDATE SET username = $4",
                member.id,
                member.created_at.replace(tzinfo=None),
                member.bot,
                member.name,
            )
            await self.bot.db.execute(
                "INSERT INTO server_membership(user_id, server_id) VALUES ($1,$2)",
                member.id,
                member.guild.id,
            )
        except asyncpg.UniqueViolationError:
            logging.error("Failed to insert user into server_membership")
        except Exception as e:
            channel = self.bot.get_channel(297916314239107072)
            await channel.send(f"{e}")

    @Cog.listener("on_member_remove")
    async def member_remove(self, member) -> None:
        await self.bot.db.execute(
            "DELETE FROM server_membership WHERE user_id = $1 AND server_id = $2",
            member.id,
            member.guild.id,
        )
        await self.bot.db.execute(
            "DELETE FROM role_membership WHERE role_id IN (SELECT id FROM roles WHERE guild_id = $2) AND user_id = $1",
            member.id,
            member.guild.id,
        )
        await self.bot.db.execute(
            "INSERT INTO join_leave VALUES($1,$2,$3,$4,$5,$6)",
            member.id,
            datetime.now(),
            "leave",
            member.guild.name,
            member.guild.id,
            member.created_at.replace(tzinfo=None),
        )

    @Cog.listener("on_member_update")
    async def member_roles_update(self, before, after) -> None:
        if before.roles != after.roles:
            if len(before.roles) < len(after.roles):
                gained = set(after.roles) - set(before.roles)
                gained = gained.pop()
                try:
                    await self.bot.db.execute(
                        "INSERT INTO role_membership(user_id, role_id) VALUES($1,$2)",
                        after.id,
                        gained.id,
                    )
                    await self.bot.db.execute(
                        "INSERT INTO role_history(role_id, user_id, date) VALUES($1,$2,$3)",
                        gained.id,
                        after.id,
                        datetime.now().replace(tzinfo=None),
                    )
                except asyncpg.exceptions.ForeignKeyViolationError:
                    await self.bot.db.execute(
                        "INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4)",
                        after.id,
                        after.created_at.replace(tzinfo=None),
                        after.bot,
                        after.name,
                    )
                    await self.bot.db.execute(
                        "INSERT INTO role_membership(user_id, role_id) VALUES($1,$2)",
                        after.id,
                        gained.id,
                    )
                except asyncpg.exceptions.UniqueViolationError:
                    logging.warning(
                        f"Duplicate key value violation {after.id}, {gained.id}"
                    )
            else:
                lost = set(before.roles) - set(after.roles)
                lost = lost.pop()
                await self.bot.db.execute(
                    "DELETE FROM role_membership WHERE user_id = $1 AND role_id = $2",
                    after.id,
                    lost.id,
                )
                await self.bot.db.execute(
                    "INSERT INTO role_history(role_id, user_id, date, gained) VALUES($1,$2,$3,FALSE)",
                    lost.id,
                    after.id,
                    datetime.now().replace(tzinfo=None),
                )
                if lost.id == 585789843368574997:
                    pink_role = after.guild.get_role(690373096099545168)
                    after.remove_roles(pink_role)

    @Cog.listener("on_user_update")
    async def user_update(self, before, after) -> None:
        if before.name != after.name:
            try:
                await self.bot.db.execute(
                    "UPDATE users SET username = $1 WHERE user_id = $2",
                    after.name,
                    after.id,
                )

                await self.bot.db.execute(
                    "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                    "users",
                    "UPDATE_USERNAME",
                    before.name,
                    after.name,
                    datetime.now().replace(tzinfo=None),
                    str(after.id),
                )
            except Exception as e:
                logging.error(f"Error {e}")

    @Cog.listener("on_guild_channel_create")
    async def guild_channel_create(self, channel) -> None:
        if channel.type == discord.ChannelType.text:
            try:
                await self.bot.db.execute(
                    "INSERT INTO "
                    "channels(id, name, category_id, created_at, guild_id, position, topic, is_nsfw) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                    channel.id,
                    channel.name,
                    channel.category_id,
                    channel.created_at.replace(tzinfo=None),
                    channel.guild.id,
                    channel.position,
                    channel.topic,
                    channel.is_nsfw(),
                )
            except Exception as e:
                logging.error(f"{e}")
        elif channel.type == discord.ChannelType.category:
            try:
                await self.bot.db.execute(
                    "INSERT INTO categories(id, name, created_at, guild_id, position, is_nsfw) VALUES($1,$2,$3,$4,$5,$6)",
                    channel.id,
                    channel.name,
                    channel.created_at.replace(tzinfo=None),
                    channel.guild_id,
                    channel.position,
                    channel.is_nsfw(),
                )
            except Exception as e:
                logging.error(f"{e}")

    @Cog.listener("on_guild_channel_delete")
    async def guild_channel_delete(self, channel) -> None:
        await self.bot.db.execute(
            "UPDATE channels set deleted = TRUE where id = $1", channel.id
        )
        await self.bot.db.execute(
            "UPDATE messages SET deleted = TRUE where channel_id = $1", channel.id
        )
        await self.bot.db.execute(
            "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
            "channel",
            "DELETED_CHANNEL",
            channel.name,
            channel.name,
            datetime.now().replace(tzinfo=None),
            str(channel.id),
        )

    @Cog.listener("on_thread_create")
    async def thread_created(self, thread) -> None:
        logging.info(f"A new thread has been created: {thread}")
        try:
            await self.bot.db.execute(
                "INSERT INTO "
                "threads(id, guild_id, parent_id, owner_id, slowmode_delay, archived, locked, archiver_id, auto_archive_duration, is_private, name, deleted) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
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
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads",
                "THREAD_CREATED",
                thread.name,
                thread.name,
                datetime.now().replace(tzinfo=None),
                str(thread.id),
            )
            if thread.parent_id != 1190045713778868335:
                await thread.send("<@&1153075640535367721>")
        except asyncpg.UniqueViolationError:
            logging.warning(f"Duplicate on {thread} in db")
        except Exception as e:
            logging.error(f"{e}")

    @Cog.listener("on_thread_delete")
    async def thread_deleted(self, thread) -> None:
        await self.bot.db.execute(
            "UPDATE threads SET deleted = $2 WHERE id = $1", thread.id, True
        )
        await self.bot.db.execute(
            "UPDATE messages SET deleted = $2 where channel_id = $1", thread.id, True
        )
        await self.bot.db.execute(
            "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
            "VALUES ($1,$2,$3,$4,$5,$6)",
            "threads",
            "THREAD_DELETED",
            thread.name,
            thread.name,
            datetime.now().replace(tzinfo=None),
            str(thread.id),
        )

    @Cog.listener("on_thread_update")
    async def thread_update(self, before, after) -> None:
        if before.slowmode_delay != after.slowmode_delay:
            await self.bot.db.execute(
                "UPDATE threads set slowmode_delay = $1 where id = $2",
                after.slowmode_delay,
                after.id,
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads",
                "THREAD_SLOWMODE_UPDATED",
                str(before.slowmode_delay),
                str(after.slowmode_delay),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.archived != after.archived:
            if after.archiver_id:
                await self.bot.db.execute(
                    "UPDATE threads set archived = $1 where id = $2",
                    after.archived,
                    after.id,
                )
            else:
                await self.bot.db.execute(
                    "UPDATE threads set archived = $1 AND archiver_id = $3 where id = $2",
                    after.archived,
                    after.id,
                    after.archiver_id,
                )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads",
                "THREAD_ARCHIVED_UPDATED",
                str(before.archived),
                str(after.archived),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.locked != after.locked:
            await self.bot.db.execute(
                "UPDATE threads set locked = $1 where id = $2", after.locked, after.id
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads",
                "THREAD_LOCKED_UPDATED",
                str(before.locked),
                str(after.locked),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.auto_archive_duration != after.auto_archive_duration:
            await self.bot.db.execute(
                "UPDATE threads set auto_archive_duration = $1 where id = $2",
                after.auto_archive_duration,
                after.id,
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads",
                "THREAD_AUTO_ARCHIVE_DURATION_UPDATED",
                str(before.auto_archive_duration),
                str(after.auto_archive_duration),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.is_private() != after.is_private():
            await self.bot.db.execute(
                "UPDATE threads set is_private = $1 where id = $2",
                after.is_private(),
                after.id,
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads",
                "THREAD_PRIVATE_UPDATED",
                str(before.is_private()),
                str(after.is_private()),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.name != after.name:
            await self.bot.db.execute(
                "UPDATE threads set name = $1 where id = $2", after.name, after.id
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads",
                "THREAD_NAME_UPDATED",
                before.name,
                after.name,
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )

    @Cog.listener("on_thread_member_join")
    async def thread_member_join(self, threadmember) -> None:
        await self.bot.db.execute(
            "INSERT INTO thread_membership(user_id, thread_id) VALUES($1,$2)",
            threadmember.id,
            threadmember.thread_id,
        )

    @Cog.listener("on_thread_member_remove")
    async def thread_member_leave(self, threadmember) -> None:
        await self.bot.db.execute(
            "DELETE FROM thread_membership WHERE user_id = $1 and thread_id = $2",
            threadmember.id,
            threadmember.thread_id,
        )

    @Cog.listener("on_guild_channel_update")
    async def guild_channel_update(self, before, after) -> None:
        if before.name != after.name:
            await self.bot.db.execute(
                "UPDATE channels set name = $1 where id = $2", after.name, after.id
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "channels",
                "UPDATE_CHANNEL_NAME",
                before.name,
                after.name,
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.category_id != after.category_id:
            await self.bot.db.execute(
                "UPDATE channels set category_id = $1 where id = $2",
                after.category_id,
                after.id,
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "channels",
                "UPDATE_CHANNEL_CATEGORY_ID",
                str(before.category_id),
                str(after.category_id),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.position != after.position:
            await self.bot.db.execute(
                "UPDATE channels set position = $1 where id = $2",
                after.position,
                after.id,
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "channels",
                "UPDATE_CHANNEL_POSITION",
                str(before.position),
                str(after.position),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.topic != after.topic:
            await self.bot.db.execute(
                "UPDATE channels set topic = $1 where id = $2", after.topic, after.id
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "channels",
                "UPDATE_CHANNEL_TOPIC",
                before.topic,
                after.topic,
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.is_nsfw() != after.is_nsfw():
            await self.bot.db.execute(
                "UPDATE channels set is_nsfw = $1 where id = $2",
                after.is_nsfw(),
                after.id,
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "channels",
                "UPDATE_CHANNEL_IS_NSFW",
                str(before.is_nsfw()),
                str(after.is_nsfw()),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )

    @Cog.listener("on_guild_update")
    async def guild_update(self, before, after) -> None:
        if before.name != after.name:
            await self.bot.db.execute(
                "UPDATE servers set server_name = $1 WHERE server_id = $2",
                after.name,
                after.id,
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "servers",
                "UPDATE_SERVER_NAME",
                before.name,
                after.name,
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )

    @Cog.listener("on_guild_emojis_update")
    async def guild_emoji_update(self, guild, before, after) -> None:
        print(f"change detected {guild}, {before}, {after}")

        before_dict = {emoji.id: emoji for emoji in before}
        after_dict = {emoji.id: emoji for emoji in after}

        for id, emoji in before_dict.items():
            after_emoji = after_dict.get(id)
            if after_emoji is None:
                print(f"Emote removed: {emoji}")
                await self.bot.db.execute("DELETE FROM emotes where emote_id = $1", id)
                return
            elif (
                emoji.name != after_emoji.name or emoji.animated != after_emoji.animated
            ):
                print(f"Emote updated: {after_emoji}")
                await self.bot.db.execute(
                    "UPDATE emotes set name = $1, animated = $2, managed = $3  where emote_id = $4",
                    after_emoji.name,
                    after_emoji.animated,
                    after_emoji.managed,
                    id,
                )
                return

        for id, emoji in after_dict.items():
            if id not in before_dict:
                print(f"Emote added: {emoji}")
                await self.bot.db.execute(
                    "INSERT INTO emotes(guild_id, emote_id, name, animated, managed) VALUES ($1,$2,$3,$4,$5)",
                    guild.id,
                    emoji.id,
                    emoji.name,
                    emoji.animated,
                    emoji.managed,
                )
                return

    @Cog.listener("on_guild_role_create")
    async def guild_role_create(self, role) -> None:
        await self.bot.db.execute(
            "INSERT INTO "
            "roles(id, name, color, created_at, hoisted, managed, position, guild_id) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
            role.id,
            role.name,
            str(role.color),
            role.created_at.replace(tzinfo=None),
            role.hoist,
            role.managed,
            role.position,
            role.guild.id,
        )

    @Cog.listener("on_guild_role_delete")
    async def guild_role_delete(self, role) -> None:
        await self.bot.db.execute(
            "UPDATE roles set deleted = TRUE where id = $1", role.id
        )
        await self.bot.db.execute(
            "DELETE FROM role_membership WHERE role_id = $1", role.id
        )

    @Cog.listener("on_guild_role_update")
    async def guild_role_update(self, before, after) -> None:
        if before.name != after.name:
            await self.bot.db.execute(
                "UPDATE roles set name = $1 where id = $2", after.name, after.id
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "roles",
                "UPDATE_ROLE_NAME",
                before.name,
                after.name,
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.color != after.color:
            await self.bot.db.execute(
                "UPDATE roles set color = $1 where id = $2", str(after.color), after.id
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "roles",
                "UPDATE_ROLE_COLOR",
                str(before.color),
                str(after.color),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.hoist != after.hoist:
            await self.bot.db.execute(
                "UPDATE roles set hoisted = $1 where id = $2", after.hoist, after.id
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "roles",
                "UPDATE_ROLE_HOISTED",
                str(before.hoist),
                str(after.hoist),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )
        if before.position != after.position:
            await self.bot.db.execute(
                "UPDATE roles set position = $1 where id = $2", after.position, after.id
            )
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "roles",
                "UPDATE_ROLE_POSITION",
                str(before.position),
                str(after.position),
                datetime.now().replace(tzinfo=None),
                str(after.id),
            )

    @Cog.listener("on_voice_state_update")
    async def voice_state_update(self, member, before, after) -> None:
        if before.afk != after.afk:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "voice_state",
                "UPDATE_VOICE_STATE_AFK",
                str(before.afk),
                str(after.afk),
                datetime.now().replace(tzinfo=None),
                str(member.id),
            )
        if before.channel != after.channel:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "voice_state",
                "UPDATE_VOICE_STATE_CHANNEL",
                str(before.channel),
                str(after.channel),
                datetime.now().replace(tzinfo=None),
                str(member.id),
            )
        if before.deaf != after.deaf:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "voice_state",
                "UPDATE_VOICE_STATE_DEAF",
                str(before.deaf),
                str(after.deaf),
                datetime.now().replace(tzinfo=None),
                str(member.id),
            )
        if before.mute != after.mute:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "voice_state",
                "UPDATE_VOICE_STATE_MUTE",
                str(before.mute),
                str(after.mute),
                datetime.now().replace(tzinfo=None),
                str(member.id),
            )
        if before.self_deaf != after.self_deaf:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "voice_state",
                "UPDATE_VOICE_STATE_SELF_DEAF",
                str(before.self_deaf),
                str(after.self_deaf),
                datetime.now().replace(tzinfo=None),
                str(member.id),
            )
        if before.self_mute != after.self_mute:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "voice_state",
                "UPDATE_VOICE_STATE_SELF_MUTE",
                str(before.self_mute),
                str(after.self_mute),
                datetime.now().replace(tzinfo=None),
                str(member.id),
            )
        if before.self_stream != after.self_stream:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "voice_state",
                "UPDATE_VOICE_STATE_SELF_STREAM",
                str(before.self_stream),
                str(after.self_stream),
                datetime.now().replace(tzinfo=None),
                str(member.id),
            )
        if before.self_video != after.self_video:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "voice_state",
                "UPDATE_VOICE_STATE_SELF_VIDEO",
                str(before.self_video),
                str(after.self_video),
                datetime.now().replace(tzinfo=None),
                str(member.id),
            )
        if before.suppress != after.suppress:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                "voice_state",
                "UPDATE_VOICE_STATE_SUPPRESS",
                str(before.suppress),
                str(after.suppress),
                datetime.now().replace(tzinfo=None),
                str(member.id),
            )

    @tasks.loop(hours=24)
    async def stats_loop(self) -> None:
        logging.info("Starting daily server activity stats gathering")
        message = ""

        # Refresh materialized views before querying them
        try:
            await self.bot.db.refresh_materialized_views()
            logging.info("Refreshed materialized views")
        except Exception as e:
            logging.error(f"Failed to refresh materialized views: {e}")

        # Query the materialized view instead of the raw tables
        messages_result = await self.bot.db.fetch(
            """         
            SELECT total, channel_name as "Channel"
            FROM daily_message_stats
            WHERE server_id = 346842016480755724
            ORDER BY total DESC
            """
        )

        if not messages_result:
            length = 6
            logging.error(
                f"No messages found in guild 346842016480755724 during the last {datetime.now() - timedelta(hours=24)} - {datetime.now()}"
            )
            owner = self.bot.get_user(self.bot.owner_id)
            if owner is not None:
                await owner.send(
                    f"No messages found in guild 346842016480755724 during the last {datetime.now() - timedelta(hours=24)} - {datetime.now()}"
                )
            else:
                logging.error("I couldn't find the owner")
        else:
            logging.debug(f"Found results {messages_result}")
            length = len(str(messages_result[0]["total"])) + 1
            message += "==== Stats last 24 hours ====\n"
            message += "==== Messages stats ====\n"
            logging.debug(f"Build message {message}")
            for result in messages_result:
                try:
                    message += f"{result['total']:<{length}}:: {result['Channel']}\n"
                except Exception as e:
                    logging.error(f"{type(e).__name__} - {e}")
            logging.debug("requesting leave/join stats")

        # Query the materialized view for join/leave stats
        user_join_leave_results = await self.bot.db.fetchrow(
            """         
            SELECT joins as "join", leaves as "leave"
            FROM daily_member_stats
            WHERE server_id = 346842016480755724
            """
        )
        logging.debug(f"Found stats {user_join_leave_results}")

        if user_join_leave_results is not None:
            message += (
                f"==== Memeber stats ====\n"
                f"{user_join_leave_results['join']:<{length}}:: Joined\n"
                f"{user_join_leave_results['leave']:<{length}}:: Left"
            )
        else:
            logging.warning("No join/leave stats found")
            message += "==== Memeber stats ====\nNo join/leave data available\n"
        logging.debug(f"Built message {message}")
        channel = self.bot.get_channel(871486325692432464)
        if channel is None:
            logging.error("Could not find channel to post stats to 871486325692432464")
        else:
            logging.debug(f"Found channel {channel.name}")
            if len(message) > 1900:
                logging.debug("Message longer than 1900 characters")
                str_list = [message[i : i + 1900] for i in range(0, len(message), 1900)]
                for string in str_list:
                    await channel.send(f"```asciidoc\n{string}\n```")
                    await asyncio.sleep(0.5)
            else:
                try:
                    await channel.send(f"```asciidoc\n{message}\n```")
                except Exception as e:
                    logging.error(
                        f"Could not post stats_loop to channel {channel.name} - {e}"
                    )
            logging.info("Daily stats report done")

    @app_commands.command(
        name="messagecount",
        description="Retrieve message count from a channel in the last x hours",
    )
    @handle_interaction_errors
    async def message_count(
        self, interaction: discord.Interaction, channel: discord.TextChannel, hours: int
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

            embed.add_field(
                name="Since",
                value=f"{d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            # Add rate information if there are messages
            if message_count > 0:
                rate_per_hour = message_count / hours
                embed.add_field(
                    name="Average Rate",
                    value=f"{rate_per_hour:.2f} messages/hour",
                    inline=True,
                )

            embed.set_footer(text=f"Requested by {interaction.user.display_name}")

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(
                f"Failed to retrieve message count for channel {channel.name}"
            ) from e
        except Exception as e:
            raise QueryError("Unexpected error during message count query") from e


async def setup(bot) -> None:
    await bot.add_cog(StatsCogs(bot))

import asyncio
import logging
from datetime import datetime, timedelta

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
from discord.ext.commands import Cog

import config
from utils.permissions import admin_or_me_check, admin_or_me_check_wrapper, app_admin_or_me_check


async def save_reaction(self, reaction: discord.Reaction):
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
                    (emoji_str, reaction.message.id, user.id, None, False, None, None, current_time, False)
                    for user in users
                ]

                # Execute batch insert
                await self.bot.db.execute_many(
                    """
                    INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                    ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                    """,
                    reaction_data
                )

            case _ if reaction.is_custom_emoji():
                # Custom emoji
                reaction_data = [
                    (None, reaction.message.id, user.id, reaction.emoji.name, reaction.emoji.animated, 
                     reaction.emoji.id, f"https://cdn.discordapp.com/emojis/{reaction.emoji.id}.{'gif' if reaction.emoji.animated else 'png'}", 
                     current_time, reaction.is_custom_emoji())
                    for user in users
                ]

                # Execute batch insert
                await self.bot.db.execute_many(
                    """
                    INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                    ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                    """,
                    reaction_data
                )

            case _:
                # Fallback for other emoji types
                reaction_data = [
                    (reaction.emoji.name, reaction.message.id, user.id, reaction.emoji.name, None, None, None, current_time, reaction.emoji.is_custom_emoji())
                    for user in users
                ]

                # Execute batch insert
                await self.bot.db.execute_many(
                    """
                    INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                    ON CONFLICT (message_id, user_id, unicode_emoji) DO UPDATE SET removed = FALSE
                    """,
                    reaction_data
                )

    except Exception as e:
        logging.error(f"Failed to batch insert reactions into db: {e}")


async def save_message(self, message):
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
    if not hasattr(self, 'save_message_stmt'):
        self.save_message_stmt = await self.bot.db.prepare_statement(
            "save_message",
            "INSERT INTO messages(message_id, created_at, content, user_name, server_name, server_id, channel_id, "
            "channel_name, user_id, user_nick, jump_url, is_bot, deleted, reference) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)"
        )

    if not hasattr(self, 'save_user_stmt'):
        self.save_user_stmt = await self.bot.db.prepare_statement(
            "save_user",
            "INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4)"
        )

    if not hasattr(self, 'save_user_mention_stmt'):
        self.save_user_mention_stmt = await self.bot.db.prepare_statement(
            "save_user_mention",
            "INSERT INTO mentions(message_id, user_mention) VALUES ($1,$2)"
        )

    if not hasattr(self, 'save_role_mention_stmt'):
        self.save_role_mention_stmt = await self.bot.db.prepare_statement(
            "save_role_mention",
            "INSERT INTO mentions(message_id, role_mention) VALUES ($1,$2)"
        )

    # Use transaction for related operations
    try:
        async with self.bot.db.transaction():
            # Insert message using prepared statement
            await self.save_message_stmt.execute(
                message.id, message.created_at.replace(tzinfo=None), message.content, message.author.name,
                message.guild.name, message.guild.id, message.channel.id, message.channel.name,
                message.author.id, nick, message.jump_url, message.author.bot, False, reference
            )

            # Batch insert mentions if any
            if mentions:
                await self.bot.db.execute_many(
                    "INSERT INTO mentions(message_id, user_mention) VALUES ($1,$2)",
                    mentions
                )

            # Batch insert role mentions if any
            if role_mentions:
                await self.bot.db.execute_many(
                    "INSERT INTO mentions(message_id, role_mention) VALUES ($1,$2)",
                    role_mentions
                )
    except asyncpg.exceptions.UniqueViolationError:
        logging.error(f"{message.id} already in DB")
    except asyncpg.exceptions.ForeignKeyViolationError as e:
        logging.error(f"{e}")
        # If user doesn't exist, create it and then insert the message
        try:
            async with self.bot.db.transaction():
                # Insert user using prepared statement
                await self.save_user_stmt.execute(
                    message.author.id, message.author.created_at.replace(tzinfo=None), 
                    message.author.bot, message.author.name
                )

                # Insert message using prepared statement
                await self.save_message_stmt.execute(
                    message.id, message.created_at.replace(tzinfo=None), message.content, message.author.name,
                    message.guild.name, message.guild.id, message.channel.id, message.channel.name,
                    message.author.id, nick, message.jump_url, message.author.bot, False, reference
                )

                # Batch insert mentions if any
                if mentions:
                    await self.bot.db.execute_many(
                        "INSERT INTO mentions(message_id, user_mention) VALUES ($1,$2)",
                        mentions
                    )

                # Batch insert role mentions if any
                if role_mentions:
                    await self.bot.db.execute_many(
                        "INSERT INTO mentions(message_id, role_mention) VALUES ($1,$2)",
                        role_mentions
                    )
        except Exception as e:
            logging.error(f"Error saving message after user creation: {e}")


class StatsCogs(commands.Cog, name="stats"):

    def __init__(self, bot):
        self.bot = bot
        if config.logfile != "test":
            self.stats_loop.start()

    @commands.command(
        name="save_users",
        hidden=True
    )
    @commands.is_owner()
    async def save_users(self, ctx):
        await ctx.message.delete()
        try:
            for guild in self.bot.guilds:
                logging.info(f"Fetching members list")
                members_list = guild.members

                # Get all member IDs for this batch
                member_ids = [member.id for member in members_list]

                # Query only the relevant user IDs in a single query
                existing_user_ids = await self.bot.db.fetch(
                    "SELECT user_id FROM users WHERE user_id = ANY($1)",
                    member_ids
                )
                existing_user_ids_set = {row['user_id'] for row in existing_user_ids}

                # Query only the relevant membership IDs in a single query
                existing_memberships = await self.bot.db.fetch(
                    "SELECT user_id FROM server_membership WHERE user_id = ANY($1) AND server_id = $2",
                    member_ids, guild.id
                )
                existing_memberships_set = {row['user_id'] for row in existing_memberships}

                # Prepare batch operations
                users_to_add = []
                memberships_to_add = []

                for member in members_list:
                    if member.id not in existing_user_ids_set:
                        users_to_add.append((
                            member.id, 
                            member.created_at.replace(tzinfo=None), 
                            member.bot,
                            member.name
                        ))
                        memberships_to_add.append((member.id, member.guild.id))
                        logging.info(f"Added {member.name} - {member.id}")
                    elif member.id not in existing_memberships_set:
                        memberships_to_add.append((member.id, member.guild.id))

                # Execute batch operations
                if users_to_add:
                    await self.bot.db.execute_many(
                        "INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4)",
                        users_to_add
                    )

                if memberships_to_add:
                    await self.bot.db.execute_many(
                        "INSERT INTO server_membership(user_id, server_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                        memberships_to_add
                    )
        except Exception as e:
            logging.exception(f'{type(e).__name__} - {e}')
        await ctx.send("Done!")

    @commands.command(
        name="save_servers",
        hidden=True
    )
    @commands.is_owner()
    async def save_servers(self, ctx):
        for guild in self.bot.guilds:
            await self.bot.db.execute(
                "INSERT INTO servers(server_id, server_name, creation_date) VALUES ($1,$2,$3)"
                " ON CONFLICT (server_id) DO NOTHING ",
                guild.id, guild.name, guild.created_at.replace(tzinfo=None))
        await ctx.send("Done")

    @commands.command(
        name="save_channels",
        hidden=True
    )
    @commands.is_owner()
    async def save_channels(self, ctx):
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                try:
                    await self.bot.db.execute("INSERT INTO "
                                                  "channels(id, name, category_id, created_at, guild_id, position, topic, is_nsfw) "
                                                  "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                                                  channel.id, channel.name, channel.category_id,
                                                  channel.created_at.replace(tzinfo=None),
                                                  channel.guild.id, channel.position, channel.topic,
                                                  channel.is_nsfw())
                except Exception as e:
                    logging.error(f'{type(e).__name__} - {e}')
                except asyncpg.UniqueViolationError:
                    logging.debug("Already in DB")
        await ctx.send("Done")

    @commands.command(
        name="save_emotes",
        hidden=True
    )
    @commands.is_owner()
    async def save_emotes(self, ctx):
        for guild in self.bot.guilds:
            for emotes in guild.emojis:
                emote = self.bot.get_emoji(emotes.id)
                await self.bot.db.execute(''' 
                    INSERT INTO emotes(guild_id, emote_id, name, animated, managed) 
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT (emote_id) 
                    DO UPDATE SET name = $3, animated = $4, managed = $5 WHERE emotes.name != $3 OR emotes.animated != $4 OR emotes.managed != $5
                    ''', guild.id, emote.id, emote.name, emote.animated, emote.managed)
        owner = self.bot.get_user(self.bot.owner_id)
        if owner is not None:
            await owner.send('The save command is now complete')
        else:
            logging.error(f"I couldn't find the owner")



    @commands.command(
        name="save_categories",
        hidden=True
    )
    @commands.is_owner()
    async def save_categories(self, ctx):
        for guild in self.bot.guilds:
            for category in guild.categories:
                try:
                    await self.bot.db.execute("INSERT INTO "
                                                  "categories(id, name, created_at, guild_id, position, is_nsfw) "
                                                  "VALUES ($1,$2,$3,$4,$5,$6)",
                                                  category.id, category.name,
                                                  category.created_at.replace(tzinfo=None),
                                                  category.guild.id, category.position, category.is_nsfw())
                except Exception as e:
                    logging.error(f'{type(e).__name__} - {e}')
                except asyncpg.UniqueViolationError:
                    logging.debug("Already in DB")
        await ctx.send("Done")

    @commands.command(
        name="save_threads",
        hidden=True
    )
    @commands.is_owner()
    async def save_threads(self, ctx):
        for guild in self.bot.guilds:
            for thread in guild.threads:
                try:
                    await self.bot.db.execute("INSERT INTO "
                                                  "threads(id, guild_id, parent_id, owner_id, slowmode_delay, archived, locked, archiver_id, auto_archive_duration, is_private, name, deleted) "
                                                  "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
                                                  thread.id, thread.guild.id, thread.parent_id, thread.owner_id,
                                                  thread.slowmode_delay, thread.archived, thread.locked,
                                                  thread.archiver_id,
                                                  thread.auto_archive_duration, thread.is_private(), thread.name, False)
                except asyncpg.UniqueViolationError:
                    pass
                except Exception:
                    logging.exception("Save_threads")
        await ctx.send("Done")

    @commands.command(
        name="save_roles",
        hidden=True
    )
    @commands.is_owner()
    async def save_roles(self, ctx):
        for guild in self.bot.guilds:
            logging.debug(f"{guild=}")
            for role in guild.roles:
                logging.debug(f"{role=}")
                if role.is_default():
                    continue
                try:
                    await self.bot.db.execute("INSERT INTO "
                                                  "roles(id, name, color, created_at, hoisted, managed, position, guild_id) "
                                                  "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                                                  role.id, role.name, str(role.color),
                                                  role.created_at.replace(tzinfo=None), role.hoist,
                                                  role.managed, role.position, guild.id)
                except asyncpg.UniqueViolationError:
                    logging.debug(f"Role already in DB")
                for member in role.members:
                    try:
                        await self.bot.db.execute("INSERT INTO role_membership(user_id, role_id) VALUES($1,$2)",
                                                      member.id, role.id)
                    except asyncpg.UniqueViolationError:
                        logging.debug(f"connection already in DB {member} - {role}")
        await ctx.send("Done")

    @commands.command(
        name="update_role_color",
        hidden=True
    )
    @commands.is_owner()
    async def update_role_color(self, ctx):
        for guild in self.bot.guilds:
            for role in guild.roles:
                if role.is_default():
                    continue
                await self.bot.db.execute("UPDATE roles SET color = $1 WHERE id = $2", str(role.color), role.id)
        await ctx.send("Done")

    @commands.command(
        name="save_users_from_join_leave",
        hidden=True
    )
    @commands.is_owner()
    async def save_users_from_join_leave(self, ctx):
        jn_users = await self.bot.db.fetch("SELECT user_id,created_at FROM join_leave")
        for user in jn_users:
            logging.debug(user)
            try:
                await self.bot.db.execute("INSERT INTO "
                                              "users(user_id, created_at, bot, username) "
                                              "VALUES($1,$2,$3,$4)",
                                              user['user_id'], user['created_at'], False, user['user_name'])

            except asyncpg.UniqueViolationError:
                logging.debug("Users already in DB")
        await ctx.send("Done")

    @commands.command(
        name="save_channels_from_messages",
        hidden=True
    )
    @commands.is_owner()
    async def save_users_from_messages(self, ctx):
        m_channels = await self.bot.db.fetch("""SELECT reactions.message_id FROM reactions
                                                    LEFT JOIN messages m on reactions.message_id = m.message_id
                                                    WHERE m.message_id IS NULL
                                                    GROUP BY reactions.message_id""")
        for channel in m_channels:
            try:
                message = await self.bot.fetch_message(channel['message_id'])
                logging.info(f"{message}")
                await self.bot.db.execute("INSERT INTO users(user_id, username, bot) VALUES($1,$2,$3)",
                                              channel['user_id'], channel['user_name'], channel['is_bot'])
                logging.info(f"inserting {channel}")
            except Exception as e:
                logging.info(f"{e}")
        await ctx.send("Done")

    @commands.command(
        name="save",
        hidden=True
    )
    @commands.is_owner()
    async def save(self, ctx):
        try:
            await ctx.message.delete()
        except:
            pass
        logging.info(f"starting save")
        for guild in self.bot.guilds:
            logging.debug(f"{guild=}")

            # Get all text channels with read permissions
            accessible_channels = [
                channel for channel in guild.text_channels 
                if channel.permissions_for(channel.guild.me).read_message_history
            ]

            if not accessible_channels:
                logging.info(f"No accessible channels found in guild {guild.name}")
                continue

            # Get channel IDs
            channel_ids = [channel.id for channel in accessible_channels]

            # Batch query for last messages in all channels
            last_messages = await self.bot.db.fetch(
                'SELECT channel_id, MAX(created_at) AS created_at FROM messages WHERE channel_id = ANY($1) GROUP BY channel_id',
                channel_ids
            )

            # Create a dictionary for quick lookup
            last_message_dict = {row['channel_id']: row['created_at'] for row in last_messages}

            # Default date for channels with no messages
            default_date = datetime.strptime('2015-01-01', '%Y-%m-%d')

            # Process each channel with the pre-fetched data
            for channel in accessible_channels:
                logging.debug(f"{channel=}")
                logging.info(f"Starting with {channel.name}")

                # Get the last message date or use default
                first = last_message_dict.get(channel.id, default_date)
                logging.info(f"Last message at {first}")

                count = 0
                async for message in channel.history(limit=None, after=first, oldest_first=True):
                    logging.debug(f"Saving {message.id} to database")
                    count += 1
                    await save_message(self, message)
                logging.info(f"{channel.name} Done. saved {count} messages")
            logging.info("\n\nStarting with threads\n")

            # Get all threads with read permissions
            accessible_threads = [
                thread for thread in guild.threads 
                if thread.permissions_for(thread.guild.me).read_message_history
            ]

            if not accessible_threads:
                logging.info(f"No accessible threads found in guild {guild.name}")
                continue

            # Get thread IDs
            thread_ids = [thread.id for thread in accessible_threads]

            # Batch query for last messages in all threads
            last_thread_messages = await self.bot.db.fetch(
                'SELECT channel_id, MAX(created_at) AS created_at FROM messages WHERE channel_id = ANY($1) GROUP BY channel_id',
                thread_ids
            )

            # Create a dictionary for quick lookup
            last_thread_message_dict = {row['channel_id']: row['created_at'] for row in last_thread_messages}

            # Default date for threads with no messages
            default_date = datetime.strptime('2015-01-01', '%Y-%m-%d')

            # Process each thread with the pre-fetched data
            for thread in accessible_threads:
                logging.debug(f"{thread=}")
                logging.info(f"Starting with {thread.name}")

                # Get the last message date or use default
                first = last_thread_message_dict.get(thread.id, default_date)
                logging.info(f"Last message at {first}")

                count = 0
                async for message in thread.history(limit=None, after=first, oldest_first=True):
                    logging.debug(f"Saving {message.id} to database")
                    count += 1
                    await save_message(self, message)
                    await asyncio.sleep(0.05)
                logging.info(f"{thread.name} Done. saved {count} messages")
        logging.info("!save completed")
        owner = self.bot.get_user(self.bot.owner_id)
        if owner is not None:
            await owner.send('The save command is now complete')
        else:
            logging.error(f"I couldn't find the owner")
        if self.save_listener not in self.bot.extra_events['on_message']:
            self.bot.add_listener(self.save_listener, name='on_message')
        if self.message_deleted not in self.bot.extra_events['on_raw_message_delete']:
            self.bot.add_listener(self.message_deleted, name='on_raw_message_delete')
        if self.message_edited not in self.bot.extra_events['on_raw_message_edit']:
            self.bot.add_listener(self.message_edited, name='on_raw_message_edit')
        if self.reaction_add not in self.bot.extra_events['on_raw_reaction_add']:
            self.bot.add_listener(self.reaction_add, name='on_raw_reaction_add')
        if self.reaction_remove not in self.bot.extra_events['on_raw_reaction_remove']:
            self.bot.add_listener(self.reaction_remove, name='on_raw_reaction_remove')

    @Cog.listener("on_message")
    async def save_listener(self, message):
        if not isinstance(message.channel, discord.channel.DMChannel):
            try:
                await save_message(self, message)
            except Exception as e:
                logging.error(f"Error: {e} on message save")

    @Cog.listener("on_raw_message_edit")
    async def message_edited(self, message):
        try:
            if 'content' in message.data and 'edited_timestamp' in message.data and message.data['edited_timestamp'] is not None:
                logging.debug(f"message edited {message}")
                old_content = await self.bot.db.fetchval(
                    "SELECT content FROM messages where message_id = $1 LIMIT 1",
                    int(message.data['id']))
                logging.debug(old_content)
                await self.bot.db.execute(
                    "INSERT INTO message_edit(id, old_content, new_content, edit_timestamp) VALUES ($1,$2,$3,$4)",
                    int(message.data['id']), old_content, message.data['content'],
                    datetime.fromisoformat(message.data['edited_timestamp']).replace(tzinfo=None))
                logging.debug("post insert")
                await self.bot.db.execute("UPDATE messages set content = $1 WHERE message_id = $2",
                                              message.data['content'], int(message.data['id']))
                logging.debug("post update")
        except:
            logging.exception(f"message_edited - {message.data}")

    @Cog.listener("on_raw_message_delete")
    async def message_deleted(self, message):

        await self.bot.db.execute("UPDATE public.messages SET deleted = true WHERE message_id = $1",
                                      message.message_id)

    @Cog.listener("on_raw_reaction_add")
    async def reaction_add(self, reaction):
        try:
            current_time = datetime.now().replace(tzinfo=None)

            # Use transaction for consistency
            async with self.bot.db.transaction():
                if reaction.emoji.is_custom_emoji():
                    await self.bot.db.execute(
                        """
                        INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                        ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                        """,
                        None, reaction.message_id, reaction.user_id,
                        reaction.emoji.name, reaction.emoji.animated, reaction.emoji.id,
                        f"https://cdn.discordapp.com/emojis/{reaction.emoji.id}.{'gif' if reaction.emoji.animated else 'png'}",
                        current_time, reaction.emoji.is_custom_emoji()
                    )
                elif isinstance(reaction.emoji, str):
                    await self.bot.db.execute(
                        """
                        INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                        ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                        """,
                        reaction.emoji, reaction.message_id, reaction.user_id,
                        None, False, None, None, current_time, False
                    )
                else:
                    await self.bot.db.execute(
                        """
                        INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                        ON CONFLICT (message_id, user_id, unicode_emoji) DO UPDATE SET removed = FALSE
                        """,
                        reaction.emoji.name, reaction.message_id, reaction.user_id,
                        reaction.emoji.name, None, None,
                        None, current_time, reaction.emoji.is_custom_emoji()
                    )
        except Exception as e:
            logging.exception(f"Error: {e} on reaction add")

    @Cog.listener("on_raw_reaction_remove")
    async def reaction_remove(self, reaction):
        try:
            # Use transaction for consistency
            async with self.bot.db.transaction():
                if reaction.emoji.is_custom_emoji():
                    await self.bot.db.execute(
                        """
                        UPDATE reactions
                        SET removed = TRUE 
                        WHERE message_id = $1 AND user_id = $2 AND emoji_id = $3
                        """,
                        reaction.message_id, reaction.user_id, reaction.emoji.id
                    )
                else:
                    await self.bot.db.execute(
                        """
                        UPDATE reactions
                        SET removed = TRUE 
                        WHERE message_id = $1 AND user_id = $2 AND unicode_emoji = $3
                        """,
                        reaction.message_id, reaction.user_id, reaction.emoji.name
                    )

                # Log the removal for analytics
                await self.bot.db.execute(
                    """
                    INSERT INTO updates(updated_table, action, before, after, date, primary_key) 
                    VALUES($1, $2, $3, $4, $5, $6)
                    """,
                    "reactions", "REACTION_REMOVED", 
                    f"message_id:{reaction.message_id},user_id:{reaction.user_id}", 
                    "removed=TRUE", 
                    datetime.now().replace(tzinfo=None),
                    f"{reaction.message_id}:{reaction.user_id}"
                )
        except Exception as e:
            logging.error(f"Error: {e} on reaction remove")

    @Cog.listener("on_member_join")
    async def member_join(self, member):
        await self.bot.db.execute("INSERT INTO join_leave VALUES($1,$2,$3,$4,$5,$6)",
                                      member.id, datetime.now(), "JOIN",
                                      member.guild.name, member.guild.id, member.created_at.replace(tzinfo=None))
        try:
            await self.bot.db.execute("INSERT INTO "
                                          "users(user_id, created_at, bot, username) "
                                          "VALUES($1,$2,$3,$4) ON CONFLICT (user_id) DO UPDATE SET username = $4",
                                          member.id, member.created_at.replace(tzinfo=None), member.bot,
                                          member.name)
            await self.bot.db.execute(
                "INSERT INTO server_membership(user_id, server_id) VALUES ($1,$2)",
                member.id, member.guild.id)
        except asyncpg.UniqueViolationError:
            logging.error("Failed to insert user into server_membership")
        except Exception as e:
            channel = self.bot.get_channel(297916314239107072)
            await channel.send(f"{e}")

    @Cog.listener("on_member_remove")
    async def member_remove(self, member):
        await self.bot.db.execute("DELETE FROM server_membership WHERE user_id = $1 AND server_id = $2",
                                      member.id, member.guild.id)
        await self.bot.db.execute("DELETE FROM role_membership WHERE role_id IN (SELECT id FROM roles WHERE guild_id = $2) AND user_id = $1",
                                      member.id, member.guild.id)
        await self.bot.db.execute("INSERT INTO join_leave VALUES($1,$2,$3,$4,$5,$6)",
                                      member.id, datetime.now(), "LEAVE", member.guild.name, member.guild.id, member.created_at.replace(tzinfo=None))

    @Cog.listener("on_member_update")
    async def member_roles_update(self, before, after):
        if before.roles != after.roles:
            if len(before.roles) < len(after.roles):
                gained = set(after.roles) - set(before.roles)
                gained = gained.pop()
                try:
                    await self.bot.db.execute("INSERT INTO role_membership(user_id, role_id) VALUES($1,$2)",
                                                  after.id, gained.id)
                    await self.bot.db.execute("INSERT INTO role_history(role_id, user_id, date) VALUES($1,$2,$3)",
                                                  gained.id, after.id, datetime.now().replace(tzinfo=None))
                except asyncpg.exceptions.ForeignKeyViolationError:
                    await self.bot.db.execute("INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4)",
                                                  after.id, after.created_at.replace(tzinfo=None), after.bot, after.name)
                    await self.bot.db.execute("INSERT INTO role_membership(user_id, role_id) VALUES($1,$2)",
                                                  after.id, gained.id)
                except asyncpg.exceptions.UniqueViolationError:
                    logging.warning(f"Duplicate key value violation {after.id}, {gained.id}")
            else:
                lost = set(before.roles) - set(after.roles)
                lost = lost.pop()
                await self.bot.db.execute("DELETE FROM role_membership WHERE user_id = $1 AND role_id = $2",
                                              after.id, lost.id)
                await self.bot.db.execute("INSERT INTO role_history(role_id, user_id, date, gained) VALUES($1,$2,$3,FALSE)",
                                              lost.id, after.id, datetime.now().replace(tzinfo=None))
                if lost.id == 585789843368574997:
                    pink_role = after.guild.get_role(690373096099545168)
                    after.remove_roles(pink_role)

    @Cog.listener("on_user_update")
    async def user_update(self, before, after):
        if before.name != after.name:
            try:
                await self.bot.db.execute("UPDATE users SET username = $1 WHERE user_id = $2",
                                              after.name, after.id)

                await self.bot.db.execute(
                    'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                    "users", "UPDATE_USERNAME", before.name, after.name, datetime.now().replace(tzinfo=None),
                    str(after.id))
            except Exception as e:
                logging.error(f"Error {e}")

    @Cog.listener("on_guild_channel_create")
    async def guild_channel_create(self, channel):
        if channel.type == discord.ChannelType.text:
            try:
                await self.bot.db.execute("INSERT INTO "
                                              "channels(id, name, category_id, created_at, guild_id, position, topic, is_nsfw) "
                                              "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                                              channel.id, channel.name, channel.category_id,
                                              channel.created_at.replace(tzinfo=None),
                                              channel.guild.id, channel.position, channel.topic,
                                              channel.is_nsfw())
            except Exception as e:
                logging.error(f"{e}")
        elif channel.type == discord.ChannelType.category:
            try:
                await self.bot.db.execute(
                    "INSERT INTO categories(id, name, created_at, guild_id, position, is_nsfw) VALUES($1,$2,$3,$4,$5,$6)",
                    channel.id, channel.name, channel.created_at.replace(tzinfo=None), channel.guild_id,
                    channel.position,
                    channel.is_nsfw())
            except Exception as e:
                logging.error(f"{e}")

    @Cog.listener("on_guild_channel_delete")
    async def guild_channel_delete(self, channel):
        await self.bot.db.execute("UPDATE channels set deleted = TRUE where id = $1",
                                      channel.id)
        await self.bot.db.execute("UPDATE messages SET deleted = TRUE where channel_id = $1",
                                      channel.id)
        await self.bot.db.execute(
            'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
            "channel", "DELETED_CHANNEL", channel.name, channel.name, datetime.now().replace(tzinfo=None),
            str(channel.id))

    @Cog.listener("on_thread_create")
    async def thread_created(self, thread):
        logging.info(f"A new thread has been created: {thread}")
        try:
            await self.bot.db.execute("INSERT INTO "
                                          "threads(id, guild_id, parent_id, owner_id, slowmode_delay, archived, locked, archiver_id, auto_archive_duration, is_private, name, deleted) "
                                          "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
                                          thread.id, thread.guild.id, thread.parent_id, thread.owner_id,
                                          thread.slowmode_delay, thread.archived, thread.locked, thread.archiver_id,
                                          thread.auto_archive_duration, thread.is_private(), thread.name, False)
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_CREATED", thread.name, thread.name, datetime.now().replace(tzinfo=None), str(thread.id))
            if thread.parent_id != 1190045713778868335:
                await thread.send("<@&1153075640535367721>")
        except asyncpg.UniqueViolationError:
            logging.warning(f"Duplicate on {thread} in db")
        except Exception as e:
            logging.error(f"{e}")

    @Cog.listener("on_thread_delete")
    async def thread_deleted(self, thread):
        await self.bot.db.execute("UPDATE threads SET deleted = $2 WHERE id = $1",
                                      thread.id, True)
        await self.bot.db.execute("UPDATE messages SET deleted = $2 where channel_id = $1",
                                      thread.id, True)
        await self.bot.db.execute(
            "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
            "VALUES ($1,$2,$3,$4,$5,$6)",
            "threads", "THREAD_DELETED", thread.name, thread.name, datetime.now().replace(tzinfo=None), str(thread.id))

    @Cog.listener("on_thread_update")
    async def thread_update(self, before, after):
        if before.slowmode_delay != after.slowmode_delay:
            await self.bot.db.execute("UPDATE threads set slowmode_delay = $1 where id = $2",
                                          after.slowmode_delay, after.id)
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_SLOWMODE_UPDATED", str(before.slowmode_delay), str(after.slowmode_delay),
                datetime.now().replace(tzinfo=None), str(after.id))
        if before.archived != after.archived:
            if after.archiver_id:
                await self.bot.db.execute("UPDATE threads set archived = $1 where id = $2",
                                              after.archived, after.id)
            else:
                await self.bot.db.execute("UPDATE threads set archived = $1 AND archiver_id = $3 where id = $2",
                                              after.archived, after.id, after.archiver_id)
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_ARCHIVED_UPDATED", str(before.archived), str(after.archived),
                datetime.now().replace(tzinfo=None), str(after.id))
        if before.locked != after.locked:
            await self.bot.db.execute("UPDATE threads set locked = $1 where id = $2",
                                          after.locked, after.id)
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_LOCKED_UPDATED", str(before.locked), str(after.locked), datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.auto_archive_duration != after.auto_archive_duration:
            await self.bot.db.execute("UPDATE threads set auto_archive_duration = $1 where id = $2",
                                          after.auto_archive_duration, after.id)
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_AUTO_ARCHIVE_DURATION_UPDATED", str(before.auto_archive_duration),
                str(after.auto_archive_duration), datetime.now().replace(tzinfo=None), str(after.id))
        if before.is_private() != after.is_private():
            await self.bot.db.execute("UPDATE threads set is_private = $1 where id = $2",
                                          after.is_private(), after.id)
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_PRIVATE_UPDATED", str(before.is_private()), str(after.is_private()),
                datetime.now().replace(tzinfo=None), str(after.id))
        if before.name != after.name:
            await self.bot.db.execute("UPDATE threads set name = $1 where id = $2",
                                          after.name, after.id)
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_NAME_UPDATED", before.name, after.name, datetime.now().replace(tzinfo=None),
                str(after.id))

    @Cog.listener("on_thread_member_join")
    async def thread_member_join(self, threadmember):
        await self.bot.db.execute("INSERT INTO thread_membership(user_id, thread_id) VALUES($1,$2)",
                                      threadmember.id, threadmember.thread_id)

    @Cog.listener("on_thread_member_remove")
    async def thread_member_leave(self, threadmember):
        await self.bot.db.execute("DELETE FROM thread_membership WHERE user_id = $1 and thread_id = $2",
                                      threadmember.id, threadmember.thread_id)

    @Cog.listener("on_guild_channel_update")
    async def guild_channel_update(self, before, after):
        if before.name != after.name:
            await self.bot.db.execute("UPDATE channels set name = $1 where id = $2",
                                          after.name, after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_NAME", before.name, after.name, datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.category_id != after.category_id:
            await self.bot.db.execute("UPDATE channels set category_id = $1 where id = $2",
                                          after.category_id, after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_CATEGORY_ID", str(before.category_id), str(after.category_id),
                datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.position != after.position:
            await self.bot.db.execute("UPDATE channels set position = $1 where id = $2",
                                          after.position, after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_POSITION", str(before.position), str(after.position),
                datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.topic != after.topic:
            await self.bot.db.execute("UPDATE channels set topic = $1 where id = $2",
                                          after.topic, after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_TOPIC", before.topic, after.topic, datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.is_nsfw() != after.is_nsfw():
            await self.bot.db.execute("UPDATE channels set is_nsfw = $1 where id = $2",
                                          after.is_nsfw(), after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_IS_NSFW", str(before.is_nsfw()), str(after.is_nsfw()),
                datetime.now().replace(tzinfo=None),
                str(after.id))

    @Cog.listener("on_guild_update")
    async def guild_update(self, before, after):
        if before.name != after.name:
            await self.bot.db.execute("UPDATE servers set server_name = $1 WHERE server_id = $2",
                                          after.name, after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "servers", "UPDATE_SERVER_NAME", before.name, after.name, datetime.now().replace(tzinfo=None),
                str(after.id))

    @Cog.listener("on_guild_emojis_update")
    async def guild_emoji_update(self, guild, before, after):
        print(f"change detected {guild}, {before}, {after}")

        before_dict = {emoji.id: emoji for emoji in before}
        after_dict = {emoji.id: emoji for emoji in after}

        for id, emoji in before_dict.items():
            after_emoji = after_dict.get(id)
            if after_emoji is None:
                print(f"Emote removed: {emoji}")
                await self.bot.db.execute("DELETE FROM emotes where emote_id = $1", id)
                return
            elif emoji.name != after_emoji.name or emoji.animated != after_emoji.animated:
                print(f"Emote updated: {after_emoji}")
                await self.bot.db.execute("UPDATE emotes set name = $1, animated = $2, managed = $3  where emote_id = $4", after_emoji.name, after_emoji.animated, after_emoji.managed, id)
                return

        for id, emoji in after_dict.items():
            if id not in before_dict:
                print(f"Emote added: {emoji}")
                await self.bot.db.execute("INSERT INTO emotes(guild_id, emote_id, name, animated, managed) VALUES ($1,$2,$3,$4,$5)",
                                          guild.id, emoji.id,emoji.name, emoji.animated, emoji.managed)
                return

    @Cog.listener("on_guild_role_create")
    async def guild_role_create(self, role):
        await self.bot.db.execute("INSERT INTO "
                                      "roles(id, name, color, created_at, hoisted, managed, position, guild_id) "
                                      "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                                      role.id, role.name, str(role.color), role.created_at.replace(tzinfo=None),
                                      role.hoist,
                                      role.managed, role.position, role.guild.id)

    @Cog.listener("on_guild_role_delete")
    async def guild_role_delete(self, role):
        await self.bot.db.execute("UPDATE roles set deleted = TRUE where id = $1",
                                      role.id)
        await self.bot.db.execute("DELETE FROM role_membership WHERE role_id = $1", role.id)

    @Cog.listener("on_guild_role_update")
    async def guild_role_update(self, before, after):
        if before.name != after.name:
            await self.bot.db.execute("UPDATE roles set name = $1 where id = $2",
                                          after.name, after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "roles", "UPDATE_ROLE_NAME", before.name, after.name, datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.color != after.color:
            await self.bot.db.execute("UPDATE roles set color = $1 where id = $2",
                                          str(after.color), after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "roles", "UPDATE_ROLE_COLOR", str(before.color), str(after.color), datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.hoist != after.hoist:
            await self.bot.db.execute("UPDATE roles set hoisted = $1 where id = $2",
                                          after.hoist, after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "roles", "UPDATE_ROLE_HOISTED", str(before.hoist), str(after.hoist), datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.position != after.position:
            await self.bot.db.execute("UPDATE roles set position = $1 where id = $2",
                                          after.position, after.id)
            await self.bot.db.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "roles", "UPDATE_ROLE_POSITION", str(before.position), str(after.position),
                datetime.now().replace(tzinfo=None),
                str(after.id))

    @Cog.listener("on_voice_state_update")
    async def voice_state_update(self, member, before, after):
        if before.afk != after.afk:
            await self.bot.db.execute("INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                                          "voice_state", "UPDATE_VOICE_STATE_AFK", str(before.afk), str(after.afk), datetime.now().replace(tzinfo=None), str(member.id))
        if before.channel != after.channel:
            await self.bot.db.execute("INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                                          "voice_state", "UPDATE_VOICE_STATE_CHANNEL", str(before.channel), str(after.channel), datetime.now().replace(tzinfo=None), str(member.id))
        if before.deaf != after.deaf:
            await self.bot.db.execute("INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                                          "voice_state", "UPDATE_VOICE_STATE_DEAF", str(before.deaf), str(after.deaf), datetime.now().replace(tzinfo=None), str(member.id))
        if before.mute != after.mute:
            await self.bot.db.execute("INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                                          "voice_state", "UPDATE_VOICE_STATE_MUTE", str(before.mute), str(after.mute), datetime.now().replace(tzinfo=None), str(member.id))
        if before.self_deaf != after.self_deaf:
            await self.bot.db.execute("INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                                          "voice_state", "UPDATE_VOICE_STATE_SELF_DEAF", str(before.self_deaf), str(after.self_deaf), datetime.now().replace(tzinfo=None), str(member.id))
        if before.self_mute != after.self_mute:
            await self.bot.db.execute("INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                                          "voice_state", "UPDATE_VOICE_STATE_SELF_MUTE", str(before.self_mute), str(after.self_mute), datetime.now().replace(tzinfo=None), str(member.id))
        if before.self_stream != after.self_stream:
            await self.bot.db.execute("INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                                          "voice_state", "UPDATE_VOICE_STATE_SELF_STREAM", str(before.self_stream), str(after.self_stream), datetime.now().replace(tzinfo=None), str(member.id))
        if before.self_video != after.self_video:
            await self.bot.db.execute("INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                                          "voice_state", "UPDATE_VOICE_STATE_SELF_VIDEO", str(before.self_video), str(after.self_video), datetime.now().replace(tzinfo=None), str(member.id))
        if before.suppress != after.suppress:
            await self.bot.db.execute("INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                                          "voice_state", "UPDATE_VOICE_STATE_SUPPRESS", str(before.suppress), str(after.suppress), datetime.now().replace(tzinfo=None), str(member.id))

    @tasks.loop(hours=24)
    async def stats_loop(self):
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
            """)

        if not messages_result:
            length = 6
            logging.error(f"No messages found in guild 346842016480755724 during the last {datetime.now() - timedelta(hours=24)} - {datetime.now()}")
            owner = self.bot.get_user(self.bot.owner_id)
            if owner is not None:
                await owner.send(f"No messages found in guild 346842016480755724 during the last {datetime.now() - timedelta(hours=24)} - {datetime.now()}")
            else:
                logging.error(f"I couldn't find the owner")
        else:
            logging.debug(f"Found results {messages_result}")
            length = len(str(messages_result[0]['total'])) + 1
            message += "==== Stats last 24 hours ====\n"
            message += "==== Messages stats ====\n"
            logging.debug(f"Build message {message}")
            for result in messages_result:
                try:
                    message += f"{result['total']:<{length}}:: {result['Channel']}\n"
                except Exception as e:
                    logging.error(f'{type(e).__name__} - {e}')
            logging.debug("requesting leave/join stats")

        # Query the materialized view for join/leave stats
        user_join_leave_results = await self.bot.db.fetchrow(
            """         
            SELECT joins as "JOIN", leaves as "LEAVE"
            FROM daily_member_stats
            WHERE server_id = 346842016480755724
            """)
        logging.debug(f"Found stats {user_join_leave_results}")
        message += f"==== Memeber stats ====\n" \
                   f"{user_join_leave_results['JOIN']:<{length}}:: Joined\n" \
                   f"{user_join_leave_results['LEAVE']:<{length}}:: Left"
        logging.debug(f"Built message {message}")
        channel = self.bot.get_channel(871486325692432464)
        if channel is None:
            logging.error("Could not find channel to post stats to 871486325692432464")
        else:
            logging.debug(f"Found channel {channel.name}")
            if len(message) > 1900:
                logging.debug("Message longer than 1900 characters")
                str_list = [message[i:i + 1900] for i in range(0, len(message), 1900)]
                for string in str_list:
                    await channel.send(f"```asciidoc\n{string}\n```")
                    await asyncio.sleep(0.5)
            else:
                try:
                    await channel.send(f"```asciidoc\n{message}\n```")
                except Exception as e:
                    logging.error(f"Could not post stats_loop to channel {channel.name} - {e}")
            logging.info("Daily stats report done")

    @app_commands.command(
        name="messagecount",
        description="Retrieve message count from a channel in the last x hours",
    )
    async def message_count(self, interaction: discord.Interaction, channel: discord.TextChannel, hours: int):
        d_time = datetime.now() - timedelta(hours=hours)
        results = await self.bot.db.fetchrow(
            "SELECT count(*) total FROM messages WHERE created_at > $1 and channel_id = $2",
            d_time, channel.id)
        await interaction.response.send_message(f"There is a total of {results['total']} messages in channel {channel} since {d_time} UTC")


async def setup(bot):
    await bot.add_cog(StatsCogs(bot))

import asyncio
import logging
import typing
from datetime import datetime, timedelta

import asyncpg
import dateparser
import discord
from discord.ext import commands
from discord.ext import tasks
from discord.ext.commands import Cog

import secrets


def admin_or_me_check(ctx):
    role = discord.utils.get(ctx.guild.roles, id=346842813687922689)
    if ctx.message.author.id == 268608466690506753:
        return True
    elif role in ctx.message.author.roles:
        return True
    else:
        return False


async def save_reaction(self, reaction):
    if type(reaction.emoji) == discord.partial_emoji.PartialEmoji or type(reaction.emoji) == discord.emoji.Emoji:
        emoji = None
        name = reaction.emoji.name
        animated = reaction.emoji.animated
        emoji_id = reaction.emoji.id
        url = reaction.emoji.url
    else:
        emoji = reaction.emoji
        name = None
        animated = False
        emoji_id = None
        url = None
    try:
        for user in await reaction.users().flatten():
            await self.bot.pg_con.execute("INSERT INTO reactions "
                                          "VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
                                          emoji,
                                          reaction.message.id, user.id,
                                          name, animated, emoji_id, str(url), datetime.now().replace(tzinfo=None))
    except Exception as e:
        logging.error(f"Failed to insert reaction into db. {e}")


async def save_message(self, message):
    for mention in message.mentions:
        await self.bot.pg_con.execute("INSERT INTO mentions(message_id, user_mention) VALUES ($1,$2)",
                                      message.id, mention.id)

    for role_mention in message.role_mentions:
        await self.bot.pg_con.execute("INSERT INTO mentions(message_id, role_mention) VALUES ($1,$2)",
                                      message.id, role_mention.id)

    # if message.attachments:
    #     for attachment in message.attachments:
    #         await self.bot.pg_con.execute("INSERT INTO attachments "
    #                                       "VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
    #                                       attachment.id, attachment.filename, attachment.url,
    #                                       attachment.size, attachment.height, attachment.width,
    #                                       attachment.is_spoiler(), message.id)

    # if message.reactions:
    #     for reaction in message.reactions:
    #         await save_reaction(self, reaction)

    try:
        nick = message.author.nick
    except AttributeError:
        nick = ""

    try:
        reference = message.reference.message_id
    except AttributeError:
        reference = None

    try:
        await self.bot.pg_con.execute(
            "INSERT INTO messages(message_id, created_at, content, user_name, server_name, server_id, channel_id, "
            "channel_name, user_id, user_nick, jump_url, is_bot, deleted, reference) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",
            message.id, message.created_at.replace(tzinfo=None), message.content, message.author.name,
            message.guild.name,
            message.guild.id, message.channel.id, message.channel.name,
            message.author.id, nick,
            message.jump_url, message.author.bot, False, reference)
    except asyncpg.exceptions.UniqueViolationError:
        logging.error(f"{message.id} already in DB")
    except asyncpg.exceptions.ForeignKeyViolationError as e:
        logging.error(f"{e}")
        await self.bot.pg_con.execute(
            "INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4)",
            message.author.id, message.author.created_at.replace(tzinfo=None), message.author.bot,
            message.author.name
        )
        await self.bot.pg_con.execute(
            "INSERT INTO messages(message_id, created_at, content, user_name, server_name, server_id, channel_id, "
            "channel_name, user_id, user_nick, jump_url, is_bot, deleted, reference) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",
            message.id, message.created_at.replace(tzinfo=None), message.content, message.author.name,
            message.guild.name,
            message.guild.id, message.channel.id, message.channel.name,
            message.author.id, nick,
            message.jump_url, message.author.bot, False, reference)


class StatsCogs(commands.Cog, name="stats"):

    def __init__(self, bot):
        self.bot = bot
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
                user_ids = await self.bot.pg_con.fetch("SELECT user_id FROM users")
                flat_user_ids = [item for sublist in user_ids for item in sublist]
                logging.debug(f"{flat_user_ids=}")
                logging.debug(f"{user_ids=}")
                for member in members_list:
                    logging.debug(f"{member=}")
                    if member.id not in flat_user_ids:
                        await self.bot.pg_con.execute("INSERT INTO "
                                                      "users(user_id, created_at, bot, username) "
                                                      "VALUES($1,$2,$3,$4)",
                                                      member.id, member.created_at.replace(tzinfo=None), member.bot,
                                                      member.name)
                        await self.bot.pg_con.execute(
                            "INSERT INTO server_membership(user_id, server_id) VALUES ($1,$2)",
                            member.id, member.guild.id)
                        logging.info(f"Added {member.name} - {member.id}")
                    else:
                        try:
                            await self.bot.pg_con.execute(
                                "INSERT INTO server_membership(user_id, server_id) VALUES ($1,$2)",
                                member.id, member.guild.id)
                        except asyncpg.UniqueViolationError:
                            pass
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
            await self.bot.pg_con.execute(
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
                    await self.bot.pg_con.execute("INSERT INTO "
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
        name="save_categories",
        hidden=True
    )
    @commands.is_owner()
    async def save_categories(self, ctx):
        for guild in self.bot.guilds:
            for category in guild.categories:
                try:
                    await self.bot.pg_con.execute("INSERT INTO "
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
                    await self.bot.pg_con.execute("INSERT INTO "
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
                    await self.bot.pg_con.execute("INSERT INTO "
                                                  "roles(id, name, color, created_at, hoisted, managed, position, guild_id) "
                                                  "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                                                  role.id, role.name, str(role.color),
                                                  role.created_at.replace(tzinfo=None), role.hoist,
                                                  role.managed, role.position, guild.id)
                except asyncpg.UniqueViolationError:
                    logging.debug(f"Role already in DB")
                for member in role.members:
                    try:
                        await self.bot.pg_con.execute("INSERT INTO role_membership(user_id, role_id) VALUES($1,$2)",
                                                      member.id, role.id)
                    except asyncpg.UniqueViolationError:
                        logging.debug(f"connection already in DB {member} - {role}")
        await ctx.send("Done")

    @commands.command(
        name="save_users_from_join_leave",
        hidden=True
    )
    @commands.is_owner()
    async def save_users_from_join_leave(self, ctx):
        jn_users = await self.bot.pg_con.fetch("SELECT user_id,created_at FROM join_leave")
        for user in jn_users:
            logging.debug(user)
            try:
                await self.bot.pg_con.execute("INSERT INTO "
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
        m_channels = await self.bot.pg_con.fetch("""SELECT reactions.message_id FROM reactions
                                                    LEFT JOIN messages m on reactions.message_id = m.message_id
                                                    WHERE m.message_id IS NULL
                                                    GROUP BY reactions.message_id""")
        for channel in m_channels:
            try:
                message = await self.bot.fetch_message(channel['message_id'])
                logging.info(f"{message}")
                await self.bot.pg_con.execute("INSERT INTO users(user_id, username, bot) VALUES($1,$2,$3)",
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
            for channel in guild.text_channels:
                logging.debug(f"{channel=}")
                logging.info(f"Starting with {channel.name}")
                if channel.permissions_for(channel.guild.me).read_message_history:
                    last_message = await self.bot.pg_con.fetchrow(
                        'SELECT created_at FROM messages WHERE channel_id = $1 ORDER BY message_id DESC LIMIT 1',
                        channel.id)
                    logging.debug(f"Fetching done. found {last_message}")
                    if last_message is None:
                        logging.debug("No last row found")
                        first = datetime.strptime('2015-01-01', '%Y-%m-%d')
                    else:
                        logging.debug("Last row found")
                        first = last_message['created_at']
                    logging.info(f"Last message at {first}")
                    count = 0
                    async for message in channel.history(limit=None, after=first, oldest_first=True):
                        logging.debug(f"Saving {message.id} to database")
                        count += 1
                        await save_message(self, message)
                        await asyncio.sleep(0.05)
                    logging.info(f"{channel.name} Done. saved {count} messages")
                else:
                    logging.info(f"I was not allowed access to {channel.name}")
            logging.info("\n\nStarting with threads\n")
            for thread in guild.threads:
                logging.debug(f"{thread=}")
                logging.info(f"Starting with {thread.name}")
                if thread.permissions_for(thread.guild.me).read_message_history:
                    last_message = await self.bot.pg_con.fetchrow(
                        'SELECT created_at FROM messages WHERE channel_id = $1 ORDER BY message_id DESC LIMIT 1',
                        thread.id)
                    logging.debug(f"Fetching done. found {last_message}")
                    if last_message is None:
                        logging.debug("No last row found")
                        first = datetime.strptime('2015-01-01', '%Y-%m-%d')
                    else:
                        logging.debug("Last row found")
                        first = last_message['created_at']
                    logging.info(f"Last message at {first}")
                    count = 0
                    async for message in thread.history(limit=None, after=first, oldest_first=True):
                        logging.debug(f"Saving {message.id} to database")
                        count += 1
                        await save_message(self, message)
                        await asyncio.sleep(0.05)
                    logging.info(f"{thread.name} Done. saved {count} messages")
                else:
                    logging.info(f"I was not allowed access to {thread.name}")
        logging.info("!save completed")
        if self.save_listener not in self.bot.extra_events['on_message']:
            self.bot.add_listener(self.save_listener, name='on_message')
        if self.message_deleted not in self.bot.extra_events['on_raw_message_delete']:
            self.bot.add_listener(self.message_deleted, name='on_raw_message_delete')
        if self.message_edited not in self.bot.extra_events['on_raw_message_edit']:
            self.bot.add_listener(self.message_edited, name='on_raw_message_edit')
        # if self.reaction_add not in self.bot.extra_events['on_raw_reaction_add']:
        #     self.bot.add_listener(self.reaction_add, name='on_raw_reaction_add')
        # if self.reaction_remove not in self.bot.extra_events['on_raw_reaction_remove']:
        #     self.bot.add_listener(self.reaction_remove, name='on_raw_reaction_remove')

    @Cog.listener("on_message")
    async def save_listener(self, message):
        try:
            await save_message(self, message)
        except Exception as e:
            logging.error(f"Error: {e} on message save")

    @Cog.listener("on_raw_message_edit")
    async def message_edited(self, message):
        try:
            if 'content' in message.data and 'edited_timestamp' in message.data and message.data['edited_timestamp'] is not None:
                logging.debug(f"message edited {message}")
                old_content = await self.bot.pg_con.fetchval(
                    "SELECT content FROM messages where message_id = $1 LIMIT 1",
                    int(message.data['id']))
                logging.debug(old_content)
                await self.bot.pg_con.execute(
                    "INSERT INTO message_edit(id, old_content, new_content, edit_timestamp) VALUES ($1,$2,$3,$4)",
                    int(message.data['id']), old_content, message.data['content'],
                    datetime.fromisoformat(message.data['edited_timestamp']).replace(tzinfo=None))
                logging.debug("post insert")
                await self.bot.pg_con.execute("UPDATE messages set content = $1 WHERE message_id = $2",
                                              message.data['content'], int(message.data['id']))
                webhook = discord.SyncWebhook.from_url(secrets.webhook)
                logging.debug("post update")
        except:
            logging.exception(f"message_edited - {message.data}")

    @Cog.listener("on_raw_message_delete")
    async def message_deleted(self, message):

        await self.bot.pg_con.execute("UPDATE public.messages SET deleted = true WHERE message_id = $1",
                                      message.message_id)

    # @Cog.listener("on_raw_reaction_add")
    # async def reaction_add(self, reaction):
    #     
    #     if type(reaction.emoji) == discord.partial_emoji.PartialEmoji or type(reaction.emoji) == discord.emoji.Emoji:
    #         async with connection.transaction():
    #             old_react = await self.bot.pg_con.fetchrow("SELECT * "
    #                                                        "FROM reactions "
    #                                                        "WHERE (message_id = $1 AND user_id = $2 AND emoji_id = $3)",
    #                                                        reaction.message_id, reaction.user_id, reaction.emoji.id)
    #     else:
    #         async with connection.transaction():
    #             old_react = await self.bot.pg_con.fetchrow("SELECT * "
    #                                                        "FROM reactions "
    #                                                        "WHERE (message_id = $1 AND user_id = $2 AND unicode_emoji = $3)",
    #                                                        reaction.message_id, reaction.user_id, reaction.emoji)
    #     if type(reaction.emoji) == discord.partial_emoji.PartialEmoji or type(reaction.emoji) == discord.emoji.Emoji:
    #         if old_react is not None:
    #             async with connection.transaction():
    #                 await self.bot.pg_con.execute("UPDATE reactions "
    #                                               "SET removed = FALSE "
    #                                               "WHERE message_id = $1 AND user_id = $2 AND emoji_id = $3",
    #                                               reaction.message_id, reaction.user_id, reaction.emoji.id)
    #             await self.bot.pg_con.release(connection)
    #             return
    #     else:
    #         if old_react is not None:
    #             async with connection.transaction():
    #                 await self.bot.pg_con.execute("UPDATE reactions "
    #                                               "SET removed = FALSE "
    #                                               "WHERE message_id = $1 AND user_id = $2 AND unicode_emoji = $3",
    #                                               reaction.message_id, reaction.user_id, reaction.emoji)
    #             return
    #     if type(reaction.emoji) == discord.partial_emoji.PartialEmoji or type(reaction.emoji) == discord.emoji.Emoji:
    #         emoji = None
    #         name = reaction.emoji.name
    #         animated = reaction.emoji.animated
    #         emoji_id = reaction.emoji.id
    #     else:
    #         emoji = reaction.emoji
    #         name = None
    #         animated = False
    #         emoji_id = None
    #     async with connection.transaction():
    #         await self.bot.pg_con.execute("INSERT INTO reactions "
    #                                       "VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
    #                                       emoji, reaction.message_id, reaction.user_id,
    #                                       name, animated, emoji_id,
    #                                       f"https://cdn.discordapp.com/emojis/{emoji_id}.{'gif' if animated else 'png'}",
    #                                       datetime.now())
    #     await self.bot.pg_con.release(connection)
    #
    #     @Cog.listener("on_raw_reaction_add")
    #     async def reaction_add(self, reaction):
    #         
    #
    # @Cog.listener("on_raw_reaction_remove")
    # async def reaction_remove(self, reaction):
    #     
    #     if type(reaction.emoji) == discord.partial_emoji.PartialEmoji or type(
    #             reaction.emoji) == discord.emoji.Emoji:
    #         async with connection.transaction():
    #             await self.bot.pg_con.execute("UPDATE reactions "
    #                                           "SET removed = TRUE "
    #                                           "WHERE message_id = $1 AND user_id = $2 AND emoji_id = $3",
    #                                           reaction.message_id, reaction.user_id, reaction.emoji.id)
    #     else:
    #         async with connection.transaction():
    #             await self.bot.pg_con.execute("UPDATE reactions "
    #                                           "SET removed = TRUE "
    #                                           "WHERE message_id = $1 AND user_id = $2 AND unicode_emoji = $3",
    #                                           reaction.message_id, reaction.user_id, reaction.emoji)
    #     await self.bot.pg_con.release(connection)

    @Cog.listener("on_member_join")
    async def member_join(self, member):
        await self.bot.pg_con.execute("INSERT INTO join_leave VALUES($1,$2,$3,$4,$5,$6)",
                                      member.id, datetime.now(), "JOIN",
                                      member.guild.name, member.guild.id, member.created_at.replace(tzinfo=None))
        try:
            await self.bot.pg_con.execute("INSERT INTO "
                                          "users(user_id, created_at, bot, username) "
                                          "VALUES($1,$2,$3,$4) ON CONFLICT (user_id) DO UPDATE SET username = $4",
                                          member.id, member.created_at.replace(tzinfo=None), member.bot,
                                          member.name)
            await self.bot.pg_con.execute(
                "INSERT INTO server_membership(user_id, server_id) VALUES ($1,$2)",
                member.id, member.guild.id)
        except asyncpg.UniqueViolationError:
            logging.error("Failed to insert user into server_membership")
        except Exception as e:
            channel = self.bot.get_channel(297916314239107072)
            await channel.send(f"{e}")

    @Cog.listener("on_member_remove")
    async def member_remove(self, member):
        await self.bot.pg_con.execute("DELETE FROM server_membership WHERE user_id = $1 AND server_id = $2",
                                      member.id, member.guild.id)
        await self.bot.pg_con.execute(
            "DELETE FROM role_membership WHERE role_id IN (SELECT id FROM roles WHERE guild_id = $2) AND user_id = $1",
            member.id, member.guild.id)
        await self.bot.pg_con.execute("INSERT INTO join_leave VALUES($1,$2,$3,$4,$5,$6)",
                                      member.id, datetime.now(), "LEAVE",
                                      member.guild.name, member.guild.id, member.created_at.replace(tzinfo=None))

    @Cog.listener("on_member_update")
    async def member_roles_update(self, before, after):
        if before.roles != after.roles:
            if len(before.roles) < len(after.roles):
                gained = set(after.roles) - set(before.roles)
                gained = gained.pop()
                await self.bot.pg_con.execute("INSERT INTO role_membership(user_id, role_id) VALUES($1,$2)",
                                              after.id, gained.id)
                await self.bot.pg_con.execute(
                    "INSERT INTO role_history(role_id, user_id, date) VALUES($1,$2,$3)",
                    gained.id, after.id, datetime.now().replace(tzinfo=None))
            else:
                lost = set(before.roles) - set(after.roles)
                lost = lost.pop()
                await self.bot.pg_con.execute(
                    "DELETE FROM role_membership WHERE user_id = $1 AND role_id = $2",
                    after.id, lost.id)
                await self.bot.pg_con.execute(
                    "INSERT INTO role_history(role_id, user_id, date, gained) VALUES($1,$2,$3,FALSE)",
                    lost.id, after.id, datetime.now().replace(tzinfo=None))
                if lost.id == 585789843368574997:
                    pink_role = await after.guild.get_role(690373096099545168)
                    after.remove_roles(pink_role)

    @Cog.listener("on_user_update")
    async def user_update(self, before, after):
        if before.name != after.name:
            try:
                await self.bot.pg_con.execute("UPDATE users SET username = $1 WHERE user_id = $2",
                                              after.name, after.id)

                await self.bot.pg_con.execute(
                    'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                    "users", "UPDATE_USERNAME", before.name, after.name, datetime.now().replace(tzinfo=None),
                    str(after.id))
            except Exception as e:
                logging.error(f"Error {e}")

    @Cog.listener("on_guild_channel_create")
    async def guild_channel_create(self, channel):
        if channel.type == discord.ChannelType.text:
            try:
                await self.bot.pg_con.execute("INSERT INTO "
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
                await self.bot.pg_con.execute(
                    "INSERT INTO categories(id, name, created_at, guild_id, position, is_nsfw) VALUES($1,$2,$3,$4,$5,$6)",
                    channel.id, channel.name, channel.created_at.replace(tzinfo=None), channel.guild_id,
                    channel.position,
                    channel.is_nsfw())
            except Exception as e:
                logging.error(f"{e}")

    @Cog.listener("on_guild_channel_delete")
    async def guild_channel_delete(self, channel):
        await self.bot.pg_con.execute("UPDATE channels set deleted = TRUE where id = $1",
                                      channel.id)
        await self.bot.pg_con.execute("UPDATE messages SET deleted = TRUE where channel_id = $1",
                                      channel.id)
        await self.bot.pg_con.execute(
            'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
            "channel", "DELETED_CHANNEL", channel.name, channel.name, datetime.now().replace(tzinfo=None),
            str(channel.id))

    @Cog.listener("on_thread_join")
    async def thread_created(self, thread):
        logging.info(f"A new thread has been created: {thread}")
        try:
            await self.bot.pg_con.execute("INSERT INTO "
                                          "threads(id, guild_id, parent_id, owner_id, slowmode_delay, archived, locked, archiver_id, auto_archive_duration, is_private, name, deleted) "
                                          "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
                                          thread.id, thread.guild.id, thread.parent_id, thread.owner_id,
                                          thread.slowmode_delay, thread.archived, thread.locked, thread.archiver_id,
                                          thread.auto_archive_duration, thread.is_private(), thread.name, False)
            await self.bot.pg_con.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_CREATED", thread.name, thread.name, datetime.now().replace(tzinfo=None),
                str(thread.id))
            channel = self.bot.get_channel(871486325692432464)
            await channel.send(f"A new thread has been created: <#{thread.id}>")
            me = await self.bot.fetch_user(268608466690506753)
            await thread.add_user(me)
        except asyncpg.UniqueViolationError:
            logging.warning(f"Duplicate on {thread} in db")
        except Exception as e:
            logging.error(f"{e}")

    @Cog.listener("on_thread_delete")
    async def thread_deleted(self, thread):
        await self.bot.pg_con.execute("UPDATE threads SET deleted = $2 WHERE id = $1",
                                      thread.id, True)
        await self.bot.pg_con.execute("UPDATE messages SET deleted = $2 where channel_id = $1",
                                      thread.id, True)
        await self.bot.pg_con.execute(
            "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
            "VALUES ($1,$2,$3,$4,$5,$6)",
            "threads", "THREAD_DELETED", thread.name, thread.name, datetime.now().replace(tzinfo=None), str(thread.id))

    @Cog.listener("on_thread_update")
    async def thread_update(self, before, after):
        if before.slowmode_delay != after.slowmode_delay:
            await self.bot.pg_con.execute("UPDATE threads set slowmode_delay = $1 where id = $2",
                                          after.slowmode_delay, after.id)
            await self.bot.pg_con.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_SLOWMODE_UPDATED", before.slowmode_delay, after.slowmode_delay,
                datetime.now().replace(tzinfo=None), str(after.id))
        if before.archived != after.archived:
            if after.archiver_id:
                await self.bot.pg_con.execute("UPDATE threads set archived = $1 where id = $2",
                                              after.archived, after.id)
            else:
                await self.bot.pg_con.execute("UPDATE threads set archived = $1 AND archiver_id = $3 where id = $2",
                                              after.archived, after.id, after.archiver_id)
            await self.bot.pg_con.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_ARCHIVED_UPDATED", before.archived, after.archived,
                datetime.now().replace(tzinfo=None), str(after.id))
        if before.locked != after.locked:
            await self.bot.pg_con.execute("UPDATE threads set locked = $1 where id = $2",
                                          after.locked, after.id)
            await self.bot.pg_con.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_LOCKED_UPDATED", before.locked, after.locked, datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.auto_archive_duration != after.auto_archive_duration:
            await self.bot.pg_con.execute("UPDATE threads set auto_archive_duration = $1 where id = $2",
                                          after.auto_archive_duration, after.id)
            await self.bot.pg_con.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_AUTO_ARCHIVE_DURATION_UPDATED", before.auto_archive_duration,
                after.auto_archive_duration, datetime.now().replace(tzinfo=None), str(after.id))
        if before.is_private() != after.is_private():
            await self.bot.pg_con.execute("UPDATE threads set is_private = $1 where id = $2",
                                          after.is_private(), after.id)
            await self.bot.pg_con.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_PRIVATE_UPDATED", before.is_private(), after.is_private(),
                datetime.now().replace(tzinfo=None), str(after.id))
        if before.name != after.name:
            await self.bot.pg_con.execute("UPDATE threads set name = $1 where id = $2",
                                          after.name, after.id)
            await self.bot.pg_con.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "threads", "THREAD_NAME_UPDATED", before.name, after.name, datetime.now().replace(tzinfo=None),
                str(after.id))

    @Cog.listener("on_thread_member_join")
    async def thread_member_join(self, threadmember):
        await self.bot.pg_con.execute("INSERT INTO thread_membership(user_id, thread_id) VALUES($1,$2)",
                                      threadmember.id, threadmember.thread_id)

    @Cog.listener("on_thread_member_remove")
    async def thread_member_leave(self, threadmember):
        await self.bot.pg_con.execute("DELETE FROM thread_membership WHERE user_id = $1 and thread_id = $2",
                                      threadmember.id, threadmember.thread_id)

    @Cog.listener("on_guild_channel_update")
    async def guild_channel_update(self, before, after):
        if before.name != after.name:
            await self.bot.pg_con.execute("UPDATE channels set name = $1 where id = $2",
                                          after.name, after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_NAME", before.name, after.name, datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.category_id != after.category_id:
            await self.bot.pg_con.execute("UPDATE channels set category_id = $1 where id = $2",
                                          after.category_id, after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_CATEGORY_ID", before.category_id, after.category_id,
                datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.position != after.position:
            await self.bot.pg_con.execute("UPDATE channels set position = $1 where id = $2",
                                          after.position, after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_POSITION", before.position, after.position,
                datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.topic != after.topic:
            await self.bot.pg_con.execute("UPDATE channels set topic = $1 where id = $2",
                                          after.topic, after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_TOPIC", before.topic, after.topic, datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.is_nsfw() != after.is_nsfw():
            await self.bot.pg_con.execute("UPDATE channels set is_nsfw = $1 where id = $2",
                                          after.is_nsfw(), after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "channels", "UPDATE_CHANNEL_IS_NSFW", before.is_nsfw(), after.is_nsfw(),
                datetime.now().replace(tzinfo=None),
                str(after.id))

    @Cog.listener("on_guild_update")
    async def guild_update(self, before, after):
        if before.name != after.name:
            await self.bot.pg_con.execute("UPDATE servers set server_name = $1 WHERE server_id = $2",
                                          after.name, after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "servers", "UPDATE_SERVER_NAME", before.name, after.name, datetime.now().replace(tzinfo=None),
                str(after.id))

    @Cog.listener("on_guild_role_create")
    async def guild_role_create(self, role):
        await self.bot.pg_con.execute("INSERT INTO "
                                      "roles(id, name, color, created_at, hoisted, managed, position, guild_id) "
                                      "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                                      role.id, role.name, str(role.color), role.created_at.replace(tzinfo=None),
                                      role.hoist,
                                      role.managed, role.position, role.guild.id)

    @Cog.listener("on_guild_role_delete")
    async def guild_role_delete(self, role):
        await self.bot.pg_con.execute("UPDATE roles set deleted = TRUE where id = $1",
                                      role.id)
        await self.bot.pg_con.execute("DELETE FROM role_membership WHERE role_id = $1", role.id)

    @Cog.listener("on_guild_role_update")
    async def guild_role_update(self, before, after):
        if before.name != after.name:
            await self.bot.pg_con.execute("UPDATE roles set name = $1 where id = $2",
                                          after.name, after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "roles", "UPDATE_ROLE_NAME", before.name, after.name, datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.color != after.color:
            await self.bot.pg_con.execute("UPDATE roles set color = $1 where id = $2",
                                          after.color, after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "roles", "UPDATE_ROLE_COLOR", before.color, after.color, datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.hoist != after.hoist:
            await self.bot.pg_con.execute("UPDATE roles set hoisted = $1 where id = $2",
                                          after.hoist, after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "roles", "UPDATE_ROLE_HOISTED", before.hoist, after.hoist, datetime.now().replace(tzinfo=None),
                str(after.id))
        if before.position != after.position:
            await self.bot.pg_con.execute("UPDATE roles set position = $1 where id = $2",
                                          after.position, after.id)
            await self.bot.pg_con.execute(
                'INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)',
                "roles", "UPDATE_ROLE_POSITION", before.position, after.position,
                datetime.now().replace(tzinfo=None),
                str(after.id))

    @tasks.loop(hours=24)
    async def stats_loop(self):
        logging.info("Starting daily server activity stats gathering")
        message = ""
        messages_result = await self.bot.pg_con.fetch(
            """         
            SELECT COUNT(*) total, string_agg(distinct channel_name::text, ','::text) AS Channel
            FROM messages 
            WHERE created_at >= NOW() - INTERVAL '1 DAY' 
            AND server_id = 346842016480755724 
            AND is_bot = FALSE
            GROUP BY channel_id
            ORDER BY total DESC
            """)
        if not messages_result:
            length = 6
            logging.error(
                f"No messages found in guild 346842016480755724 during the last {datetime.now() - timedelta(hours=24)} - {datetime.now()}")
        else:
            logging.debug(f"Found results {messages_result}")
            length = len(str(messages_result[0]['total'])) + 1
            message += "==== Stats last 24 hours ====\n"
            message += "==== Messages stats ====\n"
            logging.debug(f"Build message {message}")
            for result in messages_result:
                try:
                    message += f"{result['total']:<{length}}:: {result['channel']}\n"
                except Exception as e:
                    logging.error(f'{type(e).__name__} - {e}')
            logging.debug("requesting leave/join stats")
        user_join_leave_results = await self.bot.pg_con.fetchrow(
            """         
            SELECT
            COUNT(*) filter (where join_or_leave = 'JOIN') as "JOIN",
            COUNT(*) filter (where join_or_leave = 'LEAVE') as "LEAVE"
            FROM join_leave WHERE date >= NOW() - INTERVAL '1 DAY'
            AND server_id = 346842016480755724 
            """)
        logging.debug(f"Found stats {user_join_leave_results}")
        message += f"==== Memeber stats ====\n" \
                   f"{user_join_leave_results['JOIN']:<{length}}:: Joined\n" \
                   f"{user_join_leave_results['LEAVE']:<{length}}:: Left"
        logging.debug(f"Built message {message}")
        channel = self.bot.get_channel(871486325692432464)
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

    @commands.command(
        name="messagecount",
        brief="Retrieve message count from a channel in the last x hours",
        help="",
        aliases=['mc', 'count'],
        usage='[channel] [hours]',
        hidden=False,
    )
    async def message_count(self, ctx, channel: discord.TextChannel, *, time: typing.Union[int, str]):
        logging.debug(time)
        d_time = dateparser.parse(f'{time} ago')
        logging.debug(d_time)
        results = await self.bot.pg_con.fetchrow(
            "SELECT count(*) total FROM messages WHERE created_at > $1 and channel_id = $2",
            d_time, channel.id)
        await ctx.send(f"There is a total of {results['total']} in channel {channel} since {d_time} UTC")
        logging.info(f"total messages: {results['total']} in channel {channel.name}")


def setup(bot):
    bot.add_cog(StatsCogs(bot))

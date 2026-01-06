"""Event listeners and utility functions for the stats system.

This module contains:
- Utility functions for saving messages and reactions to the database
- Discord event listeners for real-time data collection
- Handlers for messages, reactions, member events, and other Discord events
"""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

import discord
import structlog
from discord.ext.commands import Cog

if TYPE_CHECKING:
    from discord.ext import commands

# Module-level logger for utility functions
logger = structlog.get_logger("cogs.stats_listeners")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


async def save_reaction(bot: "commands.Bot", reaction: discord.Reaction) -> None:
    """Save reaction data to the database.

    Args:
        bot: The Discord bot instance
        reaction: The Discord reaction object to save

    Raises:
        Exception: If database operations fail
    """
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
                await bot.db.execute_many(
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
                await bot.db.execute_many(
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
                await bot.db.execute_many(
                    """
                    INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                    """,
                    reaction_data,
                )

    except Exception as e:
        logger.error("save_reaction_failed", error=str(e))
        raise


async def save_message(bot: "commands.Bot", message: discord.Message) -> None:
    """Save message data to the database.

    Args:
        bot: The Discord bot instance
        message: The Discord message object to save

    Raises:
        Exception: If database operations fail
    """
    try:
        # Insert user with conflict handling (UPSERT pattern)
        await bot.db.execute(
            "INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4) ON CONFLICT (user_id) DO NOTHING",
            message.author.id,
            message.author.created_at.replace(tzinfo=None),
            message.author.bot,
            message.author.name,
        )

        # Insert the message (with conflict handling for duplicates)
        await bot.db.execute(
            """
            INSERT INTO messages(message_id, created_at, content, user_name, server_name, server_id, channel_id, channel_name, user_id, user_nick, jump_url, is_bot, deleted, reference)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            ON CONFLICT (message_id) DO NOTHING
            """,
            message.id,
            message.created_at.replace(tzinfo=None),
            message.content,
            message.author.name,
            message.guild.name if message.guild else "DM",
            message.guild.id if message.guild else None,
            message.channel.id,
            getattr(message.channel, "name", "DM"),
            message.author.id,
            getattr(message.author, "display_name", message.author.name),
            message.jump_url,
            message.author.bot,
            False,  # deleted - default to False for new messages
            message.reference.message_id if message.reference else None,
        )

        # Handle attachments
        if message.attachments:
            attachment_data = [
                (
                    attachment.id,
                    attachment.filename,
                    attachment.url,
                    attachment.size,
                    attachment.height,
                    attachment.width,
                    attachment.is_spoiler(),
                    message.id,
                )
                for attachment in message.attachments
            ]

            await bot.db.execute_many(
                "INSERT INTO attachments(id, filename, url, size, height, width, is_spoiler, message_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                attachment_data,
            )

        # Handle embeds
        if message.embeds:
            for embed in message.embeds:
                # Insert embed data into the embeds table
                embed_id = await bot.db.fetchval(
                    """
                    INSERT INTO embeds (message_id, title, description, url, timestamp, color, footer_text, footer_icon_url,
                                      image_url, image_proxy_url, image_height, image_width, thumbnail_url, thumbnail_proxy_url,
                                      thumbnail_height, thumbnail_width, video_url, video_proxy_url, video_height, video_width,
                                      provider_name, provider_url, author_name, author_url, author_icon_url, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26)
                    RETURNING id
                    """,
                    message.id,
                    embed.title,
                    embed.description,
                    embed.url,
                    embed.timestamp.replace(tzinfo=None) if embed.timestamp else None,
                    embed.color.value if embed.color else None,
                    embed.footer.text if embed.footer else None,
                    embed.footer.icon_url if embed.footer else None,
                    embed.image.url if embed.image else None,
                    embed.image.proxy_url if embed.image else None,
                    embed.image.height if embed.image else None,
                    embed.image.width if embed.image else None,
                    embed.thumbnail.url if embed.thumbnail else None,
                    embed.thumbnail.proxy_url if embed.thumbnail else None,
                    embed.thumbnail.height if embed.thumbnail else None,
                    embed.thumbnail.width if embed.thumbnail else None,
                    embed.video.url if embed.video else None,
                    embed.video.proxy_url if embed.video else None,
                    embed.video.height if embed.video else None,
                    embed.video.width if embed.video else None,
                    embed.provider.name if embed.provider else None,
                    embed.provider.url if embed.provider else None,
                    embed.author.name if embed.author else None,
                    embed.author.url if embed.author else None,
                    embed.author.icon_url if embed.author else None,
                    message.created_at.replace(tzinfo=None),
                )

                # Insert embed fields if any
                if embed.fields:
                    field_data = [
                        (
                            embed_id,
                            field.name,
                            field.value,
                            field.inline,
                            i,  # field_order
                        )
                        for i, field in enumerate(embed.fields)
                    ]

                    await bot.db.execute_many(
                        "INSERT INTO embed_fields (embed_id, name, value, inline, field_order) VALUES ($1, $2, $3, $4, $5)",
                        field_data,
                    )

        # Handle user mentions
        if message.mentions:
            user_mentions = [(message.id, user.id) for user in message.mentions]
            await bot.db.execute_many(
                "INSERT INTO mentions(message_id, user_mention) VALUES ($1,$2)",
                user_mentions,
            )

        # Handle role mentions
        if message.role_mentions:
            role_mentions = [(message.id, role.id) for role in message.role_mentions]
            await bot.db.execute_many(
                "INSERT INTO mentions(message_id, role_mention) VALUES ($1,$2)",
                role_mentions,
            )

    except Exception as e:
        logger.error("save_message_failed", error=str(e))
        raise


async def perform_comprehensive_save(
    bot: "commands.Bot", progress_callback=None, completion_callback=None
) -> dict:
    """Perform a comprehensive save of all message history from accessible channels and threads.

    This function can be called independently of any command context, making it suitable
    for use by timers, background tasks, or other automated processes.

    Args:
        bot: The Discord bot instance
        progress_callback: Optional callback function for progress updates.
                         Should accept (guilds_processed, total_guilds, channels_processed,
                         messages_saved, errors_encountered, elapsed_time, current_guild_name)
        completion_callback: Optional callback function called when operation completes.
                           Should accept the results dictionary.

    Returns:
        dict: Results of the operation containing:
            - guilds_processed: Number of guilds processed
            - total_guilds: Total number of guilds
            - channels_processed: Number of channels processed
            - threads_processed: Number of threads processed
            - messages_saved: Total number of messages saved
            - errors_encountered: Number of errors encountered
            - start_time: When the operation started
            - end_time: When the operation completed
            - total_time: Total time taken

    Raises:
        Exception: If database operations fail
    """
    # Initialize progress tracking
    start_time = datetime.now()
    total_guilds = len(bot.guilds)
    guilds_processed = 0
    total_channels_processed = 0
    total_threads_processed = 0
    total_messages_saved = 0
    errors_encountered = 0

    logger.info("comprehensive_save_started", total_guilds=total_guilds)

    try:
        for guild_index, guild in enumerate(bot.guilds, 1):
            datetime.now()
            guild_channels_processed = 0
            guild_threads_processed = 0
            guild_messages_saved = 0

            logger.info(
                "processing_guild",
                guild_index=guild_index,
                total_guilds=total_guilds,
                guild_name=guild.name,
                guild_id=guild.id,
            )

            try:
                # Get all text channels with read permissions
                accessible_channels = [
                    channel
                    for channel in guild.text_channels
                    if channel.permissions_for(channel.guild.me).read_message_history
                ]

                if not accessible_channels:
                    logger.info("no_accessible_channels", guild_name=guild.name)
                else:
                    # Process channels and save messages
                    for channel in accessible_channels:
                        try:
                            logger.debug(
                                "processing_channel",
                                channel_name=channel.name,
                                channel_id=channel.id,
                            )

                            # Get last message timestamp from database
                            last_message_time = await bot.db.fetchval(
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
                                    await save_message(bot, message)
                                    guild_messages_saved += 1
                                    total_messages_saved += 1
                                except Exception as e:
                                    logger.error(
                                        "save_message_error",
                                        message_id=message.id,
                                        error=str(e),
                                    )
                                    errors_encountered += 1

                            guild_channels_processed += 1
                            total_channels_processed += 1

                        except Exception as e:
                            logger.error(
                                "process_channel_error",
                                channel_name=channel.name,
                                error=str(e),
                            )
                            errors_encountered += 1

                # Process threads
                logger.info("processing_threads", guild_name=guild.name)

                # Get all threads with read permissions
                accessible_threads = [
                    thread
                    for thread in guild.threads
                    if thread.permissions_for(thread.guild.me).read_message_history
                ]

                if not accessible_threads:
                    logger.info("no_accessible_threads", guild_name=guild.name)
                else:
                    # Process each thread
                    for thread in accessible_threads:
                        try:
                            logger.debug(
                                "processing_thread",
                                thread_name=thread.name,
                                thread_id=thread.id,
                            )

                            # Get last message timestamp from database for this thread
                            last_thread_message_time = await bot.db.fetchval(
                                "SELECT MAX(created_at) FROM messages WHERE channel_id = $1",
                                thread.id,
                            )

                            # Set after parameter for history iteration
                            after = (
                                last_thread_message_time
                                if last_thread_message_time
                                else datetime.strptime("2015-01-01", "%Y-%m-%d")
                            )

                            # Process thread messages
                            thread_message_count = 0
                            async for message in thread.history(
                                limit=None, after=after, oldest_first=True
                            ):
                                try:
                                    await save_message(bot, message)
                                    thread_message_count += 1
                                    guild_messages_saved += 1
                                    total_messages_saved += 1
                                    # Small delay to prevent rate limiting
                                    await asyncio.sleep(0.05)
                                except Exception as e:
                                    logger.error(
                                        "save_thread_message_error",
                                        message_id=message.id,
                                        thread_name=thread.name,
                                        error=str(e),
                                    )
                                    errors_encountered += 1

                            logger.info(
                                "thread_completed",
                                thread_name=thread.name,
                                messages_saved=thread_message_count,
                            )
                            guild_threads_processed += 1
                            total_threads_processed += 1

                        except discord.Forbidden:
                            logger.warning(
                                "thread_access_forbidden", thread_name=thread.name
                            )
                            errors_encountered += 1
                        except discord.HTTPException as e:
                            logger.error(
                                "thread_http_error",
                                thread_name=thread.name,
                                error=str(e),
                            )
                            errors_encountered += 1
                        except Exception as e:
                            logger.error(
                                "process_thread_error",
                                thread_name=thread.name,
                                error=str(e),
                            )
                            errors_encountered += 1

                guilds_processed += 1

                # Call progress callback every 5 guilds or on the last guild
                if progress_callback and (
                    guild_index % 5 == 0 or guild_index == total_guilds
                ):
                    elapsed_time = datetime.now() - start_time
                    try:
                        await progress_callback(
                            guilds_processed,
                            total_guilds,
                            total_channels_processed,
                            total_messages_saved,
                            errors_encountered,
                            elapsed_time,
                            guild.name,
                        )
                    except Exception as e:
                        logger.error("progress_callback_error", error=str(e))

            except Exception as e:
                logger.error("process_guild_error", guild_name=guild.name, error=str(e))
                errors_encountered += 1

    except Exception as e:
        logger.error("comprehensive_save_unexpected_error", error=str(e))
        raise

    # Prepare results
    end_time = datetime.now()
    total_time = end_time - start_time

    results = {
        "guilds_processed": guilds_processed,
        "total_guilds": total_guilds,
        "channels_processed": total_channels_processed,
        "threads_processed": total_threads_processed,
        "messages_saved": total_messages_saved,
        "errors_encountered": errors_encountered,
        "start_time": start_time,
        "end_time": end_time,
        "total_time": total_time,
    }

    # Call completion callback if provided
    if completion_callback:
        try:
            await completion_callback(results)
        except Exception as e:
            logger.error("completion_callback_error", error=str(e))

    # Enable event listeners for ongoing message tracking
    try:
        stats_cog = bot.get_cog("stats")
        if stats_cog:
            listeners_enabled = 0
            if stats_cog.save_listener not in bot.extra_events.get("on_message", []):
                bot.add_listener(stats_cog.save_listener, name="on_message")
                listeners_enabled += 1
            if stats_cog.message_deleted not in bot.extra_events.get(
                "on_raw_message_delete", []
            ):
                bot.add_listener(
                    stats_cog.message_deleted, name="on_raw_message_delete"
                )
                listeners_enabled += 1
            if stats_cog.message_edited not in bot.extra_events.get(
                "on_raw_message_edit", []
            ):
                bot.add_listener(stats_cog.message_edited, name="on_raw_message_edit")
                listeners_enabled += 1
            if stats_cog.reaction_add not in bot.extra_events.get(
                "on_raw_reaction_add", []
            ):
                bot.add_listener(stats_cog.reaction_add, name="on_raw_reaction_add")
                listeners_enabled += 1
            if stats_cog.reaction_remove not in bot.extra_events.get(
                "on_raw_reaction_remove", []
            ):
                bot.add_listener(
                    stats_cog.reaction_remove, name="on_raw_reaction_remove"
                )
                listeners_enabled += 1

            logger.info("event_listeners_enabled", count=listeners_enabled)
        else:
            logger.warning("stats_cog_not_found")
    except Exception as e:
        logger.error("enable_listeners_error", error=str(e))
        results["errors_encountered"] = results.get("errors_encountered", 0) + 1

    logger.info(
        "comprehensive_save_completed",
        guilds_processed=guilds_processed,
        total_guilds=total_guilds,
        channels_processed=total_channels_processed,
        messages_saved=total_messages_saved,
        errors=errors_encountered,
        total_time=str(total_time).split(".")[0],
    )

    return results


# ============================================================================
# EVENT LISTENERS MIXIN
# ============================================================================


class StatsListenersMixin:
    """Mixin class containing all stats-related event listeners."""

    @Cog.listener("on_message")
    async def save_listener(self, message: discord.Message) -> None:
        """Listen for new messages and save them to the database.

        Args:
            message: The Discord message object
        """
        if not isinstance(message.channel, discord.channel.DMChannel):
            try:
                await save_message(self.bot, message)
            except Exception as e:
                logger.error("message_save_failed", error=str(e))

    @Cog.listener("on_raw_message_edit")
    async def message_edited(self, payload: discord.RawMessageUpdateEvent) -> None:
        """Listen for message edits and update the database.

        Args:
            payload: The raw message update event payload
        """
        try:
            if (
                "content" in payload.data
                and "edited_timestamp" in payload.data
                and payload.data["edited_timestamp"] is not None
            ):
                logger.debug("message_edited", message_id=payload.data.get("id"))
                old_content = await self.bot.db.fetchval(
                    "SELECT content FROM messages where message_id = $1 LIMIT 1",
                    int(payload.data["id"]),
                )
                logger.debug(
                    "old_content_fetched",
                    content_length=len(old_content) if old_content else 0,
                )
                await self.bot.db.execute(
                    "INSERT INTO message_edit(id, old_content, new_content, edit_timestamp) VALUES ($1,$2,$3,$4)",
                    int(payload.data["id"]),
                    old_content,
                    payload.data["content"],
                    datetime.fromisoformat(payload.data["edited_timestamp"]).replace(
                        tzinfo=None
                    ),
                )
                logger.debug("message_edit_inserted")
                await self.bot.db.execute(
                    "UPDATE messages set content = $1 WHERE message_id = $2",
                    payload.data["content"],
                    int(payload.data["id"]),
                )
                logger.debug("message_content_updated")
        except Exception as e:
            logger.exception(
                "message_edited_error",
                message_data=str(payload.data)[:200],
                error=str(e),
            )

    @Cog.listener("on_raw_message_delete")
    async def message_deleted(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Listen for message deletions and mark them as deleted in the database.

        Args:
            payload: The raw message delete event payload
        """
        await self.bot.db.execute(
            "UPDATE public.messages SET deleted = true WHERE message_id = $1",
            payload.message_id,
        )

    @Cog.listener("on_raw_reaction_add")
    async def reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Listen for reaction additions and save them to the database.

        Args:
            payload: The raw reaction action event payload
        """
        try:
            current_time = datetime.now().replace(tzinfo=None)

            # Use transaction for consistency
            async with self.bot.db.pool.acquire() as conn:
                async with conn.transaction():
                    if payload.emoji.is_custom_emoji():
                        await conn.execute(
                            """
                            INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                            ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                            """,
                            None,
                            payload.message_id,
                            payload.user_id,
                            payload.emoji.name,
                            payload.emoji.animated,
                            payload.emoji.id,
                            f"https://cdn.discordapp.com/emojis/{payload.emoji.id}.{'gif' if payload.emoji.animated else 'png'}",
                            current_time,
                            payload.emoji.is_custom_emoji(),
                        )
                    elif isinstance(payload.emoji, str):
                        await conn.execute(
                            """
                            INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                            ON CONFLICT (message_id, user_id, emoji_id) DO UPDATE SET removed = FALSE
                            """,
                            payload.emoji,
                            payload.message_id,
                            payload.user_id,
                            None,
                            False,
                            None,
                            None,
                            current_time,
                            False,
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO reactions(unicode_emoji, message_id, user_id, emoji_name, animated, emoji_id, url, date, is_custom_emoji) 
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) 
                            ON CONFLICT (message_id, user_id, unicode_emoji) DO UPDATE SET removed = FALSE
                            """,
                            payload.emoji.name,
                            payload.message_id,
                            payload.user_id,
                            payload.emoji.name,
                            None,
                            None,
                            None,
                            current_time,
                            payload.emoji.is_custom_emoji(),
                        )
        except Exception as e:
            logger.exception("reaction_add_error", error=str(e))

    @Cog.listener("on_raw_reaction_remove")
    async def reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """Listen for reaction removals and mark them as removed in the database.

        Args:
            payload: The raw reaction action event payload
        """
        try:
            if payload.emoji.is_custom_emoji():
                await self.bot.db.execute(
                    "UPDATE reactions SET removed = TRUE WHERE message_id = $1 AND user_id = $2 AND emoji_id = $3",
                    payload.message_id,
                    payload.user_id,
                    payload.emoji.id,
                )
            else:
                await self.bot.db.execute(
                    "UPDATE reactions SET removed = TRUE WHERE message_id = $1 AND user_id = $2 AND unicode_emoji = $3",
                    payload.message_id,
                    payload.user_id,
                    str(payload.emoji),
                )
        except Exception as e:
            logger.exception("reaction_remove_error", error=str(e))

    @Cog.listener("on_member_join")
    async def member_join(self, member: discord.Member) -> None:
        """Listen for member joins and save the join event to the database.

        Args:
            member: The Discord member who joined
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO join_leave(user_id, server_id, date, join_or_leave, server_name, created_at) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
                member.id,
                member.guild.id,
                datetime.now().replace(tzinfo=None),
                "join",
                member.guild.name,
                datetime.now().replace(tzinfo=None),
            )
        except Exception as e:
            logger.error("member_join_save_error", error=str(e))

    @Cog.listener("on_member_remove")
    async def member_remove(self, member: discord.Member) -> None:
        """Listen for member leaves and update the leave date in the database.

        Args:
            member: The Discord member who left
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO join_leave(user_id, server_id, date, join_or_leave, server_name, created_at) VALUES ($1,$2,$3,$4,$5,$6)",
                member.id,
                member.guild.id,
                datetime.now().replace(tzinfo=None),
                "leave",
                member.guild.name,
                datetime.now().replace(tzinfo=None),
            )
        except Exception as e:
            logger.error("member_leave_save_error", error=str(e))

    @Cog.listener("on_member_update")
    async def member_roles_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """Listen for member role updates and save role changes to the database.

        Args:
            before: The member state before the update
            after: The member state after the update
        """
        try:
            if before.roles != after.roles:
                # Get added and removed roles
                added_roles = set(after.roles) - set(before.roles)
                removed_roles = set(before.roles) - set(after.roles)

                current_time = datetime.now().replace(tzinfo=None)

                # Save added roles
                for role in added_roles:
                    await self.bot.db.execute(
                        "INSERT INTO role_changes(user_id, server_id, role_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                        after.id,
                        after.guild.id,
                        role.id,
                        "added",
                        current_time,
                    )

                # Save removed roles
                for role in removed_roles:
                    await self.bot.db.execute(
                        "INSERT INTO role_changes(user_id, server_id, role_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                        after.id,
                        after.guild.id,
                        role.id,
                        "removed",
                        current_time,
                    )

                # Log role changes
                if added_roles:
                    logger.info(
                        "user_gained_roles",
                        user_id=after.id,
                        roles=[role.name for role in added_roles],
                    )
                if removed_roles:
                    logger.info(
                        "user_lost_roles",
                        user_id=after.id,
                        roles=[role.name for role in removed_roles],
                    )

        except Exception as e:
            logger.error("role_changes_error", error=str(e))

    @Cog.listener("on_user_update")
    async def user_update(self, before: discord.User, after: discord.User) -> None:
        """Listen for user updates and save username changes to the database.

        Args:
            before: The user state before the update
            after: The user state after the update
        """
        try:
            if before.name != after.name:
                await self.bot.db.execute(
                    "UPDATE users SET username = $1 WHERE user_id = $2",
                    after.name,
                    after.id,
                )
        except Exception as e:
            logger.error("username_update_error", error=str(e))

    @Cog.listener("on_guild_channel_create")
    async def guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        """Listen for channel creation and save new channels to the database.

        Args:
            channel: The newly created channel
        """
        try:
            # Handle all guild channel types
            if isinstance(
                channel,
                discord.TextChannel
                | discord.VoiceChannel
                | discord.StageChannel
                | discord.ForumChannel,
            ):
                # Get channel-specific attributes with safe defaults
                topic = getattr(channel, "topic", None)
                is_nsfw = (
                    getattr(channel, "is_nsfw", lambda: False)()
                    if callable(getattr(channel, "is_nsfw", None))
                    else False
                )

                await self.bot.db.execute(
                    "INSERT INTO channels(id, name, category_id, created_at, guild_id, position, topic, is_nsfw) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                    channel.id,
                    channel.name,
                    channel.category_id,
                    channel.created_at.replace(tzinfo=None),
                    channel.guild.id,
                    channel.position,
                    topic,
                    is_nsfw,
                )
        except Exception as e:
            logger.error("save_channel_error", error=str(e))

    @Cog.listener("on_guild_channel_delete")
    async def guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        """Listen for channel deletion and mark channels as deleted in the database.

        Args:
            channel: The deleted channel
        """
        try:
            await self.bot.db.execute(
                "UPDATE channels SET deleted = TRUE WHERE id = $1",
                channel.id,
            )
        except Exception as e:
            logger.error("mark_channel_deleted_error", error=str(e))

    @Cog.listener("on_thread_create")
    async def thread_created(self, thread: discord.Thread) -> None:
        """Listen for thread creation and save new threads to the database.
        Also ping a role in new threads (except in excluded channels).

        Args:
            thread: The newly created thread
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO threads(id, name, parent_id, guild_id, archived, locked) VALUES ($1,$2,$3,$4,$5,$6)",
                thread.id,
                thread.name,
                thread.parent_id,
                thread.guild.id,
                thread.archived,
                thread.locked,
            )

            # Add the missing role pinging functionality
            # Ping role 1153075640535367721 in all new threads except those in channel 1190045713778868335
            if thread.parent_id != 1190045713778868335:
                await thread.send("<@&1153075640535367721>")

        except Exception as e:
            logger.error("save_thread_error", error=str(e))

    @Cog.listener("on_thread_delete")
    async def thread_deleted(self, thread: discord.Thread) -> None:
        """Listen for thread deletion and mark threads as deleted in the database.

        Args:
            thread: The deleted thread
        """
        try:
            await self.bot.db.execute(
                "UPDATE threads SET deleted = TRUE WHERE id = $1",
                thread.id,
            )
        except Exception as e:
            logger.error("mark_thread_deleted_error", error=str(e))

    @Cog.listener("on_guild_emojis_update")
    async def guild_emoji_update(
        self,
        guild: discord.Guild,
        before: list[discord.Emoji],
        after: list[discord.Emoji],
    ) -> None:
        """Listen for emoji updates and save changes to the database.

        Args:
            guild: The guild where emojis were updated
            before: The list of emojis before the update
            after: The list of emojis after the update
        """
        try:
            # Get added and removed emojis
            before_set = {emoji.id for emoji in before}
            after_set = {emoji.id for emoji in after}

            added_emojis = [emoji for emoji in after if emoji.id not in before_set]
            removed_emoji_ids = before_set - after_set

            current_time = datetime.now().replace(tzinfo=None)

            # Save added emojis
            for emoji in added_emojis:
                await self.bot.db.execute(
                    "INSERT INTO emojis(id, name, guild_id, animated, created_at) VALUES ($1,$2,$3,$4,$5)",
                    emoji.id,
                    emoji.name,
                    guild.id,
                    emoji.animated,
                    current_time,
                )

            # Mark removed emojis as deleted
            for emoji_id in removed_emoji_ids:
                await self.bot.db.execute(
                    "UPDATE emojis SET deleted = TRUE WHERE id = $1",
                    emoji_id,
                )
        except Exception as e:
            logger.error("update_emojis_error", error=str(e))

    @Cog.listener("on_guild_role_create")
    async def guild_role_create(self, role: discord.Role) -> None:
        """Listen for role creation and save new roles to the database.

        Args:
            role: The newly created role
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO roles(id, name, guild_id, color, position, permissions, created_at) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                role.id,
                role.name,
                role.guild.id,
                role.color.value,
                role.position,
                role.permissions.value,
                role.created_at.replace(tzinfo=None),
            )
        except Exception as e:
            logger.error("save_role_error", error=str(e))

    @Cog.listener("on_guild_role_delete")
    async def guild_role_delete(self, role: discord.Role) -> None:
        """Listen for role deletion and mark roles as deleted in the database.

        Args:
            role: The deleted role
        """
        try:
            await self.bot.db.execute(
                "UPDATE roles SET deleted = TRUE WHERE id = $1",
                role.id,
            )
        except Exception as e:
            logger.error("mark_role_deleted_error", error=str(e))

    async def ensure_channel_exists(self, channel: discord.abc.GuildChannel) -> None:
        """Ensure a channel exists in the database, inserting it if necessary."""
        try:
            # Check if channel exists
            result = await self.bot.db.fetchval(
                "SELECT id FROM channels WHERE id = $1", channel.id
            )
            if result is None:
                # Channel doesn't exist, insert it
                topic = getattr(channel, "topic", None)
                is_nsfw = (
                    getattr(channel, "is_nsfw", lambda: False)()
                    if callable(getattr(channel, "is_nsfw", None))
                    else False
                )

                await self.bot.db.execute(
                    "INSERT INTO channels(id, name, category_id, created_at, guild_id, position, topic, is_nsfw) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                    channel.id,
                    channel.name,
                    channel.category_id,
                    channel.created_at.replace(tzinfo=None),
                    channel.guild.id,
                    channel.position,
                    topic,
                    is_nsfw,
                )
        except Exception as e:
            logger.error("ensure_channel_exists_error", error=str(e))

    # ============================================================================
    # MISSING FEATURES FROM ORIGINAL IMPLEMENTATION
    # ============================================================================

    @Cog.listener("on_thread_member_join")
    async def thread_member_join(self, thread_member: discord.ThreadMember) -> None:
        """Listen for thread member joins and save them to the database.

        Args:
            thread_member: The thread member who joined
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO thread_membership(user_id, thread_id) VALUES($1,$2)",
                thread_member.id,
                thread_member.thread_id,
            )
            logger.debug(
                "thread_member_joined",
                user_id=thread_member.id,
                thread_id=thread_member.thread_id,
            )
        except Exception as e:
            logger.error("save_thread_member_join_error", error=str(e))

    @Cog.listener("on_thread_member_remove")
    async def thread_member_leave(self, thread_member: discord.ThreadMember) -> None:
        """Listen for thread member leaves and remove them from the database.

        Args:
            thread_member: The thread member who left
        """
        try:
            await self.bot.db.execute(
                "DELETE FROM thread_membership WHERE user_id = $1 and thread_id = $2",
                thread_member.id,
                thread_member.thread_id,
            )
            logger.debug(
                "thread_member_left",
                user_id=thread_member.id,
                thread_id=thread_member.thread_id,
            )
        except Exception as e:
            logger.error("remove_thread_member_error", error=str(e))

    async def log_update(
        self,
        table: str,
        action: str,
        before_value: str,
        after_value: str,
        primary_key: str,
    ) -> None:
        """Log an update to the updates table for audit trail purposes.

        Args:
            table: The table that was updated
            action: The type of action performed
            before_value: The value before the update
            after_value: The value after the update
            primary_key: The primary key of the updated record
        """
        try:
            await self.bot.db.execute(
                "INSERT INTO updates(updated_table, action, before, after, date, primary_key) VALUES($1,$2,$3,$4,$5,$6)",
                table,
                action,
                before_value,
                after_value,
                datetime.now().replace(tzinfo=None),
                primary_key,
            )
        except Exception as e:
            logger.error("log_update_error", error=str(e))

    # Enhanced Channel Update Tracking
    @Cog.listener("on_guild_channel_update")
    async def guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        """Listen for channel updates and save detailed changes to the database with audit trail.

        Args:
            before: The channel state before the update
            after: The channel state after the update
        """
        try:
            # Track channel name changes
            if before.name != after.name:
                await self.bot.db.execute(
                    "UPDATE channels SET name = $1 WHERE id = $2",
                    after.name,
                    after.id,
                )
                await self.log_update(
                    "channels",
                    "UPDATE_CHANNEL_NAME",
                    before.name,
                    after.name,
                    str(after.id),
                )

            # Track category changes
            if before.category_id != after.category_id:
                await self.bot.db.execute(
                    "UPDATE channels SET category_id = $1 WHERE id = $2",
                    after.category_id,
                    after.id,
                )
                await self.log_update(
                    "channels",
                    "UPDATE_CHANNEL_CATEGORY_ID",
                    str(before.category_id),
                    str(after.category_id),
                    str(after.id),
                )

            # Track position changes
            if before.position != after.position:
                await self.bot.db.execute(
                    "UPDATE channels SET position = $1 WHERE id = $2",
                    after.position,
                    after.id,
                )
                await self.log_update(
                    "channels",
                    "UPDATE_CHANNEL_POSITION",
                    str(before.position),
                    str(after.position),
                    str(after.id),
                )

            # Track topic changes (for text channels)
            if (
                hasattr(before, "topic")
                and hasattr(after, "topic")
                and before.topic != after.topic
            ):
                await self.bot.db.execute(
                    "UPDATE channels SET topic = $1 WHERE id = $2",
                    after.topic,
                    after.id,
                )
                await self.log_update(
                    "channels",
                    "UPDATE_CHANNEL_TOPIC",
                    before.topic,
                    after.topic,
                    str(after.id),
                )

            # Track NSFW status changes (for text channels)
            if (
                hasattr(before, "is_nsfw")
                and hasattr(after, "is_nsfw")
                and before.is_nsfw() != after.is_nsfw()
            ):
                await self.bot.db.execute(
                    "UPDATE channels SET is_nsfw = $1 WHERE id = $2",
                    after.is_nsfw(),
                    after.id,
                )
                await self.log_update(
                    "channels",
                    "UPDATE_CHANNEL_IS_NSFW",
                    str(before.is_nsfw()),
                    str(after.is_nsfw()),
                    str(after.id),
                )

        except Exception as e:
            logger.error("update_channel_audit_trail_error", error=str(e))

    # Enhanced Thread Update Tracking with Audit Trail
    @Cog.listener("on_thread_update")
    async def enhanced_thread_update(
        self, before: discord.Thread, after: discord.Thread
    ) -> None:
        """Enhanced thread update listener with comprehensive audit trail.

        Args:
            before: The thread state before the update
            after: The thread state after the update
        """
        try:
            # Track thread name changes
            if before.name != after.name:
                await self.log_update(
                    "threads",
                    "THREAD_NAME_UPDATED",
                    before.name,
                    after.name,
                    str(after.id),
                )

            # Track archive status changes
            if before.archived != after.archived:
                await self.log_update(
                    "threads",
                    "THREAD_ARCHIVED_UPDATED",
                    str(before.archived),
                    str(after.archived),
                    str(after.id),
                )

            # Track lock status changes
            if before.locked != after.locked:
                await self.log_update(
                    "threads",
                    "THREAD_LOCKED_UPDATED",
                    str(before.locked),
                    str(after.locked),
                    str(after.id),
                )

            # Update the threads table
            await self.bot.db.execute(
                "UPDATE threads SET name = $1, archived = $2, locked = $3 WHERE id = $4",
                after.name,
                after.archived,
                after.locked,
                after.id,
            )

        except Exception as e:
            logger.error("enhanced_thread_update_error", error=str(e))

    # Enhanced Guild Update Tracking with Audit Trail
    @Cog.listener("on_guild_update")
    async def enhanced_guild_update(
        self, before: discord.Guild, after: discord.Guild
    ) -> None:
        """Enhanced guild update listener with comprehensive audit trail.

        Args:
            before: The guild state before the update
            after: The guild state after the update
        """
        try:
            # Track server name changes
            if before.name != after.name:
                await self.bot.db.execute(
                    "UPDATE servers SET server_name = $1 WHERE server_id = $2",
                    after.name,
                    after.id,
                )
                await self.log_update(
                    "servers",
                    "UPDATE_SERVER_NAME",
                    before.name,
                    after.name,
                    str(after.id),
                )

        except Exception as e:
            logger.error("enhanced_guild_update_error", error=str(e))

    # Enhanced Role Update Tracking with Audit Trail
    @Cog.listener("on_guild_role_update")
    async def enhanced_guild_role_update(
        self, before: discord.Role, after: discord.Role
    ) -> None:
        """Enhanced role update listener with comprehensive audit trail.

        Args:
            before: The role state before the update
            after: The role state after the update
        """
        try:
            # Track role name changes
            if before.name != after.name:
                await self.log_update(
                    "roles", "UPDATE_ROLE_NAME", before.name, after.name, str(after.id)
                )

            # Track role color changes
            if before.color != after.color:
                await self.log_update(
                    "roles",
                    "UPDATE_ROLE_COLOR",
                    str(before.color.value),
                    str(after.color.value),
                    str(after.id),
                )

            # Track role position changes
            if before.position != after.position:
                await self.log_update(
                    "roles",
                    "UPDATE_ROLE_POSITION",
                    str(before.position),
                    str(after.position),
                    str(after.id),
                )

            # Track role permission changes
            if before.permissions != after.permissions:
                await self.log_update(
                    "roles",
                    "UPDATE_ROLE_PERMISSIONS",
                    str(before.permissions.value),
                    str(after.permissions.value),
                    str(after.id),
                )

            # Update the roles table
            await self.bot.db.execute(
                "UPDATE roles SET name = $1, color = $2, position = $3, permissions = $4 WHERE id = $5",
                after.name,
                after.color.value,
                after.position,
                after.permissions.value,
                after.id,
            )

        except Exception as e:
            logger.error("enhanced_role_update_error", error=str(e))

    # Enhanced Voice State Tracking with Detailed State Changes
    @Cog.listener("on_voice_state_update")
    async def enhanced_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Enhanced voice state update listener with detailed state change tracking.

        Args:
            member: The member whose voice state changed
            before: The voice state before the update
            after: The voice state after the update
        """
        try:
            # Track mute state changes
            if before.mute != after.mute:
                await self.log_update(
                    "voice_state",
                    "UPDATE_VOICE_STATE_MUTE",
                    str(before.mute),
                    str(after.mute),
                    str(member.id),
                )

            # Track deaf state changes
            if before.deaf != after.deaf:
                await self.log_update(
                    "voice_state",
                    "UPDATE_VOICE_STATE_DEAF",
                    str(before.deaf),
                    str(after.deaf),
                    str(member.id),
                )

            # Track self-mute state changes
            if before.self_mute != after.self_mute:
                await self.log_update(
                    "voice_state",
                    "UPDATE_VOICE_STATE_SELF_MUTE",
                    str(before.self_mute),
                    str(after.self_mute),
                    str(member.id),
                )

            # Track self-deaf state changes
            if before.self_deaf != after.self_deaf:
                await self.log_update(
                    "voice_state",
                    "UPDATE_VOICE_STATE_SELF_DEAF",
                    str(before.self_deaf),
                    str(after.self_deaf),
                    str(member.id),
                )

            # Track suppress state changes
            if before.suppress != after.suppress:
                await self.log_update(
                    "voice_state",
                    "UPDATE_VOICE_STATE_SUPPRESS",
                    str(before.suppress),
                    str(after.suppress),
                    str(member.id),
                )

            # Handle voice channel join/leave tracking
            current_time = datetime.now().replace(tzinfo=None)

            # Ensure user exists before inserting voice activity (foreign key constraint)
            await self.bot.db.execute(
                "INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4) ON CONFLICT (user_id) DO NOTHING",
                member.id,
                member.created_at.replace(tzinfo=None),
                member.bot,
                member.name,
            )

            # User joined a voice channel
            if before.channel is None and after.channel is not None:
                await self.ensure_channel_exists(after.channel)
                await self.bot.db.execute(
                    "INSERT INTO voice_activity(user_id, guild_id, channel_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                    member.id,
                    member.guild.id,
                    after.channel.id,
                    "joined",
                    current_time,
                )

            # User left a voice channel
            elif before.channel is not None and after.channel is None:
                await self.ensure_channel_exists(before.channel)
                await self.bot.db.execute(
                    "INSERT INTO voice_activity(user_id, guild_id, channel_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                    member.id,
                    member.guild.id,
                    before.channel.id,
                    "left",
                    current_time,
                )

            # User moved between voice channels
            elif (
                before.channel != after.channel
                and before.channel is not None
                and after.channel is not None
            ):
                await self.ensure_channel_exists(before.channel)
                await self.ensure_channel_exists(after.channel)
                await self.bot.db.execute(
                    "INSERT INTO voice_activity(user_id, guild_id, channel_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                    member.id,
                    member.guild.id,
                    before.channel.id,
                    "left",
                    current_time,
                )
                await self.bot.db.execute(
                    "INSERT INTO voice_activity(user_id, guild_id, channel_id, action, timestamp) VALUES ($1,$2,$3,$4,$5)",
                    member.id,
                    member.guild.id,
                    after.channel.id,
                    "joined",
                    current_time,
                )

        except Exception as e:
            logger.error("enhanced_voice_state_update_error", error=str(e))

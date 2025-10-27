"""Utility functions for the stats system.

This module contains utility functions used by the stats cog for saving
reactions and messages to the database.
"""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from discord.ext import commands


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
        logging.error(f"Error saving reaction: {e}")
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
    from datetime import datetime

    # Initialize progress tracking
    start_time = datetime.now()
    total_guilds = len(bot.guilds)
    guilds_processed = 0
    total_channels_processed = 0
    total_threads_processed = 0
    total_messages_saved = 0
    errors_encountered = 0

    logging.info(f"Starting comprehensive save operation for {total_guilds} guilds")

    try:
        for guild_index, guild in enumerate(bot.guilds, 1):
            datetime.now()
            guild_channels_processed = 0
            guild_threads_processed = 0
            guild_messages_saved = 0

            logging.info(
                f"Processing guild {guild_index}/{total_guilds}: {guild.name} ({guild.id})"
            )

            try:
                # Get all text channels with read permissions
                accessible_channels = [
                    channel
                    for channel in guild.text_channels
                    if channel.permissions_for(channel.guild.me).read_message_history
                ]

                if not accessible_channels:
                    logging.info(f"No accessible channels found in guild {guild.name}")
                else:
                    # Process channels and save messages
                    for channel in accessible_channels:
                        try:
                            logging.debug(
                                f"Processing channel: {channel.name} ({channel.id})"
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
                                    logging.error(
                                        f"Error saving message {message.id}: {e}"
                                    )
                                    errors_encountered += 1

                            guild_channels_processed += 1
                            total_channels_processed += 1

                        except Exception as e:
                            logging.error(
                                f"Error processing channel {channel.name}: {e}"
                            )
                            errors_encountered += 1

                # Process threads
                logging.info(f"Starting thread processing for guild {guild.name}")

                # Get all threads with read permissions
                accessible_threads = [
                    thread
                    for thread in guild.threads
                    if thread.permissions_for(thread.guild.me).read_message_history
                ]

                if not accessible_threads:
                    logging.info(f"No accessible threads found in guild {guild.name}")
                else:
                    # Process each thread
                    for thread in accessible_threads:
                        try:
                            logging.debug(
                                f"Processing thread: {thread.name} ({thread.id})"
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
                                    logging.error(
                                        f"Error saving message {message.id} in thread {thread.name}: {e}"
                                    )
                                    errors_encountered += 1

                            logging.info(
                                f"Thread {thread.name} completed: {thread_message_count} messages saved"
                            )
                            guild_threads_processed += 1
                            total_threads_processed += 1

                        except discord.Forbidden:
                            logging.warning(
                                f"No permission to read history in thread {thread.name}"
                            )
                            errors_encountered += 1
                        except discord.HTTPException as e:
                            logging.error(
                                f"Discord API error reading thread {thread.name}: {e}"
                            )
                            errors_encountered += 1
                        except Exception as e:
                            logging.error(f"Error processing thread {thread.name}: {e}")
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
                        logging.error(f"Error in progress callback: {e}")

            except Exception as e:
                logging.error(f"Error processing guild {guild.name}: {e}")
                errors_encountered += 1

    except Exception as e:
        logging.error(f"Unexpected error during comprehensive save operation: {e}")
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
            logging.error(f"Error in completion callback: {e}")

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

            logging.info(
                f"Enabled {listeners_enabled} event listeners for ongoing message tracking"
            )
        else:
            logging.warning("Stats cog not found, cannot enable event listeners")
    except Exception as e:
        logging.error(f"Error enabling event listeners: {e}")
        results["errors_encountered"] = results.get("errors_encountered", 0) + 1

    logging.info(
        f"Comprehensive save operation completed. "
        f"Guilds: {guilds_processed}/{total_guilds}, "
        f"Channels: {total_channels_processed}, "
        f"Messages: {total_messages_saved:,}, "
        f"Errors: {errors_encountered}, "
        f"Time: {str(total_time).split('.')[0]}"
    )

    return results


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
        logging.error(f"Error saving message: {e}")
        raise

"""
Utility functions for the stats system.

This module contains utility functions used by the stats cog for saving
reactions and messages to the database.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from discord.ext import commands


async def save_reaction(bot: "commands.Bot", reaction: discord.Reaction) -> None:
    """
    Save reaction data to the database.

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


async def save_message(bot: "commands.Bot", message: discord.Message) -> None:
    """
    Save message data to the database.

    Args:
        bot: The Discord bot instance
        message: The Discord message object to save

    Raises:
        Exception: If database operations fail
    """
    try:
        # Check if user exists, if not create them
        user_exists = await bot.db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM users WHERE user_id = $1)", message.author.id
        )

        if not user_exists:
            await bot.db.execute(
                "INSERT INTO users(user_id, created_at, bot, username) VALUES($1,$2,$3,$4)",
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
            getattr(message.channel, 'name', 'DM'),
            message.author.id,
            getattr(message.author, 'display_name', message.author.name),
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

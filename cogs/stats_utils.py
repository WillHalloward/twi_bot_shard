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

        # Insert the message
        await bot.db.execute(
            """
            INSERT INTO messages(message_id, user_id, channel_id, server_id, content, created_at, message_type, tts, mention_everyone, pinned, webhook_id, application_id, activity, flags, thread_id, reference_message_id, interaction_id, interaction_type, interaction_user_id) 
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
            """,
            message.id,
            message.author.id,
            message.channel.id,
            message.guild.id if message.guild else None,
            message.content,
            message.created_at.replace(tzinfo=None),
            str(message.type),
            message.tts,
            message.mention_everyone,
            message.pinned,
            message.webhook_id,
            message.application_id,
            str(message.activity) if message.activity else None,
            int(message.flags) if message.flags else None,
            (
                message.channel.id
                if hasattr(message.channel, "parent_id") and message.channel.parent_id
                else None
            ),
            message.reference.message_id if message.reference else None,
            message.interaction.id if message.interaction else None,
            str(message.interaction.type) if message.interaction else None,
            message.interaction.user.id if message.interaction else None,
        )

        # Handle attachments
        if message.attachments:
            attachment_data = [
                (
                    attachment.id,
                    message.id,
                    attachment.filename,
                    attachment.description,
                    attachment.content_type,
                    attachment.size,
                    attachment.url,
                    attachment.proxy_url,
                    attachment.height,
                    attachment.width,
                    attachment.ephemeral,
                )
                for attachment in message.attachments
            ]

            await bot.db.execute_many(
                "INSERT INTO attachments(attachment_id, message_id, filename, description, content_type, size, url, proxy_url, height, width, ephemeral) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
                attachment_data,
            )

        # Handle embeds
        if message.embeds:
            embed_data = [
                (
                    message.id,
                    embed.title,
                    embed.type,
                    embed.description,
                    embed.url,
                    embed.timestamp.replace(tzinfo=None) if embed.timestamp else None,
                    embed.color.value if embed.color else None,
                )
                for embed in message.embeds
            ]

            await bot.db.execute_many(
                "INSERT INTO embeds(message_id, title, type, description, url, timestamp, color) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                embed_data,
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

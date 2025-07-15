"""
Background tasks for the stats system.

This module contains background tasks that run periodically to generate
reports and perform maintenance operations for the stats system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from discord.ext import tasks

if TYPE_CHECKING:
    from discord.ext.commands import Bot


class StatsTasksMixin:
    """Mixin class containing all stats-related background tasks."""

    @tasks.loop(hours=24)
    async def stats_loop(self) -> None:
        """
        Daily background task to gather and post server activity statistics.

        This task runs every 24 hours to:
        - Refresh materialized views for performance
        - Query daily message statistics by channel
        - Query daily member join/leave statistics
        - Post formatted statistics to a designated channel

        The task posts statistics for a hardcoded server ID (346842016480755724)
        to a hardcoded channel ID (871486325692432464).
        """
        logging.info("Starting daily server activity stats gathering")
        message = ""

        # Refresh materialized views before querying them
        try:
            await self.bot.db.refresh_materialized_views()
            logging.info("Refreshed materialized views")
        except Exception as e:
            logging.error(f"Failed to refresh materialized views: {e}")

        # Query with hierarchical structure: category -> channel -> thread
        messages_result = await self.bot.db.fetch(
            """         
            WITH message_stats AS (
                SELECT 
                    m.channel_id,
                    m.channel_name,
                    COUNT(*) as message_count,
                    c.category_id,
                    cat.name as category_name,
                    t.parent_id,
                    t.name as thread_name,
                    CASE 
                        WHEN t.id IS NOT NULL THEN 'thread'
                        ELSE 'channel'
                    END as channel_type
                FROM messages m
                LEFT JOIN channels c ON m.channel_id = c.id
                LEFT JOIN categories cat ON c.category_id = cat.id
                LEFT JOIN threads t ON m.channel_id = t.id
                WHERE m.created_at >= NOW() - INTERVAL '1 DAY'
                AND m.server_id = 346842016480755724
                AND m.is_bot = FALSE
                AND m.deleted = FALSE
                GROUP BY m.channel_id, m.channel_name, c.category_id, cat.name, t.parent_id, t.name
            )
            SELECT 
                COALESCE(category_name, 'Uncategorized') as category,
                channel_name,
                thread_name,
                message_count,
                channel_type,
                COALESCE(parent_id, channel_id) as sort_parent
            FROM message_stats
            ORDER BY 
                COALESCE(category_name, 'Uncategorized'),
                COALESCE(parent_id, channel_id),
                CASE WHEN channel_type = 'thread' THEN 1 ELSE 0 END,
                message_count DESC
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

            # Calculate category totals and organize data
            category_data = {}
            max_count = 0

            for result in messages_result:
                category = result['category']
                channel_name = result['channel_name']
                thread_name = result['thread_name']
                count = result['message_count']
                channel_type = result['channel_type']

                max_count = max(max_count, count)

                if category not in category_data:
                    category_data[category] = {'total': 0, 'channels': {}}

                category_data[category]['total'] += count

                if channel_type == 'thread':
                    # Find parent channel in the same category
                    parent_found = False
                    for ch_name, ch_data in category_data[category]['channels'].items():
                        if ch_data.get('channel_id') == result['sort_parent']:
                            if 'threads' not in ch_data:
                                ch_data['threads'] = {}
                            ch_data['threads'][thread_name] = count
                            parent_found = True
                            break

                    if not parent_found:
                        # Create placeholder for parent channel if not found
                        if channel_name not in category_data[category]['channels']:
                            category_data[category]['channels'][channel_name] = {'count': 0, 'threads': {}}
                        category_data[category]['channels'][channel_name]['threads'][thread_name] = count
                else:
                    if channel_name not in category_data[category]['channels']:
                        category_data[category]['channels'][channel_name] = {'count': count}
                    else:
                        category_data[category]['channels'][channel_name]['count'] = count

            # Calculate formatting width
            length = len(str(max(max_count, max(cat_data['total'] for cat_data in category_data.values())))) + 1

            message += "==== Stats last 24 hours ====\n"
            message += "==== Messages stats ====\n\n"

            # Sort categories by total message count
            sorted_categories = sorted(category_data.items(), key=lambda x: x[1]['total'], reverse=True)

            for category, cat_data in sorted_categories:
                try:
                    # Category header with emoji
                    emoji = "📁" if category != "Uncategorized" else "📂"
                    message += f"{emoji} {category} ({cat_data['total']:,} messages)\n"

                    # Sort channels by message count
                    sorted_channels = sorted(cat_data['channels'].items(), key=lambda x: x[1].get('count', 0), reverse=True)

                    for channel_name, channel_data in sorted_channels:
                        channel_count = channel_data.get('count', 0)
                        if channel_count > 0:
                            message += f"    #{channel_name:<25} {channel_count:>{length-4}}\n"

                        # Add threads if they exist
                        if 'threads' in channel_data:
                            sorted_threads = sorted(channel_data['threads'].items(), key=lambda x: x[1], reverse=True)
                            for thread_name, thread_count in sorted_threads:
                                message += f"        🧵 {thread_name:<21} {thread_count:>{length-8}}\n"

                    message += "\n"  # Add spacing between categories

                except Exception as e:
                    logging.error(f"{type(e).__name__} - {e}")

            logging.debug("requesting leave/join stats")

        # Query the join_leave table directly for more reliable results
        # This avoids timezone issues with the materialized view
        # Calculate 24 hours ago using Python to match how data is stored
        twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
        user_join_leave_results = await self.bot.db.fetchrow(
            """         
            SELECT 
                COUNT(*) FILTER (WHERE join_or_leave = 'join') as "join",
                COUNT(*) FILTER (WHERE join_or_leave = 'leave') as "leave"
            FROM join_leave
            WHERE server_id = 346842016480755724
            AND date >= $1
            """,
            twenty_four_hours_ago
        )
        logging.debug(f"Found stats {user_join_leave_results}")

        if user_join_leave_results is not None:
            message += (
                f"==== Member stats ====\n"
                f"{user_join_leave_results['join']:<{length}}:: Joined\n"
                f"{user_join_leave_results['leave']:<{length}}:: Left"
            )
        else:
            logging.warning("No join/leave stats found")
            message += "==== Member stats ====\nNo join/leave data available\n"

        logging.debug(f"Built message {message}")

        # Get the designated stats channel
        channel = self.bot.get_channel(871486325692432464)
        if channel is None:
            logging.error("Could not find channel to post stats to 871486325692432464")
        else:
            logging.debug(f"Found channel {channel.name}")

            # Split message if it's too long for Discord's character limit
            if len(message) > 1900:
                logging.debug("Message longer than 1900 characters")
                str_list = [message[i : i + 1900] for i in range(0, len(message), 1900)]
                for string in str_list:
                    await channel.send(f"```asciidoc\n{string}\n```")
                    await asyncio.sleep(0.5)  # Rate limiting prevention
            else:
                try:
                    await channel.send(f"```asciidoc\n{message}\n```")
                except Exception as e:
                    logging.error(
                        f"Could not post stats_loop to channel {channel.name} - {e}"
                    )
            logging.info("Daily stats report done")

    @stats_loop.before_loop
    async def before_stats_loop(self) -> None:
        """
        Preparation task that runs before the stats loop starts.

        Ensures the bot is ready before starting the background task.
        """
        await self.bot.wait_until_ready()
        logging.info("Stats loop is ready to start")

    @stats_loop.error
    async def stats_loop_error(self, error: Exception) -> None:
        """
        Error handler for the stats loop task.

        Args:
            error: The exception that occurred in the stats loop
        """
        logging.error(f"Error in stats loop: {error}")

        # Notify bot owner of the error
        try:
            owner = self.bot.get_user(self.bot.owner_id)
            if owner:
                await owner.send(
                    f"⚠️ **Stats Loop Error**\n"
                    f"**Error:** {type(error).__name__}: {error}\n"
                    f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"The stats loop will attempt to restart automatically."
                )
        except Exception as e:
            logging.error(f"Failed to notify owner of stats loop error: {e}")

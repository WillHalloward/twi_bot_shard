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

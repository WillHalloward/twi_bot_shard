"""Refactored Stats Cog for Discord Bot.

This module provides comprehensive statistics tracking and reporting functionality
for Discord servers.

The cog tracks:
- Message statistics and history
- User activity and membership changes
- Reaction data
- Channel and server information
- Voice activity

Architecture:
- StatsCommandsMixin: Owner commands for data management
- StatsListenersMixin: Real-time event listeners
- StatsQueriesMixin: User-facing query commands
- Background tasks integrated directly in this module
"""

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from discord.ext import commands, tasks

import config

from .stats_commands import StatsCommandsMixin, StatsQueriesMixin
from .stats_listeners import StatsListenersMixin

if TYPE_CHECKING:
    from discord.ext.commands import Bot


class StatsCogs(
    StatsCommandsMixin,
    StatsListenersMixin,
    StatsQueriesMixin,
    commands.Cog,
    name="stats",
):
    """Comprehensive statistics tracking cog for Discord servers.

    This cog provides extensive functionality for tracking and analyzing
    Discord server activity, including messages, users, reactions, and more.

    Features:
    - Real-time message and reaction tracking
    - User activity monitoring
    - Server statistics and reporting
    - Background tasks for daily reports
    - Query commands for retrieving statistics
    - Comprehensive data management commands

    Attributes:
        bot: The Discord bot instance
        logger: Logger instance for this cog
    """

    def __init__(self, bot: "Bot") -> None:
        """Initialize the Stats cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = structlog.get_logger("cogs.stats")

        # Start the background stats loop if not in test mode
        if config.logfile != "test":
            self.stats_loop.start()
            self.logger.info("stats_loop_started")
        else:
            self.logger.info("stats_loop_disabled", reason="test_mode")

    async def cog_unload(self) -> None:
        """Cleanup when the cog is unloaded.

        Stops the background stats loop to prevent resource leaks.
        """
        if hasattr(self, "stats_loop") and self.stats_loop.is_running():
            self.stats_loop.cancel()
            self.logger.info("stats_loop_stopped")

    async def cog_load(self) -> None:
        """Setup when the cog is loaded.

        Performs any necessary initialization after the cog is added to the bot.
        """
        self.logger.info("stats_cog_loaded")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Event listener for when the bot is ready.

        Logs that the stats cog is ready and operational.
        """
        self.logger.info("stats_cog_ready")

    # ==================== Background Tasks ====================

    @tasks.loop(hours=24)
    async def stats_loop(self) -> None:
        """Daily background task to gather and post server activity statistics.

        This task runs every 24 hours to:
        - Refresh materialized views for performance
        - Query daily message statistics by channel
        - Query daily member join/leave statistics
        - Post formatted statistics to a designated channel

        The task posts statistics for a hardcoded server ID (346842016480755724)
        to a hardcoded channel ID (871486325692432464).
        """
        self.logger.info("stats_loop_starting", task="daily_stats")
        message = ""

        # Refresh materialized views before querying them
        try:
            await self.bot.db.refresh_materialized_views()
            self.logger.info("materialized_views_refreshed")
        except Exception as e:
            self.logger.error("materialized_views_refresh_failed", error=str(e))

        # Query with hierarchical structure: category -> channel -> thread
        messages_result = await self.bot.db.fetch(
            """
            WITH message_stats AS (
                SELECT
                    m.channel_id,
                    m.channel_name,
                    COUNT(*) as message_count,
                    COALESCE(parent_c.category_id, c.category_id) as category_id,
                    COALESCE(parent_cat.name, cat.name) as category_name,
                    t.parent_id,
                    t.name as thread_name,
                    COALESCE(parent_c.name, m.channel_name) as parent_channel_name,
                    CASE
                        WHEN t.id IS NOT NULL THEN 'thread'
                        ELSE 'channel'
                    END as channel_type
                FROM messages m
                LEFT JOIN channels c ON m.channel_id = c.id
                LEFT JOIN categories cat ON c.category_id = cat.id
                LEFT JOIN threads t ON m.channel_id = t.id
                LEFT JOIN channels parent_c ON t.parent_id = parent_c.id
                LEFT JOIN categories parent_cat ON parent_c.category_id = parent_cat.id
                WHERE m.created_at >= NOW() - INTERVAL '1 DAY'
                AND m.server_id = 346842016480755724
                AND m.is_bot = FALSE
                AND m.deleted = FALSE
                GROUP BY m.channel_id, m.channel_name,
                         COALESCE(parent_c.category_id, c.category_id),
                         COALESCE(parent_cat.name, cat.name),
                         t.parent_id, t.name, t.id,
                         COALESCE(parent_c.name, m.channel_name)
            )
            SELECT
                COALESCE(category_name, 'Uncategorized') as category,
                channel_name,
                thread_name,
                message_count,
                channel_type,
                parent_channel_name,
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
            self.logger.error(
                "no_messages_found",
                guild_id=346842016480755724,
                period="24h",
            )
            try:
                owner = await self.bot.fetch_user(self.bot.owner_id)
                await owner.send(
                    f"No messages found in guild 346842016480755724 during the last {datetime.now() - timedelta(hours=24)} - {datetime.now()}"
                )
            except Exception as e:
                self.logger.error("owner_notification_failed", error=str(e))
        else:
            self.logger.debug("messages_found", count=len(messages_result))

            # Calculate category totals and organize data
            category_data = {}
            max_count = 0

            for result in messages_result:
                category = result["category"]
                channel_name = result["channel_name"]
                thread_name = result["thread_name"]
                count = result["message_count"]
                channel_type = result["channel_type"]
                parent_channel_name = result["parent_channel_name"]

                max_count = max(max_count, count)

                if category not in category_data:
                    category_data[category] = {"total": 0, "channels": {}}

                category_data[category]["total"] += count

                if channel_type == "thread":
                    if parent_channel_name not in category_data[category]["channels"]:
                        category_data[category]["channels"][parent_channel_name] = {
                            "count": 0,
                            "threads": {},
                        }

                    if (
                        "threads"
                        not in category_data[category]["channels"][parent_channel_name]
                    ):
                        category_data[category]["channels"][parent_channel_name][
                            "threads"
                        ] = {}
                    category_data[category]["channels"][parent_channel_name]["threads"][
                        thread_name
                    ] = count
                else:
                    if channel_name not in category_data[category]["channels"]:
                        category_data[category]["channels"][channel_name] = {
                            "count": count
                        }
                    else:
                        category_data[category]["channels"][channel_name]["count"] = (
                            count
                        )

            # Calculate formatting width
            length = (
                len(
                    str(
                        max(
                            max_count,
                            max(
                                cat_data["total"] for cat_data in category_data.values()
                            ),
                        )
                    )
                )
                + 1
            )

            message += "==== Stats last 24 hours ====\n"
            message += "==== Messages stats ====\n\n"

            # Sort categories by total message count
            sorted_categories = sorted(
                category_data.items(), key=lambda x: x[1]["total"], reverse=True
            )

            for category, cat_data in sorted_categories:
                try:
                    emoji = "📁" if category != "Uncategorized" else "📂"
                    message += f"{emoji} {category} ({cat_data['total']:,} messages)\n"

                    sorted_channels = sorted(
                        cat_data["channels"].items(),
                        key=lambda x: x[1].get("count", 0),
                        reverse=True,
                    )

                    for channel_name, channel_data in sorted_channels:
                        channel_count = channel_data.get("count", 0)
                        if channel_count > 0:
                            message += f"    #{channel_name:<25} {channel_count:>{length - 4}}\n"

                        if "threads" in channel_data:
                            sorted_threads = sorted(
                                channel_data["threads"].items(),
                                key=lambda x: x[1],
                                reverse=True,
                            )
                            for thread_name, thread_count in sorted_threads:
                                message += f"        🧵 {thread_name:<21} {thread_count:>{length - 8}}\n"

                    message += "\n"

                except Exception as e:
                    self.logger.error("category_format_error", error=str(e))

            self.logger.debug("requesting_join_leave_stats")

        # Query join/leave stats
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
            twenty_four_hours_ago,
        )
        self.logger.debug(
            "join_leave_stats_found",
            stats=dict(user_join_leave_results) if user_join_leave_results else None,
        )

        if user_join_leave_results is not None:
            message += (
                f"==== Member stats ====\n"
                f"{user_join_leave_results['join']:<{length}}:: Joined\n"
                f"{user_join_leave_results['leave']:<{length}}:: Left"
            )
        else:
            self.logger.warning("no_join_leave_stats")
            message += "==== Member stats ====\nNo join/leave data available\n"

        self.logger.debug("stats_message_built", length=len(message))

        # Get the designated stats channel
        channel = self.bot.get_channel(871486325692432464)
        if channel is None:
            self.logger.error("stats_channel_not_found", channel_id=871486325692432464)
        else:
            self.logger.debug("posting_to_channel", channel=channel.name)

            # Split message if it's too long for Discord's character limit
            if len(message) > 1900:
                self.logger.debug("message_split_required", length=len(message))
                str_list = [message[i : i + 1900] for i in range(0, len(message), 1900)]
                for string in str_list:
                    await channel.send(f"```asciidoc\n{string}\n```")
                    await asyncio.sleep(0.5)
            else:
                try:
                    await channel.send(f"```asciidoc\n{message}\n```")
                except Exception as e:
                    self.logger.error(
                        "stats_post_failed", channel=channel.name, error=str(e)
                    )
            self.logger.info("daily_stats_report_completed")

    @stats_loop.before_loop
    async def before_stats_loop(self) -> None:
        """Preparation task that runs before the stats loop starts.

        Ensures the bot is ready before starting the background task.
        """
        await self.bot.wait_until_ready()
        self.logger.info("stats_loop_ready")

    @stats_loop.error
    async def stats_loop_error(self, error: Exception) -> None:
        """Error handler for the stats loop task.

        Args:
            error: The exception that occurred in the stats loop
        """
        self.logger.error(
            "stats_loop_error", error=str(error), error_type=type(error).__name__
        )

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
            self.logger.error("owner_notification_failed", error=str(e))


async def setup(bot: "Bot") -> None:
    """Setup function to add the cog to the bot.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(StatsCogs(bot))

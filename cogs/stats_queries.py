"""
Query commands for the stats system.

This module contains app commands and query methods that allow users
to retrieve statistical information from the database.
"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import asyncpg
import discord
from discord import app_commands

from utils.error_handling import handle_interaction_errors
from utils.exceptions import DatabaseError, QueryError, ValidationError

if TYPE_CHECKING:
    from discord import Interaction


class StatsQueriesMixin:
    """Mixin class containing all stats-related query commands."""

    @app_commands.command(
        name="messagecount",
        description="Retrieve message count from a channel in the last x hours",
    )
    @handle_interaction_errors
    async def message_count(
        self, interaction: "Interaction", channel: discord.TextChannel, hours: int
    ) -> None:
        """
        Retrieve message count from a specific channel within a time range.

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

            # Calculate average messages per hour
            avg_per_hour = message_count / hours if hours > 0 else 0
            embed.add_field(
                name="Average per Hour",
                value=f"**{avg_per_hour:.1f}** messages/hour",
                inline=True,
            )

            # Add additional context
            embed.add_field(
                name="Query Time",
                value=f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during message count query: {e}") from e

    @app_commands.command(
        name="channelstats",
        description="Get comprehensive statistics for a channel",
    )
    @handle_interaction_errors
    async def channel_stats(
        self, interaction: "Interaction", channel: discord.TextChannel, days: int = 7
    ) -> None:
        """
        Get comprehensive statistics for a specific channel.

        Args:
            interaction: The Discord interaction object
            channel: The text channel to get statistics for
            days: Number of days to look back (default: 7, max: 365)

        Raises:
            ValidationError: If the days parameter is invalid
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        # Validate days parameter
        if days <= 0:
            raise ValidationError(
                field="days", message="Days must be a positive number"
            )

        if days > 365:  # More than a year
            raise ValidationError(
                field="days", message="Days cannot exceed 365 (1 year)"
            )

        # Calculate the time threshold
        d_time = datetime.now() - timedelta(days=days)

        try:
            # Query for comprehensive channel statistics
            stats_query = """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as unique_users,
                AVG(LENGTH(content)) as avg_message_length,
                COUNT(*) FILTER (WHERE attachments.attachment_id IS NOT NULL) as messages_with_attachments,
                COUNT(*) FILTER (WHERE embeds.message_id IS NOT NULL) as messages_with_embeds
            FROM messages 
            LEFT JOIN attachments ON messages.message_id = attachments.message_id
            LEFT JOIN embeds ON messages.message_id = embeds.message_id
            WHERE messages.created_at > $1 AND messages.channel_id = $2
            """

            results = await self.bot.db.fetchrow(stats_query, d_time, channel.id)

            if results is None:
                raise QueryError("Database query returned no results")

            # Query for top users in the channel
            top_users_query = """
            SELECT user_id, COUNT(*) as message_count
            FROM messages 
            WHERE created_at > $1 AND channel_id = $2
            GROUP BY user_id
            ORDER BY message_count DESC
            LIMIT 5
            """

            top_users = await self.bot.db.fetch(top_users_query, d_time, channel.id)

            # Create a formatted response
            embed = discord.Embed(
                title=f"📈 Channel Statistics: {channel.name}",
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )

            # Basic statistics
            embed.add_field(
                name="📝 Total Messages",
                value=f"**{results['total_messages']:,}**",
                inline=True,
            )

            embed.add_field(
                name="👥 Unique Users",
                value=f"**{results['unique_users']:,}**",
                inline=True,
            )

            avg_length = results["avg_message_length"] or 0
            embed.add_field(
                name="📏 Avg Message Length",
                value=f"**{avg_length:.1f}** characters",
                inline=True,
            )

            embed.add_field(
                name="📎 Messages with Attachments",
                value=f"**{results['messages_with_attachments']:,}**",
                inline=True,
            )

            embed.add_field(
                name="🎨 Messages with Embeds",
                value=f"**{results['messages_with_embeds']:,}**",
                inline=True,
            )

            # Calculate activity rate
            messages_per_day = results["total_messages"] / days if days > 0 else 0
            embed.add_field(
                name="📊 Activity Rate",
                value=f"**{messages_per_day:.1f}** messages/day",
                inline=True,
            )

            # Top users section
            if top_users:
                top_users_text = ""
                for i, user_data in enumerate(top_users, 1):
                    user = self.bot.get_user(user_data["user_id"])
                    username = (
                        user.display_name if user else f"User {user_data['user_id']}"
                    )
                    top_users_text += (
                        f"{i}. {username}: {user_data['message_count']:,} messages\n"
                    )

                embed.add_field(
                    name="🏆 Top Contributors",
                    value=top_users_text,
                    inline=False,
                )

            embed.add_field(
                name="📅 Time Period",
                value=f"Last {days} day{'s' if days != 1 else ''}\n"
                f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during channel stats query: {e}") from e

    @app_commands.command(
        name="serverstats",
        description="Get comprehensive statistics for the current server",
    )
    @handle_interaction_errors
    async def server_stats(self, interaction: "Interaction", days: int = 7) -> None:
        """
        Get comprehensive statistics for the current server.

        Args:
            interaction: The Discord interaction object
            days: Number of days to look back (default: 7, max: 365)

        Raises:
            ValidationError: If the days parameter is invalid
            DatabaseError: If database query fails
            QueryError: If there's an issue with the SQL query
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!", ephemeral=True
            )
            return

        # Validate days parameter
        if days <= 0:
            raise ValidationError(
                field="days", message="Days must be a positive number"
            )

        if days > 365:  # More than a year
            raise ValidationError(
                field="days", message="Days cannot exceed 365 (1 year)"
            )

        # Calculate the time threshold
        d_time = datetime.now() - timedelta(days=days)

        try:
            # Query for comprehensive server statistics
            stats_query = """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as active_users,
                COUNT(DISTINCT channel_id) as active_channels
            FROM messages 
            WHERE created_at > $1 AND server_id = $2
            """

            results = await self.bot.db.fetchrow(
                stats_query, d_time, interaction.guild.id
            )

            # Query for member join/leave statistics
            member_stats_query = """
            SELECT 
                COUNT(*) FILTER (WHERE date > $1 AND join_or_leave = 'join') as new_joins,
                COUNT(*) FILTER (WHERE date > $1 AND join_or_leave = 'leave') as leaves
            FROM join_leave 
            WHERE server_id = $2
            """

            member_results = await self.bot.db.fetchrow(
                member_stats_query, d_time, interaction.guild.id
            )

            if results is None:
                raise QueryError("Database query returned no results")

            # Create a formatted response
            embed = discord.Embed(
                title=f"🏰 Server Statistics: {interaction.guild.name}",
                color=discord.Color.purple(),
                timestamp=datetime.now(),
            )

            # Basic statistics
            embed.add_field(
                name="📝 Total Messages",
                value=f"**{results['total_messages']:,}**",
                inline=True,
            )

            embed.add_field(
                name="👥 Active Users",
                value=f"**{results['active_users']:,}**",
                inline=True,
            )

            embed.add_field(
                name="📺 Active Channels",
                value=f"**{results['active_channels']:,}**",
                inline=True,
            )

            if member_results:
                embed.add_field(
                    name="📈 New Members",
                    value=f"**{member_results['new_joins'] or 0:,}**",
                    inline=True,
                )

                embed.add_field(
                    name="📉 Members Left",
                    value=f"**{member_results['leaves'] or 0:,}**",
                    inline=True,
                )

                net_growth = (member_results["new_joins"] or 0) - (
                    member_results["leaves"] or 0
                )
                embed.add_field(
                    name="📊 Net Growth",
                    value=f"**{net_growth:+,}**",
                    inline=True,
                )

            # Calculate activity rates
            messages_per_day = results["total_messages"] / days if days > 0 else 0
            embed.add_field(
                name="📈 Message Activity",
                value=f"**{messages_per_day:.1f}** messages/day",
                inline=True,
            )

            # Current server info
            embed.add_field(
                name="👑 Current Members",
                value=f"**{interaction.guild.member_count:,}**",
                inline=True,
            )

            embed.add_field(
                name="📅 Time Period",
                value=f"Last {days} day{'s' if days != 1 else ''}\n"
                f"From: {d_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                inline=False,
            )

            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.response.send_message(embed=embed)

        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database query failed: {e}") from e
        except Exception as e:
            raise QueryError(f"Unexpected error during server stats query: {e}") from e

"""
Patreon Poll Management Cog

This module provides comprehensive functionality for managing and displaying Patreon polls
within a Discord bot. It includes commands for fetching polls from the Patreon API,
displaying poll information with rich embeds, searching through poll options, and
listing polls by year.

Key Features:
- Fetch and sync polls from Patreon API with detailed progress tracking
- Display active and historical polls with vote counts and percentages
- Full-text search through poll options using PostgreSQL text search
- List polls by year with filtering and pagination
- Comprehensive structured logging for all operations
- Rich Discord embeds with emojis and formatting
- Robust error handling with user-friendly messages
- Permission-based access control for administrative functions

Commands:
- /poll [poll_id]: Display latest active poll or specific poll by ID
- /polllist [year]: List all polls from a specific year
- /getpoll: Fetch and update polls from Patreon API (admin only)
- /findpoll <query>: Search through poll options using keywords

Database Integration:
- Uses PostgreSQL with asyncpg for efficient database operations
- Stores poll metadata, options, and vote counts
- Supports full-text search with tsvector indexing
- Handles both active and expired polls

Logging:
- Structured logging with contextual information
- Performance timing for database operations
- User action tracking for audit purposes
- Error logging with detailed context

Author: Twi Bot Shard Development Team
Version: Enhanced with comprehensive logging and documentation
"""

import json
import logging
from datetime import datetime, timezone
from operator import itemgetter

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
import structlog

import config
from utils.permissions import (
    admin_or_me_check,
    admin_or_me_check_wrapper,
    app_admin_or_me_check,
    is_bot_channel,
    is_bot_channel_wrapper,
    app_is_bot_channel,
)
from utils.logging import RequestContext, TimingContext


async def fetch(session, url, cookies=None, headers=None):
    """
    Fetch data from a URL using the provided session.

    Args:
        session: The aiohttp ClientSession to use
        url: The URL to fetch
        cookies: Optional cookies to send with the request
        headers: Optional headers to send with the request

    Returns:
        The response text
    """
    cookies = cookies or config.cookies
    headers = headers or config.headers

    async with session.get(url, cookies=cookies, headers=headers) as response:
        return await response.text()


async def get_poll(bot):
    """
    Fetch and process polls from Patreon API with comprehensive logging and statistics.

    Args:
        bot: The Discord bot instance

    Returns:
        dict: Statistics about the operation including polls processed, new polls found, etc.
    """
    logger = structlog.get_logger("patreon_poll")

    async with RequestContext(logger, "get_poll_operation") as ctx:
        stats = {
            "pages_processed": 0,
            "polls_found": 0,
            "new_polls_added": 0,
            "expired_polls_added": 0,
            "active_polls_added": 0,
            "poll_options_added": 0,
            "errors": 0,
        }

        url = "https://www.patreon.com/api/posts?include=Cpoll.choices%2Cpoll.current_user_responses.poll&filter[campaign_id]=568211"

        # Get existing poll IDs for reference
        async with TimingContext(logger, "fetch_existing_polls") as timing_ctx:
            poll_ids = await bot.db.fetch("SELECT id FROM poll")
            timing_ctx.add_info(existing_poll_count=len(poll_ids))

        logger.info(
            "poll_fetch_started",
            initial_url=url,
            existing_polls=len(poll_ids),
            request_id=ctx.request_id,
        )

        while True:
            stats["pages_processed"] += 1

            try:
                # Fetch page data
                async with TimingContext(logger, "fetch_page_data") as timing_ctx:
                    session = await bot.http_client.get_session()
                    html = await fetch(session, url)
                    timing_ctx.add_info(page_number=stats["pages_processed"], url=url)

                # Parse JSON data
                try:
                    json_data = json.loads(html)
                    logger.debug(
                        "page_data_parsed",
                        page=stats["pages_processed"],
                        posts_count=len(json_data.get("data", [])),
                    )
                except Exception as e:
                    logger.error(
                        "json_parse_failed",
                        page=stats["pages_processed"],
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    stats["errors"] += 1
                    continue

                # Process each post
                for posts in json_data["data"]:
                    if posts["relationships"]["poll"]["data"] is not None:
                        stats["polls_found"] += 1
                        poll_api_id = int(posts["relationships"]["poll"]["data"]["id"])

                        # Check if poll already exists
                        async with TimingContext(
                            logger, "check_poll_exists"
                        ) as timing_ctx:
                            poll_id = await bot.db.fetch(
                                "SELECT * FROM poll WHERE id = $1", poll_api_id
                            )
                            timing_ctx.add_info(
                                poll_api_id=poll_api_id, exists=bool(poll_id)
                            )

                        if not poll_id:
                            logger.info(
                                "processing_new_poll",
                                poll_api_id=poll_api_id,
                                poll_url=posts["attributes"]["patreon_url"],
                            )

                            try:
                                # Fetch detailed poll data
                                async with TimingContext(
                                    logger, "fetch_poll_details"
                                ) as timing_ctx:
                                    session = await bot.http_client.get_session()
                                    html = await fetch(
                                        session,
                                        posts["relationships"]["poll"]["links"][
                                            "related"
                                        ],
                                    )
                                    json_data2 = json.loads(html)
                                    timing_ctx.add_info(poll_api_id=poll_api_id)

                                # Parse poll data
                                open_at_converted = datetime.fromisoformat(
                                    json_data2["data"]["attributes"]["created_at"]
                                )
                                try:
                                    closes_at_converted = datetime.fromisoformat(
                                        json_data2["data"]["attributes"]["closes_at"]
                                    )
                                except TypeError:
                                    closes_at_converted = None

                                title = json_data2["data"]["attributes"][
                                    "question_text"
                                ]
                                num_options = len(
                                    json_data2["data"]["relationships"]["choices"][
                                        "data"
                                    ]
                                )

                                # Determine if poll is expired
                                is_expired = (
                                    closes_at_converted is None
                                    or closes_at_converted < datetime.now(timezone.utc)
                                )

                                # Insert poll record
                                async with TimingContext(
                                    logger, "insert_poll_record"
                                ) as timing_ctx:
                                    if is_expired:
                                        await bot.db.execute(
                                            "INSERT INTO poll(api_url, poll_url, id, start_date, expire_date, title, total_votes, "
                                            "expired, num_options) "
                                            "VALUES ($1,$2,$3,$4,$5,$6,$7, TRUE, $8)",
                                            posts["relationships"]["poll"]["links"][
                                                "related"
                                            ],
                                            posts["attributes"]["patreon_url"],
                                            poll_api_id,
                                            open_at_converted,
                                            closes_at_converted,
                                            title,
                                            int(
                                                json_data2["data"]["attributes"][
                                                    "num_responses"
                                                ]
                                            ),
                                            num_options,
                                        )
                                        stats["expired_polls_added"] += 1

                                        # Insert poll options for expired polls
                                        for i in range(num_options):
                                            await bot.db.execute(
                                                "INSERT INTO poll_option(option_text, poll_id, num_votes, option_id)"
                                                "VALUES ($1,$2,$3,$4)",
                                                json_data2["included"][i]["attributes"][
                                                    "text_content"
                                                ],
                                                poll_api_id,
                                                int(
                                                    json_data2["included"][i][
                                                        "attributes"
                                                    ]["num_responses"]
                                                ),
                                                int(
                                                    json_data2["data"]["relationships"][
                                                        "choices"
                                                    ]["data"][i]["id"]
                                                ),
                                            )
                                            stats["poll_options_added"] += 1
                                    else:
                                        await bot.db.execute(
                                            "INSERT INTO poll(api_url, poll_url, id, start_date, expire_date, title, expired, "
                                            "num_options) "
                                            "VALUES ($1,$2,$3,$4,$5,$6, FALSE, $7)",
                                            posts["relationships"]["poll"]["links"][
                                                "related"
                                            ],
                                            posts["attributes"]["patreon_url"],
                                            poll_api_id,
                                            open_at_converted,
                                            closes_at_converted,
                                            title,
                                            num_options,
                                        )
                                        stats["active_polls_added"] += 1

                                    timing_ctx.add_info(
                                        poll_api_id=poll_api_id,
                                        is_expired=is_expired,
                                        num_options=num_options,
                                    )

                                stats["new_polls_added"] += 1
                                logger.info(
                                    "poll_added_successfully",
                                    poll_api_id=poll_api_id,
                                    title=title,
                                    is_expired=is_expired,
                                    num_options=num_options,
                                    start_date=open_at_converted.isoformat(),
                                    expire_date=(
                                        closes_at_converted.isoformat()
                                        if closes_at_converted
                                        else None
                                    ),
                                )

                            except Exception as e:
                                logger.error(
                                    "poll_processing_failed",
                                    poll_api_id=poll_api_id,
                                    error=str(e),
                                    error_type=type(e).__name__,
                                )
                                stats["errors"] += 1

                # Check for next page
                try:
                    url = json_data["links"]["next"]
                    logger.info(
                        "proceeding_to_next_page",
                        page=stats["pages_processed"],
                        next_url=url,
                    )
                except KeyError:
                    logger.info(
                        "pagination_complete", total_pages=stats["pages_processed"]
                    )
                    break

            except Exception as e:
                logger.error(
                    "page_processing_failed",
                    page=stats["pages_processed"],
                    url=url,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                stats["errors"] += 1
                break

        logger.info("poll_fetch_completed", **stats, request_id=ctx.request_id)

        return stats


async def check_and_update_expired_polls(bot, polls):
    """
    Check if any polls have expired and update them in the database.

    This function checks polls that are marked as not expired in the database
    but have actually expired based on their expire_date. It fetches the latest
    vote data from the Patreon API and saves it to the database.

    Args:
        bot: The Discord bot instance
        polls: List of poll records to check

    Returns:
        List of polls with updated expiration status
    """
    logger = structlog.get_logger("patreon_poll.expiration_check")
    updated_polls = []

    for poll in polls:
        # Check if poll has an expire_date and if it has passed
        if (
            poll["expire_date"] is not None
            and poll["expire_date"] < datetime.now(timezone.utc)
            and not poll["expired"]
        ):

            logger.info(
                "poll_expired_detected",
                poll_id=poll["id"],
                poll_title=poll["title"],
                expire_date=poll["expire_date"].isoformat(),
            )

            try:
                # Fetch latest poll data from Patreon API to get final vote counts
                session = await bot.http_client.get_session()
                html = await fetch(session, poll["api_url"])
                json_data = json.loads(html)

                # Calculate total votes
                total_votes = int(json_data["data"]["attributes"]["num_responses"])

                # Update poll as expired in database
                await bot.db.execute(
                    "UPDATE poll SET expired = TRUE, total_votes = $1 WHERE id = $2",
                    total_votes,
                    poll["id"],
                )

                # Save poll options with final vote counts
                num_options = len(json_data["data"]["relationships"]["choices"]["data"])
                for i in range(num_options):
                    option_text = json_data["included"][i]["attributes"]["text_content"]
                    num_votes = int(
                        json_data["included"][i]["attributes"]["num_responses"]
                    )
                    option_id = int(
                        json_data["data"]["relationships"]["choices"]["data"][i]["id"]
                    )

                    # Check if option already exists
                    existing_option = await bot.db.fetch(
                        "SELECT option_id FROM poll_option WHERE option_id = $1",
                        option_id,
                    )

                    if not existing_option:
                        # Insert new option
                        await bot.db.execute(
                            "INSERT INTO poll_option(option_text, poll_id, num_votes, option_id) "
                            "VALUES ($1, $2, $3, $4)",
                            option_text,
                            poll["id"],
                            num_votes,
                            option_id,
                        )
                    else:
                        # Update existing option
                        await bot.db.execute(
                            "UPDATE poll_option SET num_votes = $1 WHERE option_id = $2",
                            num_votes,
                            option_id,
                        )

                # Update the poll record to reflect new status
                updated_poll = dict(poll)
                updated_poll["expired"] = True
                updated_poll["total_votes"] = total_votes
                updated_polls.append(updated_poll)

                logger.info(
                    "poll_expired_updated",
                    poll_id=poll["id"],
                    poll_title=poll["title"],
                    total_votes=total_votes,
                    num_options=num_options,
                )

            except Exception as e:
                logger.error(
                    "failed_to_update_expired_poll",
                    poll_id=poll["id"],
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Keep original poll if update fails
                updated_polls.append(poll)
        else:
            # Poll is not expired or already marked as expired
            updated_polls.append(poll)

    return updated_polls


async def p_poll(polls, interaction, bot):
    """
    Display poll information in a Discord embed format.

    This function processes poll data and creates a formatted Discord embed
    showing poll options, vote counts, and timing information.

    Args:
        polls: List of poll records from the database
        interaction: Discord interaction object for sending the response
        bot: The Discord bot instance

    Raises:
        Exception: If there's an error fetching poll data or creating the embed
    """
    logger = structlog.get_logger("patreon_poll.display")

    try:
        for poll in polls:
            logger.info(
                "displaying_poll",
                poll_id=poll["id"],
                poll_title=poll["title"],
                is_expired=poll["expired"],
                user_id=interaction.user.id,
            )

            if not poll["expired"]:
                # Fetch live poll data from Patreon API
                logger.info("fetching_live_poll_data", poll_id=poll["id"])
                try:
                    # Use the bot's shared HTTP client session for connection pooling
                    session = await bot.http_client.get_session()
                    html = await fetch(session, poll["api_url"])
                    json_data = json.loads(html)

                    # Extract poll options and vote counts
                    options = []
                    for i in range(
                        0, len(json_data["data"]["relationships"]["choices"]["data"])
                    ):
                        data = (
                            json_data["included"][i]["attributes"]["text_content"],
                            json_data["included"][i]["attributes"]["num_responses"],
                        )
                        options.append(data)
                    options = sorted(options, key=itemgetter(1), reverse=True)

                    logger.debug(
                        "live_poll_data_processed",
                        poll_id=poll["id"],
                        options_count=len(options),
                        total_votes=sum(opt[1] for opt in options),
                    )

                except Exception as e:
                    logger.error(
                        "failed_to_fetch_live_poll_data",
                        poll_id=poll["id"],
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    # Fall back to database data if API fails
                    options = await bot.db.fetch(
                        "SELECT option_text, num_votes FROM poll_option WHERE poll_id = $1 ORDER BY num_votes DESC",
                        poll["id"],
                    )
            else:
                # Use cached poll data from database for expired polls
                logger.debug("using_cached_poll_data", poll_id=poll["id"])
                options = await bot.db.fetch(
                    "SELECT option_text, num_votes FROM poll_option WHERE poll_id = $1 ORDER BY num_votes DESC",
                    poll["id"],
                )

            # Create the Discord embed
            # Handle both full URLs and path-only URLs from Patreon API
            poll_url = poll["poll_url"]
            if poll_url.startswith("/"):
                poll_url = f"https://www.patreon.com{poll_url}"

            embed = discord.Embed(
                title=f"📊 {poll['title']}",
                url=poll_url,
                color=(
                    discord.Color.red() if poll["expired"] else discord.Color(0x3CD63D)
                ),
                description="📊 Poll Results" if poll["expired"] else "📊 Active Poll",
                timestamp=datetime.now(timezone.utc),
            )

            # Add timing information
            if poll["expire_date"] is not None:
                time_left = poll["expire_date"] - datetime.now(timezone.utc)
                hours = int(((time_left.total_seconds() // 3600) % 24))
                embed.set_footer(
                    text=f"Poll started at {poll['start_date'].strftime('%Y-%m-%d %H:%M:%S %Z')} "
                    f"and {'closed' if poll['expired'] else 'closes'} at "
                    f"{poll['expire_date'].strftime('%Y-%m-%d %H:%M:%S %Z')} "
                    f"({time_left.days} days and {hours} hours {'ago' if poll['expired'] else 'left'})"
                )
            else:
                embed.set_footer(
                    text=f"Poll started at {poll['start_date'].strftime('%Y-%m-%d %H:%M:%S %Z')} "
                    f"and does not have a close date"
                )

            # Add poll options as embed fields
            total_votes = sum(option[1] for option in options)
            for i, option in enumerate(options):
                percentage = (option[1] / total_votes * 100) if total_votes > 0 else 0
                embed.add_field(
                    name=f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else '📊'} {option[0]}",
                    value=f"**{option[1]}** votes ({percentage:.1f}%)",
                    inline=False,
                )

            # Add total votes information
            if total_votes > 0:
                embed.add_field(
                    name="📈 Total Votes",
                    value=f"**{total_votes}** total votes cast",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

            logger.info(
                "poll_displayed_successfully",
                poll_id=poll["id"],
                total_votes=total_votes,
                options_count=len(options),
                user_id=interaction.user.id,
            )

    except Exception as e:
        logger.error(
            "poll_display_failed",
            error=str(e),
            error_type=type(e).__name__,
            user_id=interaction.user.id,
        )

        # Send user-friendly error message
        error_embed = discord.Embed(
            title="❌ Error Displaying Poll",
            description="Sorry, there was an error displaying the poll. Please try again later.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=error_embed, ephemeral=True
                )
        except Exception:
            # If we can't send the error message, just log it
            logger.error("failed_to_send_error_message", user_id=interaction.user.id)

        raise


async def search_poll(bot, query: str):
    """
    Search for polls containing the specified query in their options.

    This function performs a full-text search on poll options using PostgreSQL's
    text search capabilities and returns formatted results in a Discord embed.

    Args:
        bot: The Discord bot instance with database connection
        query: The search query string to look for in poll options

    Returns:
        discord.Embed: An embed containing the search results

    Raises:
        Exception: If there's an error executing the database query
    """
    logger = structlog.get_logger("patreon_poll.search")

    try:
        logger.info("poll_search_started", query=query, query_length=len(query))

        # Execute the full-text search query
        async with TimingContext(logger, "execute_search_query") as timing_ctx:
            search_results = await bot.db.fetch(
                "SELECT poll_id, option_text FROM poll_option WHERE tokens @@ plainto_tsquery($1)",
                query,
            )
            timing_ctx.add_info(results_count=len(search_results), query=query)

        logger.debug(
            "search_query_completed", query=query, results_found=len(search_results)
        )

        # Create the results embed
        embed = discord.Embed(
            title="🔍 Poll Search Results",
            color=discord.Color(0x3CD63D) if search_results else discord.Color.orange(),
            description=f"Query: **{query}**",
            timestamp=datetime.now(timezone.utc),
        )

        if not search_results:
            embed.add_field(
                name="No Results Found",
                value="No poll options match your search query. Try using different keywords or check your spelling.",
                inline=False,
            )
            embed.color = discord.Color.orange()
            logger.info("poll_search_no_results", query=query)
        else:
            # Process each search result
            for i, result in enumerate(search_results):
                try:
                    # Fetch poll details for each result
                    poll_details = await bot.db.fetchrow(
                        "SELECT title, index_serial FROM poll WHERE id = $1",
                        result["poll_id"],
                    )

                    if poll_details:
                        embed.add_field(
                            name=f"📊 {poll_details['title']}",
                            value=f"**Poll #{poll_details['index_serial']}** - {result['option_text']}",
                            inline=False,
                        )
                    else:
                        logger.warning(
                            "poll_details_not_found",
                            poll_id=result["poll_id"],
                            query=query,
                        )

                except Exception as e:
                    logger.error(
                        "error_processing_search_result",
                        poll_id=result["poll_id"],
                        error=str(e),
                        error_type=type(e).__name__,
                        query=query,
                    )
                    continue

            # Add summary information
            embed.set_footer(
                text=f"Found {len(search_results)} matching poll option(s)"
            )

            logger.info(
                "poll_search_completed", query=query, results_count=len(search_results)
            )

        return embed

    except Exception as e:
        logger.error(
            "poll_search_failed", query=query, error=str(e), error_type=type(e).__name__
        )

        # Create error embed
        error_embed = discord.Embed(
            title="❌ Search Error",
            description=f"An error occurred while searching for polls with query: **{query}**\n\nPlease try again later.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )

        return error_embed


class PollCog(commands.Cog, name="Poll"):
    """
    A Discord cog for managing and displaying Patreon polls.

    This cog provides commands for:
    - Displaying active or specific polls
    - Listing polls by year
    - Fetching new polls from Patreon API
    - Searching through poll options

    The cog integrates with a PostgreSQL database to store poll data
    and provides rich Discord embeds for user interaction.
    """

    def __init__(self, bot):
        """
        Initialize the PollCog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = structlog.get_logger("patreon_poll.cog")
        self.logger.info("poll_cog_initialized")

    @app_commands.command(
        name="poll",
        description="Display the latest active poll or a specific poll by ID",
    )
    @app_commands.describe(
        poll_id="Optional: Specific poll ID to display (defaults to latest active or most recent poll)"
    )
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: (i.user.id, i.channel.id))
    async def poll(self, interaction: discord.Interaction, poll_id: int = None):
        """
        Display poll information to the user.

        This command shows either the latest active poll or a specific poll by ID.
        If no active polls exist and no ID is specified, it shows the most recent poll.

        Args:
            interaction: The Discord interaction object
            poll_id: Optional poll ID to display specific poll
        """
        self.logger.info(
            "poll_command_started",
            user_id=interaction.user.id,
            user_name=str(interaction.user),
            guild_id=interaction.guild.id if interaction.guild else None,
            requested_poll_id=poll_id,
        )

        try:
            # Check for active polls first
            async with TimingContext(self.logger, "fetch_active_polls") as timing_ctx:
                active_polls = await self.bot.db.fetch(
                    "SELECT * FROM poll WHERE expire_date > now()"
                )
                timing_ctx.add_info(active_polls_count=len(active_polls))

            # Also check for polls that might have expired but aren't marked as such
            async with TimingContext(
                self.logger, "fetch_potentially_expired_polls"
            ) as timing_ctx:
                potentially_expired_polls = await self.bot.db.fetch(
                    "SELECT * FROM poll WHERE expired = FALSE AND expire_date IS NOT NULL AND expire_date <= now()"
                )
                timing_ctx.add_info(
                    potentially_expired_count=len(potentially_expired_polls)
                )

            # Update any expired polls
            if potentially_expired_polls:
                self.logger.info(
                    "checking_for_expired_polls",
                    user_id=interaction.user.id,
                    potentially_expired_count=len(potentially_expired_polls),
                )

                async with TimingContext(
                    self.logger, "update_expired_polls"
                ) as timing_ctx:
                    updated_polls = await check_and_update_expired_polls(
                        self.bot, potentially_expired_polls
                    )
                    timing_ctx.add_info(
                        polls_updated=len(
                            [p for p in updated_polls if p.get("expired", False)]
                        )
                    )

            # Re-fetch active polls after potential updates
            async with TimingContext(self.logger, "refetch_active_polls") as timing_ctx:
                active_polls = await self.bot.db.fetch(
                    "SELECT * FROM poll WHERE expire_date > now()"
                )
                timing_ctx.add_info(active_polls_count=len(active_polls))

            if active_polls and poll_id is None:
                # Display active polls
                self.logger.info(
                    "displaying_active_polls",
                    user_id=interaction.user.id,
                    active_polls_count=len(active_polls),
                )
                await p_poll(active_polls, interaction, self.bot)
            else:
                # Handle specific poll ID or latest poll
                if poll_id is None:
                    # Get the latest poll by finding the maximum index_serial
                    async with TimingContext(
                        self.logger, "get_latest_poll_id"
                    ) as timing_ctx:
                        latest_poll_result = await self.bot.db.fetch(
                            "SELECT MAX(index_serial) FROM poll"
                        )
                        poll_id = latest_poll_result[0][0]
                        timing_ctx.add_info(latest_poll_id=poll_id)

                    # Check if no polls exist
                    if poll_id is None:
                        error_embed = discord.Embed(
                            title="❌ No Polls Available",
                            description="No polls are currently available in the database.",
                            color=discord.Color.red(),
                            timestamp=datetime.now(timezone.utc),
                        )
                        await interaction.response.send_message(
                            embed=error_embed, ephemeral=True
                        )
                        self.logger.warning(
                            "no_polls_in_database", user_id=interaction.user.id
                        )
                        return

                    self.logger.info(
                        "using_latest_poll_id",
                        user_id=interaction.user.id,
                        poll_id=poll_id,
                    )
                else:
                    self.logger.info(
                        "using_specified_poll_id",
                        user_id=interaction.user.id,
                        poll_id=poll_id,
                    )

                # Validate poll ID
                if poll_id <= 0:
                    error_embed = discord.Embed(
                        title="❌ Invalid Poll ID",
                        description="Poll ID must be a positive number.",
                        color=discord.Color.red(),
                        timestamp=datetime.now(timezone.utc),
                    )
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )
                    self.logger.warning(
                        "invalid_poll_id_provided",
                        user_id=interaction.user.id,
                        poll_id=poll_id,
                    )
                    return

                # Fetch the specific poll
                async with TimingContext(
                    self.logger, "fetch_specific_poll"
                ) as timing_ctx:
                    poll_data = await self.bot.db.fetch(
                        "SELECT * FROM poll WHERE index_serial = $1", int(poll_id)
                    )
                    timing_ctx.add_info(poll_id=poll_id, found=len(poll_data) > 0)

                if not poll_data:
                    # Poll not found
                    error_embed = discord.Embed(
                        title="❌ Poll Not Found",
                        description=f"No poll found with ID **{poll_id}**. Use `/polllist` to see available polls.",
                        color=discord.Color.red(),
                        timestamp=datetime.now(timezone.utc),
                    )
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )
                    self.logger.warning(
                        "poll_not_found", user_id=interaction.user.id, poll_id=poll_id
                    )
                    return

                self.logger.info(
                    "displaying_specific_poll",
                    user_id=interaction.user.id,
                    poll_id=poll_id,
                    poll_title=poll_data[0]["title"] if poll_data else "Unknown",
                )

                await p_poll(poll_data, interaction, self.bot)

            self.logger.info(
                "poll_command_completed", user_id=interaction.user.id, poll_id=poll_id
            )

        except Exception as e:
            self.logger.error(
                "poll_command_failed",
                user_id=interaction.user.id,
                poll_id=poll_id,
                error=str(e),
                error_type=type(e).__name__,
            )

            # Send user-friendly error message
            error_embed = discord.Embed(
                title="❌ Error Loading Poll",
                description="Sorry, there was an error loading the poll. Please try again later.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                else:
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )
            except Exception:
                self.logger.error(
                    "failed_to_send_poll_error_message", user_id=interaction.user.id
                )

            raise

    @poll.error
    async def on_poll_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, discord.app_commands.errors.CommandOnCooldown):
            self.logger.warning(
                "poll_command_cooldown",
                user_id=interaction.user.id,
                retry_after=error.retry_after,
            )
            try:
                await interaction.response.send_message(
                    f"Please wait {round(error.retry_after, 2)} seconds before using this command again.",
                    ephemeral=True,
                )
            except Exception as e:
                self.logger.error(
                    "failed_to_send_cooldown_message",
                    user_id=interaction.user.id,
                    error=str(e),
                )
            # Don't let the error propagate to the global handler since we've handled it
            return
        else:
            self.logger.error(
                "poll_command_error",
                user_id=interaction.user.id,
                error=str(error),
                error_type=type(error).__name__,
            )
            # Let other errors propagate to the global handler

    @app_commands.command(
        name="polllist",
        description="Display a list of polls from a specific year with their IDs",
    )
    @app_commands.describe(
        year="The year to list polls from (defaults to current year)"
    )
    @commands.check(is_bot_channel)
    async def poll_list(
        self,
        interaction: discord.Interaction,
        year: int = datetime.now(timezone.utc).year,
    ):
        """
        Display a list of polls from the specified year.

        This command shows all polls from a given year with their titles and IDs,
        ordered by start date. Restricted to bot channels to avoid spam.

        Args:
            interaction: The Discord interaction object
            year: The year to list polls from (defaults to current year)
        """
        self.logger.info(
            "poll_list_command_started",
            user_id=interaction.user.id,
            user_name=str(interaction.user),
            guild_id=interaction.guild.id if interaction.guild else None,
            requested_year=year,
        )

        try:
            # Validate year input
            current_year = datetime.now(timezone.utc).year
            if year < 2000 or year > current_year + 1:
                error_embed = discord.Embed(
                    title="❌ Invalid Year",
                    description=f"Please provide a valid year between 2000 and {current_year + 1}.",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc),
                )
                await interaction.response.send_message(
                    embed=error_embed, ephemeral=True
                )
                self.logger.warning(
                    "invalid_year_provided", user_id=interaction.user.id, year=year
                )
                return

            # Fetch polls for the specified year
            async with TimingContext(self.logger, "fetch_polls_by_year") as timing_ctx:
                polls_years = await self.bot.db.fetch(
                    "SELECT title, index_serial, start_date, expired FROM poll WHERE date_part('year', start_date) = $1 ORDER BY start_date",
                    year,
                )
                timing_ctx.add_info(year=year, polls_found=len(polls_years))

            self.logger.debug(
                "polls_fetched_for_year",
                year=year,
                polls_count=len(polls_years),
                user_id=interaction.user.id,
            )

            if not polls_years:
                # No polls found for the year
                embed = discord.Embed(
                    title="📊 No Polls Found",
                    description=f"No polls were found for the year **{year}**.\n\nTry a different year or check if polls exist for that period.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(
                    name="💡 Tip",
                    value="Use `/poll` to see the latest polls or try recent years.",
                    inline=False,
                )

                await interaction.response.send_message(embed=embed)
                self.logger.info(
                    "no_polls_found_for_year", year=year, user_id=interaction.user.id
                )
            else:
                # Create polls list embed
                embed = discord.Embed(
                    title="📊 Poll List",
                    color=discord.Color(0x3CD63D),
                    description=f"**Polls from {year}** ({len(polls_years)} total)",
                    timestamp=datetime.now(timezone.utc),
                )

                # Count active vs expired polls
                active_count = sum(1 for poll in polls_years if not poll["expired"])
                expired_count = len(polls_years) - active_count

                # Add summary field
                embed.add_field(
                    name="📈 Summary",
                    value=f"🟢 Active: **{active_count}**\n🔴 Expired: **{expired_count}**",
                    inline=True,
                )

                # Add polls to embed (limit to prevent embed size issues)
                max_polls_to_show = 20
                polls_to_show = polls_years[:max_polls_to_show]

                for poll in polls_to_show:
                    status_emoji = "🟢" if not poll["expired"] else "🔴"
                    start_date = poll["start_date"].strftime("%m/%d")

                    embed.add_field(
                        name=f"{status_emoji} {poll['title'][:50]}{'...' if len(poll['title']) > 50 else ''}",
                        value=f"**ID:** {poll['index_serial']} | **Started:** {start_date}",
                        inline=False,
                    )

                # Add note if there are more polls than shown
                if len(polls_years) > max_polls_to_show:
                    embed.add_field(
                        name="ℹ️ Note",
                        value=f"Showing first {max_polls_to_show} of {len(polls_years)} polls. Use specific poll IDs with `/poll` command.",
                        inline=False,
                    )

                embed.set_footer(text=f"Use /poll <id> to view a specific poll")

                await interaction.response.send_message(embed=embed)

                self.logger.info(
                    "poll_list_displayed",
                    year=year,
                    polls_count=len(polls_years),
                    active_count=active_count,
                    expired_count=expired_count,
                    user_id=interaction.user.id,
                )

        except Exception as e:
            self.logger.error(
                "poll_list_command_failed",
                user_id=interaction.user.id,
                year=year,
                error=str(e),
                error_type=type(e).__name__,
            )

            # Send user-friendly error message
            error_embed = discord.Embed(
                title="❌ Error Loading Poll List",
                description="Sorry, there was an error loading the poll list. Please try again later.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                else:
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )
            except Exception:
                self.logger.error(
                    "failed_to_send_poll_list_error_message",
                    user_id=interaction.user.id,
                )

            raise

    @poll_list.error
    async def isError(self, interaction: discord.Interaction, error):
        if isinstance(error, commands.CheckFailure):
            self.logger.info(
                "poll_list_permission_denied",
                user_id=interaction.user.id,
                channel_id=interaction.channel.id,
                error_type="CheckFailure",
            )
            await interaction.response.send_message(
                "Please use this command in <#361694671631548417> only. It takes up quite a bit of space.",
                ephemeral=True,
            )
        else:
            self.logger.error(
                "poll_list_error",
                user_id=interaction.user.id,
                error=str(error),
                error_type=type(error).__name__,
            )

    @app_commands.command(
        name="getpoll", description="Fetch and update polls from Patreon API"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def getpoll(self, interaction: discord.Interaction):
        """Fetch and update polls from Patreon API with detailed progress feedback."""
        logger = structlog.get_logger("patreon_poll.command")

        # Defer the response since this operation can take time
        await interaction.response.defer(ephemeral=True)

        # Log the command execution
        logger.info(
            "getpoll_command_started",
            user_id=interaction.user.id,
            user_name=str(interaction.user),
            guild_id=interaction.guild.id if interaction.guild else None,
        )

        try:
            # Send initial progress message
            await interaction.followup.send(
                "🔄 Starting poll fetch operation...", ephemeral=True
            )

            # Execute the poll fetch operation
            stats = await get_poll(self.bot)

            # Create detailed success message
            embed = discord.Embed(
                title="✅ Poll Fetch Completed",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )

            # Add statistics fields
            embed.add_field(
                name="📊 Processing Summary",
                value=f"• Pages processed: **{stats['pages_processed']}**\n"
                f"• Polls found: **{stats['polls_found']}**\n"
                f"• New polls added: **{stats['new_polls_added']}**",
                inline=False,
            )

            embed.add_field(
                name="📈 Poll Details",
                value=f"• Active polls: **{stats['active_polls_added']}**\n"
                f"• Expired polls: **{stats['expired_polls_added']}**\n"
                f"• Poll options added: **{stats['poll_options_added']}**",
                inline=False,
            )

            if stats["errors"] > 0:
                embed.add_field(
                    name="⚠️ Errors",
                    value=f"**{stats['errors']}** errors occurred during processing.\nCheck logs for details.",
                    inline=False,
                )
                embed.color = discord.Color.orange()

            # Add footer with execution info
            embed.set_footer(text=f"Executed by {interaction.user.display_name}")

            # Send the detailed results
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Log successful completion
            logger.info(
                "getpoll_command_completed", user_id=interaction.user.id, **stats
            )

        except Exception as e:
            # Create error embed
            error_embed = discord.Embed(
                title="❌ Poll Fetch Failed",
                description=f"An error occurred while fetching polls: {str(e)}",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )
            error_embed.set_footer(text=f"Executed by {interaction.user.display_name}")

            # Send error message to user
            await interaction.followup.send(embed=error_embed, ephemeral=True)

            # Log the error
            logger.error(
                "getpoll_command_failed",
                user_id=interaction.user.id,
                user_name=str(interaction.user),
                error=str(e),
                error_type=type(e).__name__,
            )

            # Re-raise the exception for global error handling
            raise

    @app_commands.command(
        name="findpoll",
        description="Search through poll options using keywords or phrases",
    )
    @app_commands.describe(
        query="The search term to look for in poll options (keywords or phrases)"
    )
    async def findpoll(self, interaction: discord.Interaction, query: str):
        """
        Search for polls containing specific keywords in their options.

        This command performs a full-text search through all poll options
        to find matches for the provided query string.

        Args:
            interaction: The Discord interaction object
            query: The search query string
        """
        self.logger.info(
            "findpoll_command_started",
            user_id=interaction.user.id,
            user_name=str(interaction.user),
            guild_id=interaction.guild.id if interaction.guild else None,
            query=query,
            query_length=len(query),
        )

        try:
            # Validate query input
            if not query or len(query.strip()) < 2:
                error_embed = discord.Embed(
                    title="❌ Invalid Search Query",
                    description="Please provide a search query with at least 2 characters.",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc),
                )
                error_embed.add_field(
                    name="💡 Example",
                    value="Try searching for: `character names`, `story elements`, or `specific topics`",
                    inline=False,
                )
                await interaction.response.send_message(
                    embed=error_embed, ephemeral=True
                )
                self.logger.warning(
                    "invalid_search_query", user_id=interaction.user.id, query=query
                )
                return

            # Sanitize query for logging (remove potential sensitive content)
            clean_query = query.strip()[:100]  # Limit length for logging

            self.logger.debug(
                "executing_poll_search",
                user_id=interaction.user.id,
                query_length=len(clean_query),
            )

            # Defer response since search might take time
            await interaction.response.defer()

            # Execute the search
            async with TimingContext(
                self.logger, "poll_search_execution"
            ) as timing_ctx:
                search_embed = await search_poll(self.bot, clean_query)
                timing_ctx.add_info(query=clean_query)

            # Send the search results
            await interaction.followup.send(embed=search_embed)

            self.logger.info(
                "findpoll_command_completed",
                user_id=interaction.user.id,
                query=clean_query,
                query_length=len(clean_query),
            )

        except Exception as e:
            self.logger.error(
                "findpoll_command_failed",
                user_id=interaction.user.id,
                query=query[:100] if query else "None",
                error=str(e),
                error_type=type(e).__name__,
            )

            # Send user-friendly error message
            error_embed = discord.Embed(
                title="❌ Search Error",
                description="Sorry, there was an error searching for polls. Please try again later.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )
            error_embed.add_field(
                name="💡 Tip",
                value="Try simplifying your search query or using different keywords.",
                inline=False,
            )

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                else:
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )
            except Exception:
                self.logger.error(
                    "failed_to_send_findpoll_error_message", user_id=interaction.user.id
                )

            raise


async def setup(bot):
    await bot.add_cog(PollCog(bot))

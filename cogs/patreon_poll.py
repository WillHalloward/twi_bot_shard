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
            "errors": 0
        }

        url = "https://www.patreon.com/api/posts?include=Cpoll.choices%2Cpoll.current_user_responses.poll&filter[campaign_id]=568211"

        # Get existing poll IDs for reference
        async with TimingContext(logger, "fetch_existing_polls") as timing_ctx:
            poll_ids = await bot.db.fetch("SELECT id FROM poll")
            timing_ctx.add_info(existing_poll_count=len(poll_ids))

        logger.info("poll_fetch_started", 
                   initial_url=url, 
                   existing_polls=len(poll_ids),
                   request_id=ctx.request_id)

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
                    logger.debug("page_data_parsed", 
                               page=stats["pages_processed"],
                               posts_count=len(json_data.get("data", [])))
                except Exception as e:
                    logger.error("json_parse_failed", 
                               page=stats["pages_processed"],
                               error=str(e),
                               error_type=type(e).__name__)
                    stats["errors"] += 1
                    continue

                # Process each post
                for posts in json_data["data"]:
                    if posts["relationships"]["poll"]["data"] is not None:
                        stats["polls_found"] += 1
                        poll_api_id = int(posts["relationships"]["poll"]["data"]["id"])

                        # Check if poll already exists
                        async with TimingContext(logger, "check_poll_exists") as timing_ctx:
                            poll_id = await bot.db.fetch(
                                "SELECT * FROM poll WHERE id = $1", poll_api_id
                            )
                            timing_ctx.add_info(poll_api_id=poll_api_id, exists=bool(poll_id))

                        if not poll_id:
                            logger.info("processing_new_poll", 
                                      poll_api_id=poll_api_id,
                                      poll_url=posts["attributes"]["patreon_url"])

                            try:
                                # Fetch detailed poll data
                                async with TimingContext(logger, "fetch_poll_details") as timing_ctx:
                                    session = await bot.http_client.get_session()
                                    html = await fetch(
                                        session, posts["relationships"]["poll"]["links"]["related"]
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

                                title = json_data2["data"]["attributes"]["question_text"]
                                num_options = len(json_data2["data"]["relationships"]["choices"]["data"])

                                # Determine if poll is expired
                                is_expired = (
                                    closes_at_converted is None
                                    or closes_at_converted < datetime.now(timezone.utc)
                                )

                                # Insert poll record
                                async with TimingContext(logger, "insert_poll_record") as timing_ctx:
                                    if is_expired:
                                        await bot.db.execute(
                                            "INSERT INTO poll(api_url, poll_url, id, start_date, expire_date, title, total_votes, "
                                            "expired, num_options) "
                                            "VALUES ($1,$2,$3,$4,$5,$6,$7, TRUE, $8)",
                                            posts["relationships"]["poll"]["links"]["related"],
                                            posts["attributes"]["patreon_url"],
                                            poll_api_id,
                                            open_at_converted,
                                            closes_at_converted,
                                            title,
                                            int(json_data2["data"]["attributes"]["num_responses"]),
                                            num_options,
                                        )
                                        stats["expired_polls_added"] += 1

                                        # Insert poll options for expired polls
                                        for i in range(num_options):
                                            await bot.db.execute(
                                                "INSERT INTO poll_option(option_text, poll_id, num_votes, option_id)"
                                                "VALUES ($1,$2,$3,$4)",
                                                json_data2["included"][i]["attributes"]["text_content"],
                                                poll_api_id,
                                                int(json_data2["included"][i]["attributes"]["num_responses"]),
                                                int(json_data2["data"]["relationships"]["choices"]["data"][i]["id"]),
                                            )
                                            stats["poll_options_added"] += 1
                                    else:
                                        await bot.db.execute(
                                            "INSERT INTO poll(api_url, poll_url, id, start_date, expire_date, title, expired, "
                                            "num_options) "
                                            "VALUES ($1,$2,$3,$4,$5,$6, FALSE, $7)",
                                            posts["relationships"]["poll"]["links"]["related"],
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
                                        num_options=num_options
                                    )

                                stats["new_polls_added"] += 1
                                logger.info("poll_added_successfully",
                                          poll_api_id=poll_api_id,
                                          title=title,
                                          is_expired=is_expired,
                                          num_options=num_options,
                                          start_date=open_at_converted.isoformat(),
                                          expire_date=closes_at_converted.isoformat() if closes_at_converted else None)

                            except Exception as e:
                                logger.error("poll_processing_failed",
                                           poll_api_id=poll_api_id,
                                           error=str(e),
                                           error_type=type(e).__name__)
                                stats["errors"] += 1

                # Check for next page
                try:
                    url = json_data["links"]["next"]
                    logger.info("proceeding_to_next_page", 
                              page=stats["pages_processed"],
                              next_url=url)
                except KeyError:
                    logger.info("pagination_complete", 
                              total_pages=stats["pages_processed"])
                    break

            except Exception as e:
                logger.error("page_processing_failed",
                           page=stats["pages_processed"],
                           url=url,
                           error=str(e),
                           error_type=type(e).__name__)
                stats["errors"] += 1
                break

        logger.info("poll_fetch_completed", 
                   **stats,
                   request_id=ctx.request_id)

        return stats


async def p_poll(polls, interaction, bot):
    for poll in polls:
        if not poll["expired"]:
            # Use the bot's shared HTTP client session for connection pooling
            session = await bot.http_client.get_session()
            html = await fetch(session, poll["api_url"])
            json_data = json.loads(html)
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
        else:
            options = await bot.db.fetch(
                "SELECT option_text, num_votes FROM poll_option WHERE poll_id = $1 ORDER BY num_votes DESC",
                poll["id"],
            )
        embed = discord.Embed(
            title="Poll",
            color=discord.Color(0x3CD63D),
            description=f"**[{poll['title']}]({poll['poll_url']})**",
        )
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

        for option in options:
            embed.add_field(name=option[0], value=option[1], inline=False)
        await interaction.response.send_message(embed=embed)


async def search_poll(bot, query: str):
    test = await bot.db.fetch(
        "SELECT poll_id, option_text FROM poll_option WHERE tokens @@ plainto_tsquery($1)",
        query,
    )
    embed = discord.Embed(
        title="Poll search results",
        color=discord.Color(0x3CD63D),
        description=f"Query: **{query}**",
    )
    for results in test:
        polls_year = await bot.db.fetchrow(
            "select title, index_serial from poll where id = $1", results["poll_id"]
        )
        embed.add_field(
            name=polls_year["title"],
            value=f"{polls_year['index_serial']} - {results['option_text']}",
            inline=False,
        )
    return embed


class PollCog(commands.Cog, name="Poll"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = structlog.get_logger("patreon_poll.cog")

    @app_commands.command(
        name="poll",
        description="Posts the latest poll or a specific poll",
    )
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: (i.user.id, i.channel.id))
    async def poll(self, interaction: discord.Interaction, poll_id: int = None):
        active_polls = await self.bot.db.fetch(
            "SELECT * FROM poll WHERE expire_date > now()"
        )
        if active_polls and poll_id is None:
            await p_poll(active_polls, interaction, self.bot)
        else:
            last_poll = await self.bot.db.fetch("SELECT COUNT (*) FROM poll")
            if poll_id is None:
                poll_id = last_poll[0][0]
            value = await self.bot.db.fetch(
                "SELECT * FROM poll ORDER BY id OFFSET $1 LIMIT 1", int(poll_id) - 1
            )
            await p_poll(value, interaction, self.bot)

    @poll.error
    async def on_poll_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, discord.app_commands.errors.CommandOnCooldown):
            self.logger.info("poll_command_cooldown",
                           user_id=interaction.user.id,
                           retry_after=error.retry_after)
            await interaction.response.send_message(
                f"Please wait {round(error.retry_after, 2)} seconds before using this command again.",
                ephemeral=True,
            )
        else:
            self.logger.error("poll_command_error",
                            user_id=interaction.user.id,
                            error=str(error),
                            error_type=type(error).__name__)

    @app_commands.command(
        name="polllist",
        description="Shows the list of poll ids sorted by year.",
    )
    @commands.check(is_bot_channel)
    async def poll_list(
        self,
        interaction: discord.Interaction,
        year: int = datetime.now(timezone.utc).year,
    ):
        polls_years = await self.bot.db.fetch(
            "SELECT title, index_serial FROM poll WHERE date_part('year', start_date) = $1 ORDER BY start_date",
            year,
        )
        if not polls_years:
            await interaction.response.send_message(
                "Sorry there were no polls that year that i could find :("
            )
        else:
            embed = discord.Embed(
                title="List of polls",
                color=discord.Color(0x3CD63D),
                description=f"**{year}**",
            )
            for polls in polls_years:
                embed.add_field(
                    name=f"{polls['title']}", value=polls["index_serial"], inline=False
                )
            await interaction.response.send_message(embed=embed)

    @poll_list.error
    async def isError(self, interaction: discord.Interaction, error):
        if isinstance(error, commands.CheckFailure):
            self.logger.info("poll_list_permission_denied",
                           user_id=interaction.user.id,
                           channel_id=interaction.channel.id,
                           error_type="CheckFailure")
            await interaction.response.send_message(
                "Please use this command in <#361694671631548417> only. It takes up quite a bit of space.",
                ephemeral=True,
            )
        else:
            self.logger.error("poll_list_error",
                            user_id=interaction.user.id,
                            error=str(error),
                            error_type=type(error).__name__)

    @app_commands.command(name="getpoll", description="Fetch and update polls from Patreon API")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def getpoll(self, interaction: discord.Interaction):
        """Fetch and update polls from Patreon API with detailed progress feedback."""
        logger = structlog.get_logger("patreon_poll.command")

        # Defer the response since this operation can take time
        await interaction.response.defer(ephemeral=True)

        # Log the command execution
        logger.info("getpoll_command_started", 
                   user_id=interaction.user.id,
                   user_name=str(interaction.user),
                   guild_id=interaction.guild.id if interaction.guild else None)

        try:
            # Send initial progress message
            await interaction.followup.send("🔄 Starting poll fetch operation...", ephemeral=True)

            # Execute the poll fetch operation
            stats = await get_poll(self.bot)

            # Create detailed success message
            embed = discord.Embed(
                title="✅ Poll Fetch Completed",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )

            # Add statistics fields
            embed.add_field(
                name="📊 Processing Summary",
                value=f"• Pages processed: **{stats['pages_processed']}**\n"
                      f"• Polls found: **{stats['polls_found']}**\n"
                      f"• New polls added: **{stats['new_polls_added']}**",
                inline=False
            )

            embed.add_field(
                name="📈 Poll Details",
                value=f"• Active polls: **{stats['active_polls_added']}**\n"
                      f"• Expired polls: **{stats['expired_polls_added']}**\n"
                      f"• Poll options added: **{stats['poll_options_added']}**",
                inline=False
            )

            if stats['errors'] > 0:
                embed.add_field(
                    name="⚠️ Errors",
                    value=f"**{stats['errors']}** errors occurred during processing.\nCheck logs for details.",
                    inline=False
                )
                embed.color = discord.Color.orange()

            # Add footer with execution info
            embed.set_footer(text=f"Executed by {interaction.user.display_name}")

            # Send the detailed results
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Log successful completion
            logger.info("getpoll_command_completed",
                       user_id=interaction.user.id,
                       **stats)

        except Exception as e:
            # Create error embed
            error_embed = discord.Embed(
                title="❌ Poll Fetch Failed",
                description=f"An error occurred while fetching polls: {str(e)}",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            error_embed.set_footer(text=f"Executed by {interaction.user.display_name}")

            # Send error message to user
            await interaction.followup.send(embed=error_embed, ephemeral=True)

            # Log the error
            logger.error("getpoll_command_failed",
                        user_id=interaction.user.id,
                        user_name=str(interaction.user),
                        error=str(e),
                        error_type=type(e).__name__)

            # Re-raise the exception for global error handling
            raise

    @app_commands.command(
        name="findpoll",
        description="Searches poll questions for a given query",
    )
    async def findpoll(self, interaction: discord.Interaction, query: str):
        await interaction.response.send_message(
            embed=await search_poll(self.bot, query)
        )


async def setup(bot):
    await bot.add_cog(PollCog(bot))

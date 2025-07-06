"""
The Wandering Inn cog for the Twi Bot Shard.

This module provides commands related to The Wandering Inn web serial, including
password retrieval for Patreon supporters, wiki searches, invisible text lookup,
and other TWI-specific functionality.
"""

import datetime
import json
import logging
import os
from typing import List
from PIL import Image, ImageSequence
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from googleapiclient.discovery import build
from os import remove
import config
from cogs.patreon_poll import fetch
from utils.permissions import (
    admin_or_me_check,
    admin_or_me_check_wrapper,
    app_admin_or_me_check,
    is_bot_channel,
    is_bot_channel_wrapper,
    app_is_bot_channel,
)
from utils.error_handling import handle_command_errors, handle_interaction_errors
from utils.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    ExternalServiceError,
    DatabaseError,
    PermissionError,
)


def google_search(search_term, api_key, cse_id, **kwargs):
    """
    Perform a Google Custom Search using the provided API credentials.

    Args:
        search_term (str): The search query to execute
        api_key (str): Google API key for authentication
        cse_id (str): Custom Search Engine ID
        **kwargs: Additional parameters to pass to the search API

    Returns:
        dict: The search results as returned by the Google API
    """
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, num=9, **kwargs).execute()
    return res


class TwiCog(commands.Cog, name="The Wandering Inn"):
    """
    Cog providing commands related to The Wandering Inn web serial.

    This cog includes commands for retrieving Patreon passwords, searching the TWI wiki,
    finding content within the story, and accessing special text features like invisible text
    and colored text used in the serial.

    Attributes:
        bot: The bot instance
        invis_text_cache: Cache of invisible text chapter titles for autocomplete
        last_run: Timestamp of the last time the password command was run publicly
    """

    def __init__(self, bot):
        """
        Initialize the TwiCog.

        Args:
            bot: The bot instance to which this cog is attached
        """
        self.bot = bot
        self.invis_text_cache = None
        self.last_run = datetime.datetime.now() - datetime.timedelta(minutes=10)

    async def cog_load(self) -> None:
        """
        Load initial data when the cog is added to the bot.

        This method is called automatically when the cog is loaded.
        It populates the invisible text cache for use in autocomplete.
        """
        self.invis_text_cache = await self.bot.db.fetch(
            "SELECT DISTINCT title FROM invisible_text_twi"
        )

    # button class for linking people to the chapter
    class Button(discord.ui.Button):
        """
        A simple link button for directing users to a chapter.

        This button is used in various commands to provide a direct link
        to the relevant chapter on The Wandering Inn website.
        """

        def __init__(self, url):
            """
            Initialize the button with a URL.

            Args:
                url (str): The URL to link to
            """
            super().__init__(style=discord.ButtonStyle.link, url=url, label="Chapter")

    @app_commands.command(
        name="password",
        description="Gives the password for the latest chapter for patreons or instructions for non patreons.",
    )
    @handle_interaction_errors
    async def password(self, interaction: discord.Interaction):
        """
        Provide the current Patreon password or instructions on how to get it.

        If used in an allowed channel, this command provides the current password
        for accessing Patreon-exclusive content. If used elsewhere, it provides
        instructions on how to obtain the password through various methods.

        Args:
            interaction: The interaction that triggered the command

        Raises:
            DatabaseError: If database operations fail
            ValidationError: If password data is invalid
        """
        try:
            logging.info(
                f"TWI PASSWORD: User {interaction.user.id} ({interaction.user.display_name}) requesting password in channel {interaction.channel.id}"
            )

            if interaction.channel.id in config.password_allowed_channel_ids:
                # Fetch password from database with error handling
                try:
                    password = await self.bot.db.fetchrow(
                        "SELECT password, link "
                        "FROM password_link "
                        "WHERE password IS NOT NULL "
                        "ORDER BY serial_id DESC "
                        "LIMIT 1"
                    )
                except Exception as e:
                    logging.error(
                        f"TWI PASSWORD ERROR: Database query failed for user {interaction.user.id}: {e}"
                    )
                    raise DatabaseError(
                        message="❌ **Database Error**\nFailed to retrieve password from database"
                    ) from e

                # Validate password data
                if not password:
                    logging.warning(
                        f"TWI PASSWORD WARNING: No password found in database for user {interaction.user.id}"
                    )
                    raise ValidationError(
                        message="❌ **No Password Available**\nNo password is currently available. Please contact an admin."
                    )

                if not password["password"] or not password["link"]:
                    logging.warning(
                        f"TWI PASSWORD WARNING: Invalid password data for user {interaction.user.id}"
                    )
                    raise ValidationError(
                        message="❌ **Invalid Password Data**\nPassword data is incomplete. Please contact an admin."
                    )

                # Check rate limiting
                is_public = (
                    self.last_run
                    < datetime.datetime.now() - datetime.timedelta(minutes=10)
                )

                # Create enhanced embed response
                embed = discord.Embed(
                    title="🔐 Patreon Password",
                    description=f"**Password:** `{password['password']}`",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now(),
                )

                embed.add_field(
                    name="📖 Chapter Link",
                    value=f"[Click here to read]({password['link']})",
                    inline=False,
                )

                if is_public:
                    embed.add_field(
                        name="ℹ️ Note",
                        value="This password is posted publicly. Future requests in the next 10 minutes will be private.",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="🔒 Private Response",
                        value="This is a private response to avoid spam.",
                        inline=False,
                    )

                embed.set_footer(text="Password provided for Patreon supporters")

                view = discord.ui.View().add_item(self.Button(password["link"]))

                if is_public:
                    await interaction.response.send_message(embed=embed, view=view)
                    self.last_run = datetime.datetime.now()
                    logging.info(
                        f"TWI PASSWORD: Public password provided to user {interaction.user.id}"
                    )
                else:
                    await interaction.response.send_message(
                        embed=embed, view=view, ephemeral=True
                    )
                    logging.info(
                        f"TWI PASSWORD: Private password provided to user {interaction.user.id}"
                    )

            else:
                # Create enhanced instructions embed
                embed = discord.Embed(
                    title="🔐 How to Get the Patreon Password",
                    description="Here are the ways to access the latest chapter password:",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(),
                )

                embed.add_field(
                    name="1️⃣ Discord + Patreon Integration",
                    value=f"Link your Discord to Patreon, then go to <#{config.inn_general_channel_id}> and check pins or use `/password`.\n"
                    "Use `/connectdiscord` if you need help linking accounts.",
                    inline=False,
                )

                embed.add_field(
                    name="2️⃣ Email Notifications",
                    value="You'll receive an email with the password every time pirateaba posts it.",
                    inline=False,
                )

                embed.add_field(
                    name="3️⃣ Direct Patreon Access",
                    value="Visit [pirateaba's Patreon](https://www.patreon.com/pirateaba) and check the latest posts for the password.",
                    inline=False,
                )

                embed.set_footer(text="Support The Wandering Inn on Patreon!")

                await interaction.response.send_message(embed=embed)
                logging.info(
                    f"TWI PASSWORD: Instructions provided to user {interaction.user.id} in non-allowed channel {interaction.channel.id}"
                )

        except (DatabaseError, ValidationError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Password Request Failed**\nUnexpected error while retrieving password: {str(e)}"
            logging.error(
                f"TWI PASSWORD ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @app_commands.command(
        name="connectdiscord",
        description="Information for patreons on how to connect their patreon account to discord.",
    )
    @handle_interaction_errors
    async def connect_discord(self, interaction: discord.Interaction):
        """
        Provide instructions on connecting Patreon and Discord accounts.

        This command sends a link to Patreon's official documentation on
        how to link Discord and Patreon accounts to receive role benefits.

        Args:
            interaction: The interaction that triggered the command
        """
        await interaction.response.send_message(
            "Check this link https://support.patreon.com/hc/en-us/articles/212052266-How-do-I-receive-my-Discord-role"
        )

    @app_commands.command(
        name="wiki",
        description="Searches the The Wandering Inn wiki for a matching article.",
    )
    @handle_interaction_errors
    async def wiki(self, interaction: discord.Interaction, query: str):
        """
        Search The Wandering Inn wiki for articles matching the query.

        This command queries the TWI wiki API and returns matching articles
        with links. If available, it also includes a thumbnail image from
        the first result.

        Args:
            interaction: The interaction that triggered the command
            query: The search term to look for on the wiki

        Raises:
            ValidationError: If query is invalid or too short
            ExternalServiceError: If wiki API requests fail
        """
        try:
            # Input validation
            if not query or len(query.strip()) < 2:
                raise ValidationError(
                    message="❌ **Invalid Search Query**\nPlease provide a search query with at least 2 characters."
                )

            query = query.strip()
            if len(query) > 100:
                raise ValidationError(
                    message="❌ **Query Too Long**\nSearch query must be 100 characters or less."
                )

            logging.info(
                f"TWI WIKI: User {interaction.user.id} ({interaction.user.display_name}) searching for: '{query[:50]}{'...' if len(query) > 50 else ''}'"
            )

            # Defer response since API calls might take time
            await interaction.response.defer()

            # Use the bot's shared HTTP client session for connection pooling
            try:
                session = await self.bot.http_client.get_session()
            except Exception as e:
                logging.error(
                    f"TWI WIKI ERROR: Failed to get HTTP session for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="❌ **Connection Error**\nFailed to establish connection to wiki"
                ) from e

            # Search for articles
            try:
                search_url = f"https://thewanderinginn.fandom.com/api.php?action=query&generator=search&gsrsearch={query}&format=json&prop=info|images&inprop=url"
                html = await fetch(session, search_url)

                if not html:
                    raise ExternalServiceError(
                        message="❌ **Wiki API Error**\nReceived empty response from wiki API"
                    )

            except Exception as e:
                logging.error(
                    f"TWI WIKI ERROR: Wiki API request failed for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="❌ **Wiki Search Failed**\nFailed to search the wiki. Please try again later."
                ) from e

            # Parse search results
            try:
                wiki_data = json.loads(html)

                if "query" not in wiki_data or "pages" not in wiki_data["query"]:
                    # No results found
                    embed = discord.Embed(
                        title="🔍 Wiki Search Results",
                        description=f"No articles found matching **{query}**",
                        color=discord.Color.orange(),
                        timestamp=datetime.datetime.now(),
                    )

                    embed.add_field(
                        name="💡 Search Tips",
                        value="• Try different keywords\n• Check spelling\n• Use broader search terms\n• Try character or location names",
                        inline=False,
                    )

                    embed.set_footer(text="Search powered by The Wandering Inn Wiki")

                    await interaction.followup.send(embed=embed)
                    logging.info(
                        f"TWI WIKI: No results found for user {interaction.user.id} query: '{query}'"
                    )
                    return

                sorted_json_data = sorted(
                    wiki_data["query"]["pages"].values(), key=lambda k: k["index"]
                )

            except (json.JSONDecodeError, KeyError) as e:
                logging.error(
                    f"TWI WIKI ERROR: Failed to parse wiki response for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="❌ **Wiki Response Error**\nFailed to parse wiki search results"
                ) from e

            # Create results embed
            embed = discord.Embed(
                title="🔍 Wiki Search Results",
                description=f"Found **{len(sorted_json_data)}** article{'s' if len(sorted_json_data) != 1 else ''} for **{query}**",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(),
            )

            # Add search results (limit to prevent embed size issues)
            max_results = 10
            results_to_show = sorted_json_data[:max_results]

            for i, result in enumerate(results_to_show, 1):
                try:
                    title = result.get("title", "Unknown Title")
                    url = result.get("fullurl", "#")

                    embed.add_field(
                        name=f"{i}. {title[:50]}{'...' if len(title) > 50 else ''}",
                        value=f"[Read Article]({url})",
                        inline=False,
                    )
                except Exception as e:
                    logging.warning(
                        f"TWI WIKI WARNING: Failed to process result {i} for user {interaction.user.id}: {e}"
                    )
                    continue

            # Try to get thumbnail from first result
            try:
                if (
                    sorted_json_data
                    and "images" in sorted_json_data[0]
                    and sorted_json_data[0]["images"]
                ):
                    image_title = sorted_json_data[0]["images"][0]["title"]
                    image_url = f"https://thewanderinginn.fandom.com/api.php?action=query&format=json&titles={image_title}&prop=imageinfo&iiprop=url"

                    image_json = await fetch(session, image_url)
                    if image_json:
                        image_data = json.loads(image_json)
                        image_pages = image_data.get("query", {}).get("pages", {})

                        if image_pages:
                            image_info = next(iter(image_pages.values()))
                            if "imageinfo" in image_info and image_info["imageinfo"]:
                                thumbnail_url = image_info["imageinfo"][0].get("url")
                                if thumbnail_url:
                                    embed.set_thumbnail(url=thumbnail_url)

            except Exception as e:
                logging.warning(
                    f"TWI WIKI WARNING: Failed to get thumbnail for user {interaction.user.id}: {e}"
                )
                # Continue without thumbnail

            # Add note if there are more results
            if len(sorted_json_data) > max_results:
                embed.add_field(
                    name="ℹ️ Note",
                    value=f"Showing first {max_results} of {len(sorted_json_data)} results. Try a more specific search for fewer results.",
                    inline=False,
                )

            embed.set_footer(text="Search powered by The Wandering Inn Wiki")

            await interaction.followup.send(embed=embed)
            logging.info(
                f"TWI WIKI: Successfully returned {len(results_to_show)} results for user {interaction.user.id}"
            )

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Wiki Search Failed**\nUnexpected error while searching wiki: {str(e)}"
            logging.error(
                f"TWI WIKI ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @app_commands.command(
        name="find",
        description="Does a google search on 'Wanderinginn.com' and returns the results",
    )
    @app_commands.check(app_is_bot_channel)
    @handle_interaction_errors
    async def find(self, interaction: discord.Interaction, query: str):
        """
        Search wanderinginn.com using Google Custom Search.

        This command performs a Google search restricted to the Wandering Inn
        website and returns the results with snippets and links. Due to the
        potentially large response, this command is restricted to bot channels.

        Args:
            interaction: The interaction that triggered the command
            query: The search term to look for on wanderinginn.com

        Raises:
            ValidationError: If query is invalid or too short
            ExternalServiceError: If Google API requests fail
        """
        try:
            # Input validation
            if not query or len(query.strip()) < 2:
                raise ValidationError(
                    message="❌ **Invalid Search Query**\nPlease provide a search query with at least 2 characters."
                )

            query = query.strip()
            if len(query) > 200:
                raise ValidationError(
                    message="❌ **Query Too Long**\nSearch query must be 200 characters or less."
                )

            logging.info(
                f"TWI FIND: User {interaction.user.id} ({interaction.user.display_name}) searching wanderinginn.com for: '{query[:50]}{'...' if len(query) > 50 else ''}'"
            )

            # Defer response since Google API calls might take time
            await interaction.response.defer()

            # Perform Google search with error handling
            try:
                results = google_search(
                    query, config.google_api_key, config.google_cse_id
                )

                if not results:
                    raise ExternalServiceError(
                        message="❌ **Search API Error**\nReceived empty response from Google Search API"
                    )

            except Exception as e:
                logging.error(
                    f"TWI FIND ERROR: Google search failed for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="❌ **Search Failed**\nFailed to search wanderinginn.com. Please try again later."
                ) from e

            # Check for results
            try:
                total_results = results.get("searchInformation", {}).get(
                    "totalResults", "0"
                )
                search_items = results.get("items", [])

                if total_results == "0" or not search_items:
                    # No results found
                    embed = discord.Embed(
                        title="🔍 Search Results",
                        description=f"No results found on wanderinginn.com for **{query}**",
                        color=discord.Color.orange(),
                        timestamp=datetime.datetime.now(),
                    )

                    embed.add_field(
                        name="💡 Search Tips",
                        value="• Try different keywords\n• Check spelling\n• Use broader search terms\n• Try character names or chapter numbers",
                        inline=False,
                    )

                    embed.set_footer(text="Search powered by Google Custom Search")

                    await interaction.followup.send(embed=embed)
                    logging.info(
                        f"TWI FIND: No results found for user {interaction.user.id} query: '{query}'"
                    )
                    return

            except Exception as e:
                logging.error(
                    f"TWI FIND ERROR: Failed to parse search results for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="❌ **Search Response Error**\nFailed to parse search results"
                ) from e

            # Create results embed
            embed = discord.Embed(
                title="🔍 Search Results",
                description=f"Found **{total_results}** result{'s' if total_results != '1' else ''} on wanderinginn.com for **{query}**",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(),
            )

            # Add search results (limit to prevent embed size issues)
            max_results = 8
            results_to_show = search_items[:max_results]

            for i, result in enumerate(results_to_show, 1):
                try:
                    title = result.get("title", "Unknown Title")
                    snippet = result.get("snippet", "No description available")
                    link = result.get("link", "#")

                    # Truncate long titles and snippets
                    if len(title) > 60:
                        title = title[:60] + "..."
                    if len(snippet) > 150:
                        snippet = snippet[:150] + "..."

                    embed.add_field(
                        name=f"{i}. {title}",
                        value=f"{snippet}\n[Read More]({link})",
                        inline=False,
                    )

                except Exception as e:
                    logging.warning(
                        f"TWI FIND WARNING: Failed to process result {i} for user {interaction.user.id}: {e}"
                    )
                    continue

            # Add note if there are more results
            if len(search_items) > max_results:
                embed.add_field(
                    name="ℹ️ Note",
                    value=f"Showing first {max_results} of {total_results} results. Try a more specific search for fewer results.",
                    inline=False,
                )

            embed.set_footer(text="Search powered by Google Custom Search")

            await interaction.followup.send(embed=embed)
            logging.info(
                f"TWI FIND: Successfully returned {len(results_to_show)} results for user {interaction.user.id}"
            )

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Search Failed**\nUnexpected error while searching wanderinginn.com: {str(e)}"
            logging.error(
                f"TWI FIND ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=error_msg) from e

    @app_commands.command(
        name="invistext", description="Gives a list of all the invisible text in TWI."
    )
    @handle_interaction_errors
    async def invis_text(self, interaction: discord.Interaction, chapter: str = None):
        """
        Retrieve invisible text from The Wandering Inn chapters.

        This command either lists all chapters containing invisible text
        or provides the specific invisible text from a requested chapter.
        Invisible text is special content that's hidden in the web serial
        by making the text color match the background.

        Args:
            interaction: The interaction that triggered the command
            chapter: Optional chapter name to get specific invisible text

        Raises:
            ValidationError: If chapter parameter is invalid
            DatabaseError: If database operations fail
        """
        try:
            logging.info(
                f"TWI INVISTEXT: User {interaction.user.id} ({interaction.user.display_name}) requesting invisible text{f' for chapter: {chapter[:50]}' if chapter else ' list'}"
            )

            if chapter is None:
                # List all chapters with invisible text
                try:
                    invis_text_chapters = await self.bot.db.fetch(
                        "SELECT title, COUNT(*) FROM invisible_text_twi GROUP BY title, date ORDER BY date"
                    )
                except Exception as e:
                    logging.error(
                        f"TWI INVISTEXT ERROR: Database query failed for user {interaction.user.id}: {e}"
                    )
                    raise DatabaseError(
                        message="❌ **Database Error**\nFailed to retrieve invisible text chapters from database"
                    ) from e

                if not invis_text_chapters:
                    embed = discord.Embed(
                        title="👻 Invisible Text",
                        description="No chapters with invisible text found in the database.",
                        color=discord.Color.orange(),
                        timestamp=datetime.datetime.now(),
                    )

                    embed.add_field(
                        name="ℹ️ Information",
                        value="Invisible text is special content hidden in chapters by making the text color match the background.",
                        inline=False,
                    )

                    await interaction.response.send_message(embed=embed)
                    logging.info(
                        f"TWI INVISTEXT: No chapters found for user {interaction.user.id}"
                    )
                    return

                # Create chapters list embed
                embed = discord.Embed(
                    title="👻 Chapters with Invisible Text",
                    description=f"Found **{len(invis_text_chapters)}** chapter{'s' if len(invis_text_chapters) != 1 else ''} containing invisible text",
                    color=discord.Color.purple(),
                    timestamp=datetime.datetime.now(),
                )

                # Add chapters (limit to prevent embed size issues)
                max_chapters = 20
                chapters_to_show = invis_text_chapters[:max_chapters]

                for chapter_data in chapters_to_show:
                    try:
                        title = chapter_data.get("title", "Unknown Chapter")
                        count = chapter_data.get("count", 0)

                        # Truncate long titles
                        display_title = title[:60] + "..." if len(title) > 60 else title

                        embed.add_field(
                            name=f"📖 {display_title}",
                            value=f"**{count}** invisible text{'s' if count != 1 else ''}",
                            inline=False,
                        )
                    except Exception as e:
                        logging.warning(
                            f"TWI INVISTEXT WARNING: Failed to process chapter for user {interaction.user.id}: {e}"
                        )
                        continue

                # Add note if there are more chapters
                if len(invis_text_chapters) > max_chapters:
                    embed.add_field(
                        name="ℹ️ Note",
                        value=f"Showing first {max_chapters} of {len(invis_text_chapters)} chapters. Use the chapter parameter to search for specific chapters.",
                        inline=False,
                    )

                embed.add_field(
                    name="💡 Tip",
                    value="Use `/invistext chapter:<chapter_name>` to see invisible text from a specific chapter.",
                    inline=False,
                )

                embed.set_footer(text="Invisible text data from The Wandering Inn")

                await interaction.response.send_message(embed=embed)
                logging.info(
                    f"TWI INVISTEXT: Successfully listed {len(chapters_to_show)} chapters for user {interaction.user.id}"
                )

            else:
                # Search for specific chapter
                # Input validation
                chapter = chapter.strip()
                if len(chapter) < 2:
                    raise ValidationError(
                        message="❌ **Invalid Chapter Name**\nChapter name must be at least 2 characters long."
                    )

                if len(chapter) > 100:
                    raise ValidationError(
                        message="❌ **Chapter Name Too Long**\nChapter name must be 100 characters or less."
                    )

                try:
                    texts = await self.bot.db.fetch(
                        "SELECT title, content FROM invisible_text_twi WHERE lower(title) similar to lower($1)",
                        chapter,
                    )
                except Exception as e:
                    logging.error(
                        f"TWI INVISTEXT ERROR: Database search failed for user {interaction.user.id}: {e}"
                    )
                    raise DatabaseError(
                        message="❌ **Database Error**\nFailed to search for invisible text in database"
                    ) from e

                if texts:
                    # Create results embed
                    embed = discord.Embed(
                        title="👻 Invisible Text Found",
                        description=f"Found **{len(texts)}** invisible text{'s' if len(texts) != 1 else ''} matching **{chapter}**",
                        color=discord.Color.purple(),
                        timestamp=datetime.datetime.now(),
                    )

                    # Add invisible texts (limit to prevent embed size issues)
                    max_texts = 10
                    texts_to_show = texts[:max_texts]

                    for i, text in enumerate(texts_to_show, 1):
                        try:
                            title = text.get("title", "Unknown Chapter")
                            content = text.get("content", "No content available")

                            # Truncate long content
                            if len(content) > 500:
                                content = content[:500] + "..."

                            embed.add_field(
                                name=f"{i}. {title}",
                                value=f"```{content}```",
                                inline=False,
                            )
                        except Exception as e:
                            logging.warning(
                                f"TWI INVISTEXT WARNING: Failed to process text {i} for user {interaction.user.id}: {e}"
                            )
                            continue

                    # Add note if there are more texts
                    if len(texts) > max_texts:
                        embed.add_field(
                            name="ℹ️ Note",
                            value=f"Showing first {max_texts} of {len(texts)} invisible texts. Try a more specific chapter name for fewer results.",
                            inline=False,
                        )

                    embed.set_footer(text="Invisible text data from The Wandering Inn")

                    await interaction.response.send_message(embed=embed)
                    logging.info(
                        f"TWI INVISTEXT: Successfully found {len(texts_to_show)} invisible texts for user {interaction.user.id}"
                    )

                else:
                    # No results found
                    embed = discord.Embed(
                        title="👻 No Invisible Text Found",
                        description=f"No invisible text found matching **{chapter}**",
                        color=discord.Color.orange(),
                        timestamp=datetime.datetime.now(),
                    )

                    embed.add_field(
                        name="💡 Search Tips",
                        value="• Try the exact chapter title\n• Use partial chapter names\n• Check spelling\n• Use `/invistext` without parameters to see all available chapters",
                        inline=False,
                    )

                    embed.set_footer(text="Invisible text data from The Wandering Inn")

                    await interaction.response.send_message(embed=embed)
                    logging.info(
                        f"TWI INVISTEXT: No invisible text found for user {interaction.user.id} query: '{chapter}'"
                    )

        except (ValidationError, DatabaseError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Invisible Text Request Failed**\nUnexpected error while retrieving invisible text: {str(e)}"
            logging.error(
                f"TWI INVISTEXT ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise DatabaseError(message=error_msg) from e

    @invis_text.autocomplete("chapter")
    async def invis_text_autocomplete(
        self,
        interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete suggestions for chapter names with invisible text.

        This method filters the cached chapter titles based on the user's current input
        and returns matching options for the autocomplete dropdown.

        Args:
            interaction: The interaction that triggered the autocomplete
            current: The current text input by the user

        Returns:
            A list of up to 25 matching chapter name choices
        """
        ln = []
        for x in self.invis_text_cache:
            ln.append(x["title"])
        return [
            app_commands.Choice(name=title, value=title)
            for title in ln
            if current.lower() in title.lower() or current == ""
        ][0:25]

    @app_commands.command(
        name="coloredtext", description="List of all the different colored texts in twi"
    )
    @handle_interaction_errors
    async def colored_text(self, interaction: discord.Interaction):
        """
        Display a comprehensive list of colored text used in The Wandering Inn.

        This command creates an embed with information about all the different
        colored text used in the web serial, including their hex codes, visual
        representation, and the chapters where they first appeared. The colors
        are used for various special elements like skills, classes, and character
        speech.

        Args:
            interaction: The interaction that triggered the command
        """
        embed = discord.Embed(title="Twi's different colored text")
        embed.add_field(
            name="Red skills and classes",
            value="#FF0000\n"
            f"{'<:FF0000:666429504834633789>' * 4}"
            "\n[3.17T](https://wanderinginn.com/2017/09/27/3-17-t/)",
        )
        embed.add_field(
            name="Ser Raim skill",
            value="#EB0E0E\n"
            f"{'<:EB0E0E:666429505019183144>' * 4}"
            "\n[6.43E](https://wanderinginn.com/2019/09/10/6-43-e/)",
        )
        embed.add_field(
            name="Ivolethe summoning fire",
            value="#E01D1D\n"
            f"{'<:E01D1D:666429504863993908>' * 4}"
            "\n[Interlude 4](https://wanderinginn.com/2017/12/30/interlude-4/)",
        )
        embed.add_field(
            name="Unique Skills",
            value="#99CC00\n"
            f"{'<:99CC00:666429504998211594>' * 4}"
            "\n[2.19](https://wanderinginn.com/2017/05/03/2-19/)",
        )
        embed.add_field(
            name="Erin's landmark skill",
            value="#FF9900\n"
            f"{'<:FF9900:666435308480364554>' * 4}"
            "\n[5.44](https://wanderinginn.com/2018/12/08/5-44/)",
        )
        embed.add_field(
            name="Divine/Temporary skills",
            value="#FFD700\n"
            f"{'<:FFD700:666429505031897107>' * 4}"
            "\n[4.23E](https://wanderinginn.com/2018/03/27/4-23-e/)",
        )
        embed.add_field(
            name="Class restoration / Conviction skill",
            value="#99CCFF\n"
            f"{'<:99CCFF:667886770679054357>' * 4}"
            "\n[3.20T](https://wanderinginn.com/2017/10/03/3-20-t/)",
        )
        embed.add_field(
            name="Winter fae talking",
            value="#8AE8FF\n"
            f"{'<:8AE8FF:666429505015119922>' * 4}"
            "\n[2.06](https://wanderinginn.com/2017/03/28/2-06/)",
        )
        embed.add_field(
            name="Spring fae talking",
            value="#96BE50\n"
            f"{'<:96BE50:666429505014857728>' * 4}"
            "\n[5.11E](https://wanderinginn.com/2018/08/14/5-11-e/)",
        )
        embed.add_field(
            name="Grand Queen talking",
            value="#FFCC00\n"
            f"{'<:FFCC00:674267820678316052>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Silent Queen talking and purple skills",
            value="#CC99FF\n"
            f"{'<:CC99FF:674267820732841984>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Armored Queen talking",
            value="#999999\n"
            f"{'<:999999:674267820820791306>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Twisted Queen talking",
            value="#993300\n"
            f"{'<:993300:674267820694962186>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Flying Queen talking",
            value="#99CC00\n"
            f"{'<:99CC00:666429504998211594>' * 4}"
            "\n[5.54](https://wanderinginn.com/2019/01/22/5-54-2/)",
        )
        embed.add_field(
            name="Magnolia charm skill",
            value="#FDDBFF, #FFB8FD,\n#FD78FF, #FB00FF\n"
            "<:FDDBFF:674370583412080670><:FFB8FD:674385325572751371><:FD78FF:674385325208109088><:FB00FF:674385325522681857>"
            "\n[2.31](https://wanderinginn.com/2017/06/21/2-31/)",
        )
        embed.add_field(
            name="Ceria cold skill",
            value="#CCFFFF, #99CCFF,\n#3366FF\n"
            "<:CCFFFF:962498665317011527><:99CCFF:667886770679054357><:3366FF:962498751086338088>"
            "\n[8.36H](https://wanderinginn.com/2021/08/15/8-36-h/)",
        )
        embed.add_field(
            name="Siren water skill",
            value="#00CCFF\n"
            f"{'<:00CCFF:962498765879656498>' * 4}"
            "\n[8.36H](https://wanderinginn.com/2021/08/15/8-36-h/)",
        )
        embed.add_field(
            name="Invisible Skills/Text",
            value="#0C0E0E,\n"
            f"{'<:0C0E0E:666452140994330624>' * 4}\n"
            "[1.08 R](https://wanderinginn.com/2016/12/18/1-08-r//)",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="update_password",
        description="Updates the password and link from /password",
    )
    @app_commands.check(app_admin_or_me_check)
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @handle_interaction_errors
    async def update_password(
        self, interaction: discord.Interaction, password: str, link: str
    ):
        """
        Update the Patreon password and chapter link in the database.

        This admin-only command updates the password and link that are provided
        by the /password command. It records the user who made the update and
        the current timestamp.

        Args:
            interaction: The interaction that triggered the command
            password: The new Patreon password to store
            link: The URL to the chapter that requires the password

        Raises:
            ValidationError: If password or link parameters are invalid
            DatabaseError: If database operations fail
            PermissionError: If user lacks admin permissions
        """
        try:
            # Input validation
            if not password or len(password.strip()) == 0:
                raise ValidationError(
                    message="❌ **Invalid Password**\nPassword cannot be empty"
                )

            if not link or len(link.strip()) == 0:
                raise ValidationError(
                    message="❌ **Invalid Link**\nLink cannot be empty"
                )

            password = password.strip()
            link = link.strip()

            # Validate password length and content
            if len(password) < 3:
                raise ValidationError(
                    message="❌ **Password Too Short**\nPassword must be at least 3 characters long"
                )

            if len(password) > 100:
                raise ValidationError(
                    message="❌ **Password Too Long**\nPassword must be 100 characters or less"
                )

            # Basic URL validation
            if not (link.startswith("http://") or link.startswith("https://")):
                raise ValidationError(
                    message="❌ **Invalid URL**\nLink must be a valid URL starting with http:// or https://"
                )

            if len(link) > 500:
                raise ValidationError(
                    message="❌ **URL Too Long**\nLink must be 500 characters or less"
                )

            # Additional security check - ensure it's a wanderinginn.com link
            if (
                "wanderinginn.com" not in link.lower()
                and "patreon.com" not in link.lower()
            ):
                logging.warning(
                    f"TWI UPDATE_PASSWORD WARNING: Non-standard URL provided by admin {interaction.user.id}: {link}"
                )

            logging.info(
                f"TWI UPDATE_PASSWORD: Admin {interaction.user.id} ({interaction.user.display_name}) updating password and link"
            )

            # Insert into database with error handling
            try:
                await self.bot.db.execute(
                    "INSERT INTO password_link(password, link, user_id, date) VALUES ($1, $2, $3, now())",
                    password,
                    link,
                    interaction.user.id,
                )
            except Exception as e:
                logging.error(
                    f"TWI UPDATE_PASSWORD ERROR: Database insert failed for admin {interaction.user.id}: {e}"
                )
                raise DatabaseError(
                    message="❌ **Database Error**\nFailed to update password in database"
                ) from e

            # Create success embed
            embed = discord.Embed(
                title="✅ Password Updated Successfully",
                description="The Patreon password and chapter link have been updated",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(),
            )

            embed.add_field(name="🔐 New Password", value=f"`{password}`", inline=False)

            embed.add_field(
                name="📖 Chapter Link", value=f"[View Chapter]({link})", inline=False
            )

            embed.add_field(
                name="👤 Updated By",
                value=f"{interaction.user.mention}\n**ID:** {interaction.user.id}",
                inline=True,
            )

            embed.add_field(
                name="⏰ Updated At",
                value=f"<t:{int(datetime.datetime.now().timestamp())}:F>",
                inline=True,
            )

            embed.add_field(
                name="ℹ️ Note",
                value="This password is now available via the `/password` command in allowed channels.",
                inline=False,
            )

            embed.set_footer(text="Password update logged for security")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            logging.info(
                f"TWI UPDATE_PASSWORD: Successfully updated password for admin {interaction.user.id}"
            )

        except (ValidationError, PermissionError, DatabaseError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Password Update Failed**\nUnexpected error while updating password: {str(e)}"
            logging.error(
                f"TWI UPDATE_PASSWORD ERROR: Unexpected error for admin {interaction.user.id}: {e}"
            )
            raise DatabaseError(message=error_msg) from e

    # Reddit verification functionality has been removed or disabled
    # This feature previously allowed users to link their Discord and Reddit accounts
    # for access to the TWI_Patreon subreddit


async def setup(bot):
    """
    Set up the TwiCog.

    This function is called automatically by the bot when loading the extension.

    Args:
        bot: The bot instance to attach the cog to
    """
    await bot.add_cog(TwiCog(bot))

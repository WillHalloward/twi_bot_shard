"""
Search functionality for The Wandering Inn cog.

This module handles wiki searches and Google Custom Search functionality
for finding content related to The Wandering Inn.
"""

import datetime
import json
import logging
from typing import Dict, Any

import discord
from discord import app_commands
from discord.ext import commands

import config
from cogs.patreon_poll import fetch
from cogs.twi_utils import (
    google_search,
    ChapterLinkButton,
    log_command_usage,
    log_command_error,
    truncate_text,
    validate_search_query,
)
from utils.error_handling import handle_interaction_errors
from utils.exceptions import ValidationError, ExternalServiceError
from utils.permissions import app_is_bot_channel


class SearchMixin:
    """Mixin class providing search-related commands for The Wandering Inn cog."""

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
            try:
                query = validate_search_query(query, min_length=2, max_length=100)
            except ValueError as e:
                raise ValidationError(message=f"❌ **Invalid Search Query**\n{str(e)}")

            log_command_usage(
                "WIKI",
                interaction.user.id,
                interaction.user.display_name,
                f"searching for: '{truncate_text(query, 50)}'",
            )

            # Defer response since API calls might take time
            await interaction.response.defer()

            # Use the bot's shared HTTP client session for connection pooling
            try:
                session = await self.bot.http_client.get_session()
            except Exception as e:
                log_command_error(
                    "WIKI", interaction.user.id, e, "Failed to get HTTP session"
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
                log_command_error(
                    "WIKI", interaction.user.id, e, "Wiki API request failed"
                )
                raise ExternalServiceError(
                    message="❌ **Wiki Search Failed**\nFailed to search the wiki. Please try again later."
                ) from e

            # Parse search results
            try:
                wiki_data = json.loads(html)

                if "query" not in wiki_data or "pages" not in wiki_data["query"]:
                    await self._send_no_wiki_results(interaction, query)
                    return

                sorted_json_data = sorted(
                    wiki_data["query"]["pages"].values(), key=lambda k: k["index"]
                )

            except (json.JSONDecodeError, KeyError) as e:
                log_command_error(
                    "WIKI", interaction.user.id, e, "Failed to parse wiki response"
                )
                raise ExternalServiceError(
                    message="❌ **Wiki Response Error**\nFailed to parse wiki search results"
                ) from e

            # Create and send results embed
            await self._send_wiki_results(interaction, query, sorted_json_data)

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Wiki Search Failed**\nUnexpected error while searching wiki: {str(e)}"
            log_command_error("WIKI", interaction.user.id, e)
            raise ExternalServiceError(message=error_msg) from e

    async def _send_no_wiki_results(self, interaction: discord.Interaction, query: str):
        """Send embed when no wiki results are found."""
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

    async def _send_wiki_results(
        self, interaction: discord.Interaction, query: str, results: list
    ):
        """Send embed with wiki search results."""
        embed = discord.Embed(
            title="🔍 Wiki Search Results",
            description=f"Found **{len(results)}** result{'s' if len(results) != 1 else ''} for **{query}**",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(),
        )

        # Add search results (limit to prevent embed size issues)
        max_results = 8
        results_to_show = results[:max_results]

        for result in results_to_show:
            try:
                title = result.get("title", "Unknown Article")
                url = result.get("fullurl", "")

                # Truncate long titles
                display_title = truncate_text(title, 60)

                if url:
                    embed.add_field(
                        name=f"📖 {display_title}",
                        value=f"[Read article]({url})",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name=f"📖 {display_title}",
                        value="Article found (no direct link available)",
                        inline=False,
                    )
            except Exception as e:
                logging.warning(
                    f"TWI WIKI WARNING: Failed to process result for user {interaction.user.id}: {e}"
                )
                continue

        # Add note if there are more results
        if len(results) > max_results:
            embed.add_field(
                name="ℹ️ Note",
                value=f"Showing first {max_results} of {len(results)} results. Try more specific search terms for better results.",
                inline=False,
            )

        embed.set_footer(text="Search powered by The Wandering Inn Wiki")

        # Try to get thumbnail from first result
        if results_to_show and "images" in results_to_show[0]:
            try:
                # This would require additional API calls to get actual image URLs
                # For now, we'll skip thumbnail functionality to keep it simple
                pass
            except Exception:
                pass

        await interaction.followup.send(embed=embed)
        logging.info(
            f"TWI WIKI: Successfully found {len(results_to_show)} results for user {interaction.user.id}"
        )

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
            try:
                query = validate_search_query(query, min_length=2, max_length=200)
            except ValueError as e:
                raise ValidationError(message=f"❌ **Invalid Search Query**\n{str(e)}")

            log_command_usage(
                "FIND",
                interaction.user.id,
                interaction.user.display_name,
                f"searching wanderinginn.com for: '{truncate_text(query, 50)}'",
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
                log_command_error(
                    "FIND", interaction.user.id, e, "Google search failed"
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
                    await self._send_no_find_results(interaction, query)
                    return

            except Exception as e:
                log_command_error(
                    "FIND", interaction.user.id, e, "Failed to parse search results"
                )
                raise ExternalServiceError(
                    message="❌ **Search Response Error**\nFailed to parse search results"
                ) from e

            # Create and send results embed
            await self._send_find_results(
                interaction, query, total_results, search_items
            )

        except (ValidationError, ExternalServiceError):
            # Re-raise our custom exceptions to be handled by the decorator
            raise
        except Exception as e:
            error_msg = f"❌ **Search Failed**\nUnexpected error while searching wanderinginn.com: {str(e)}"
            log_command_error("FIND", interaction.user.id, e)
            raise ExternalServiceError(message=error_msg) from e

    async def _send_no_find_results(self, interaction: discord.Interaction, query: str):
        """Send embed when no search results are found."""
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

    async def _send_find_results(
        self,
        interaction: discord.Interaction,
        query: str,
        total_results: str,
        search_items: list,
    ):
        """Send embed with search results."""
        embed = discord.Embed(
            title="🔍 Search Results",
            description=f"Found **{total_results}** result{'s' if total_results != '1' else ''} on wanderinginn.com for **{query}**",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(),
        )

        # Add search results (limit to prevent embed size issues)
        max_results = 8
        results_to_show = search_items[:max_results]

        for item in results_to_show:
            try:
                title = item.get("title", "Unknown Page")
                link = item.get("link", "")
                snippet = item.get("snippet", "No description available")

                # Truncate long titles and snippets
                display_title = truncate_text(title, 60)
                display_snippet = truncate_text(snippet, 150)

                if link:
                    embed.add_field(
                        name=f"📖 {display_title}",
                        value=f"{display_snippet}\n[Read more]({link})",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name=f"📖 {display_title}",
                        value=display_snippet,
                        inline=False,
                    )
            except Exception as e:
                logging.warning(
                    f"TWI FIND WARNING: Failed to process search result for user {interaction.user.id}: {e}"
                )
                continue

        # Add note if there are more results
        if len(search_items) > max_results:
            embed.add_field(
                name="ℹ️ Note",
                value=f"Showing first {max_results} of {total_results} results. Try more specific search terms for better results.",
                inline=False,
            )

        embed.set_footer(text="Search powered by Google Custom Search")

        await interaction.followup.send(embed=embed)
        logging.info(
            f"TWI FIND: Successfully found {len(results_to_show)} results for user {interaction.user.id}"
        )

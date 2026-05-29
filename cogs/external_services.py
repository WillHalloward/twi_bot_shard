"""External services cog for the Twi Bot Shard.

This module provides commands for interacting with external services like AO3.
"""

import asyncio
import logging
import re

import AO3
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.base_cog import BaseCog
from utils.command_groups import admin
from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    ExternalServiceError,
    ValidationError,
)


class ExternalServices(BaseCog, name="ExternalServices"):
    """Commands for interacting with external services."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.ao3_session = None
        self.ao3_login_successful = False
        self.ao3_login_in_progress = False

    async def _initialize_ao3_session(self, max_retries: int = 3) -> None:
        """Initialize AO3 session with retry logic.

        This method runs the blocking AO3 authentication in an executor to avoid
        blocking the event loop. If authentication fails, it will retry with
        exponential backoff up to max_retries times.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
        """
        if self.ao3_login_in_progress:
            self.logger.warning(
                "AO3 login already in progress, skipping duplicate attempt"
            )
            return

        self.ao3_login_in_progress = True

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(
                    f"Attempting AO3 login (attempt {attempt}/{max_retries})"
                )

                loop = asyncio.get_event_loop()
                session = await loop.run_in_executor(
                    None,
                    AO3.Session,
                    str(config.ao3_username),
                    str(config.ao3_password),
                )

                self.ao3_session = session
                self.ao3_login_successful = True
                self.logger.info("AO3 login successful")
                self.ao3_login_in_progress = False
                return

            except Exception as e:
                self.logger.error(
                    f"AO3 login failed (attempt {attempt}/{max_retries}): {e}",
                    exc_info=True,
                )

                if attempt < max_retries:
                    wait_time = 2**attempt
                    self.logger.info(f"Retrying AO3 login in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error("AO3 login failed after all retry attempts")
                    self.ao3_login_successful = False

        self.ao3_login_in_progress = False

    async def cog_load(self) -> None:
        """Load initial data when the cog is added to the bot."""
        cog_method_names = {"ao3_status"}

        for cmd in admin.commands:
            if cmd.callback.__name__ in cog_method_names:
                cmd.binding = self

        asyncio.create_task(self._initialize_ao3_session())

    @admin.command(
        name="ao3_status",
        description="Check AO3 authentication status or retry login",
    )
    @app_commands.describe(retry="Set to True to retry AO3 login")
    @app_commands.checks.has_permissions(administrator=True)
    @handle_interaction_errors
    async def ao3_status(
        self, interaction: discord.Interaction, retry: bool = False
    ) -> None:
        """Check AO3 authentication status or manually retry login."""
        await interaction.response.defer(ephemeral=True)

        if retry:
            if self.ao3_login_in_progress:
                await interaction.followup.send(
                    "AO3 login is already in progress. Please wait...",
                    ephemeral=True,
                )
                return

            self.logger.info(
                f"Admin {interaction.user.id} triggered manual AO3 login retry"
            )
            await interaction.followup.send(
                "Retrying AO3 login... This may take up to 90 seconds per attempt.",
                ephemeral=True,
            )

            asyncio.create_task(self._initialize_ao3_session())

            await asyncio.sleep(2)

            if self.ao3_login_successful:
                await interaction.edit_original_response(
                    content="AO3 login successful!"
                )
            elif self.ao3_login_in_progress:
                await interaction.edit_original_response(
                    content="AO3 login in progress... Check status again in a moment."
                )
            else:
                await interaction.edit_original_response(
                    content="AO3 login failed. Check bot logs for details."
                )
        else:
            if self.ao3_login_successful:
                status_msg = (
                    "**AO3 Status: Connected**\nAuthentication is working properly."
                )
            elif self.ao3_login_in_progress:
                status_msg = "**AO3 Status: Connecting**\nLogin attempt in progress..."
            else:
                status_msg = "**AO3 Status: Disconnected**\nAuthentication failed. Use `retry: True` to retry."

            await interaction.followup.send(status_msg, ephemeral=True)

    @app_commands.command(name="ao3", description="Posts information about a ao3 work")
    @handle_interaction_errors
    async def ao3(self, interaction: discord.Interaction, ao3_url: str) -> None:
        """Display detailed information about an Archive of Our Own (AO3) work."""
        try:
            if not ao3_url or not ao3_url.strip():
                raise ValidationError(message="Please provide a valid AO3 work URL")

            url_pattern = r"https?://archiveofourown\.org/works/\d+"
            if not re.search(url_pattern, ao3_url):
                raise ValidationError(
                    message="Please provide a valid AO3 work URL (e.g., https://archiveofourown.org/works/12345)"
                )

            if not self.ao3_login_successful:
                raise ExternalServiceError(
                    message="AO3 authentication failed. Please try again later."
                )

            logging.info(
                f"EXTERNAL AO3: User {interaction.user.id} requesting AO3 work info for URL: {ao3_url}"
            )

            await interaction.response.defer()

            try:
                self.ao3_session.refresh_auth_token()
            except Exception as e:
                logging.error(
                    f"EXTERNAL AO3 ERROR: Failed to refresh auth token for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="Failed to authenticate with AO3"
                ) from e

            try:
                ao3_id = AO3.utils.workid_from_url(ao3_url)
                work = AO3.Work(ao3_id)
                work.set_session(self.ao3_session)
            except AO3.utils.InvalidIdError:
                raise ValidationError(
                    message="Could not find that work on AO3. Please check the URL and try again."
                )
            except Exception as e:
                logging.error(
                    f"EXTERNAL AO3 ERROR: Failed to create work object for user {interaction.user.id}: {e}"
                )
                raise ExternalServiceError(
                    message="Failed to retrieve work information from AO3"
                ) from e

            try:
                embed = discord.Embed(
                    title=work.title or "Unknown Title",
                    description=(work.summary or "No summary available")[:4096],
                    color=discord.Color(0x3CD63D),
                    url=work.url,
                    timestamp=discord.utils.utcnow(),
                )

                try:
                    authors = []
                    for author in work.authors or []:
                        try:
                            author_match = re.search(
                                r"https?://archiveofourown\.org/users/(\w+)", author.url
                            )
                            if author_match:
                                author_name = author_match.group(1)
                                authors.append(f"[{author_name}]({author.url})")
                            else:
                                authors.append(str(author))
                        except (AttributeError, TypeError):
                            authors.append("Unknown Author")

                    author_text = "\n".join(authors) if authors else "Unknown Author"
                    embed.add_field(
                        name="Author(s)", value=author_text[:1024], inline=False
                    )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process authors for user {interaction.user.id}: {e}"
                    )
                    embed.add_field(
                        name="Author(s)", value="Unknown Author", inline=False
                    )

                try:
                    embed.add_field(
                        name="Rating", value=work.rating or "Not Rated", inline=True
                    )
                    embed.add_field(
                        name="Category",
                        value=", ".join(work.categories) if work.categories else "None",
                        inline=True,
                    )
                    embed.add_field(
                        name="Language",
                        value=work.language or "Unknown",
                        inline=True,
                    )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process basic info for user {interaction.user.id}: {e}"
                    )

                try:
                    if work.fandoms:
                        fandoms_text = "\n".join(work.fandoms)[:1024]
                        embed.add_field(
                            name="Fandoms", value=fandoms_text, inline=False
                        )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process fandoms for user {interaction.user.id}: {e}"
                    )

                try:
                    if work.relationships:
                        relationships_text = "\n".join(work.relationships)[:1024]
                        embed.add_field(
                            name="Relationships",
                            value=relationships_text,
                            inline=False,
                        )

                    if work.characters:
                        characters_text = "\n".join(work.characters)[:1024]
                        embed.add_field(
                            name="Characters", value=characters_text, inline=False
                        )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process relationships/characters for user {interaction.user.id}: {e}"
                    )

                try:
                    if work.warnings:
                        warnings_text = "\n".join(work.warnings)
                        embed.add_field(
                            name="Warnings", value=warnings_text[:1024], inline=False
                        )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process warnings for user {interaction.user.id}: {e}"
                    )

                try:
                    stats_text = []
                    if hasattr(work, "words") and work.words:
                        stats_text.append(f"**Words:** {int(work.words):,}")
                    if hasattr(work, "nchapters") and work.nchapters:
                        expected = (
                            work.expected_chapters if work.expected_chapters else "?"
                        )
                        stats_text.append(f"**Chapters:** {work.nchapters}/{expected}")
                    if hasattr(work, "comments") and work.comments is not None:
                        stats_text.append(f"**Comments:** {work.comments}")
                    if hasattr(work, "kudos") and work.kudos is not None:
                        stats_text.append(f"**Kudos:** {work.kudos}")
                    if hasattr(work, "bookmarks") and work.bookmarks is not None:
                        stats_text.append(f"**Bookmarks:** {work.bookmarks}")
                    if hasattr(work, "hits") and work.hits is not None:
                        stats_text.append(f"**Hits:** {work.hits}")

                    if stats_text:
                        embed.add_field(
                            name="Statistics",
                            value="\n".join(stats_text),
                            inline=False,
                        )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process statistics for user {interaction.user.id}: {e}"
                    )

                try:
                    date_text = []
                    if hasattr(work, "date_published") and work.date_published:
                        date_text.append(
                            f"**Published:** {work.date_published.strftime('%Y-%m-%d')}"
                        )
                    if hasattr(work, "date_updated") and work.date_updated:
                        date_text.append(
                            f"**Updated:** {work.date_updated.strftime('%Y-%m-%d')}"
                        )
                    if hasattr(work, "status") and work.status:
                        date_text.append(f"**Status:** {work.status}")

                    if date_text:
                        embed.add_field(
                            name="Publication Info",
                            value="\n".join(date_text),
                            inline=False,
                        )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process dates for user {interaction.user.id}: {e}"
                    )

                embed.set_footer(text="Data retrieved from Archive of Our Own")

                logging.info(
                    f"EXTERNAL AO3: Successfully retrieved work info for user {interaction.user.id}"
                )
                await interaction.followup.send(embed=embed)

            except AttributeError as e:
                logging.error(
                    f"EXTERNAL AO3 ERROR: Missing work attributes for user {interaction.user.id}: {e}"
                )
                raise ValidationError(
                    message="The work exists but some information is missing or inaccessible"
                ) from e

        except (ValidationError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(
                f"EXTERNAL AO3 ERROR: Unexpected error for user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(
                message=f"Unexpected error while retrieving work information: {e}"
            ) from e


async def setup(bot: commands.Bot) -> None:
    """Set up the ExternalServices cog."""
    await bot.add_cog(ExternalServices(bot))

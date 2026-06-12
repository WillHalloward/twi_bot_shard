"""External services cog for the Twi Bot Shard.

This module provides commands for interacting with external services like AO3.
"""

import asyncio
import datetime
import logging
import pickle
import re
from typing import Any

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

AO3_SESSION_MAX_AGE = datetime.timedelta(days=7)
AO3_PROBE_URL_TEMPLATE = "https://archiveofourown.org/users/{username}/readings"


class ExternalServices(BaseCog, name="ExternalServices"):  # type: ignore[call-arg]
    """Commands for interacting with external services."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.ao3_session: Any = None
        self.ao3_login_successful = False
        self.ao3_login_in_progress = False

    async def _initialize_ao3_session(self, max_retries: int = 3) -> None:
        """Initialize AO3 session with retry logic.

        Attempts to rehydrate a cached session from the database first; if no
        non-stale cached session exists or the cached session fails an auth
        probe, falls back to a fresh login (which runs in an executor and
        retries with exponential backoff up to max_retries times). Successful
        fresh logins are persisted to the cache.

        Args:
            max_retries: Maximum number of retry attempts for fresh login.
        """
        if self.ao3_login_in_progress:
            self.logger.warning(
                "AO3 login already in progress, skipping duplicate attempt"
            )
            return

        self.ao3_login_in_progress = True
        try:
            cached = await self._load_cached_session()
            if cached is not None:
                self.ao3_session = cached
                self.ao3_login_successful = True
                self.logger.info("ao3_session_restored_from_cache")
                return

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
                    await self._save_session(session)
                    return

                except Exception as e:
                    if attempt < max_retries:
                        # Transient AO3 flakiness — e.g. the login page comes
                        # back without an authenticity_token, which surfaces as
                        # a TypeError deep in the AO3 lib. The retry loop almost
                        # always recovers, so keep this at WARNING: it stays in
                        # the logs (as a Sentry breadcrumb) but does NOT raise a
                        # Sentry issue for a failure we self-heal from.
                        wait_time = 2**attempt
                        self.logger.warning(
                            f"AO3 login attempt {attempt}/{max_retries} failed "
                            f"({type(e).__name__}: {e}); retrying in {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        # All retries exhausted and no cached session was
                        # usable — AO3 features are now degraded, so this one is
                        # genuinely Sentry-worthy.
                        self.logger.error(
                            f"AO3 login failed after {max_retries} attempts: {e}",
                            exc_info=True,
                        )
                        self.ao3_login_successful = False
        finally:
            self.ao3_login_in_progress = False

    async def _load_cached_session(self) -> Any | None:
        """Try to restore a pickled AO3 session from the database.

        Returns the rehydrated session if a row exists, is within the
        staleness window, unpickles cleanly, and passes an auth probe.
        Returns None otherwise (callers should fall back to fresh login).
        """
        username = str(config.ao3_username)
        try:
            row = await self.bot.db.fetchrow(
                "SELECT session_data, saved_at FROM ao3_sessions WHERE username = $1",
                username,
            )
        except Exception as e:
            self.logger.warning("ao3_cached_session_db_read_failed", error=str(e))
            return None

        if row is None:
            return None

        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        age = now - row["saved_at"]
        if age > AO3_SESSION_MAX_AGE:
            self.logger.info(
                "ao3_cached_session_stale",
                age_days=age.days,
                max_age_days=AO3_SESSION_MAX_AGE.days,
            )
            return None

        try:
            session = pickle.loads(row["session_data"])
        except Exception as e:
            self.logger.warning("ao3_cached_session_unpickle_failed", error=str(e))
            return None

        if not await self._probe_session(session):
            self.logger.info("ao3_cached_session_probe_failed")
            return None

        try:
            await self.bot.db.execute(
                "UPDATE ao3_sessions SET last_validated_at = $1 WHERE username = $2",
                now,
                username,
            )
        except Exception as e:
            self.logger.warning(
                "ao3_cached_session_validated_update_failed", error=str(e)
            )

        return session

    async def _probe_session(self, session: Any) -> bool:
        """Verify a session is still authenticated by hitting a login-only page."""
        url = AO3_PROBE_URL_TEMPLATE.format(username=config.ao3_username)
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, session.session.get, url)
        except Exception as e:
            self.logger.warning("ao3_session_probe_request_failed", error=str(e))
            return False
        # Authed → 200 on the readings page. Unauthed sessions get redirected
        # to /users/login, which ends up as the final response URL.
        return resp.status_code == 200 and "/users/login" not in resp.url

    async def _save_session(self, session: Any) -> None:
        """Persist a freshly authenticated AO3 session to the database."""
        try:
            data = pickle.dumps(session)
        except Exception as e:
            self.logger.warning("ao3_session_pickle_failed", error=str(e))
            return

        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        try:
            await self.bot.db.execute(
                """
                INSERT INTO ao3_sessions (username, session_data, saved_at, last_validated_at)
                VALUES ($1, $2, $3, $3)
                ON CONFLICT (username) DO UPDATE
                    SET session_data = EXCLUDED.session_data,
                        saved_at = EXCLUDED.saved_at,
                        last_validated_at = EXCLUDED.last_validated_at
                """,
                str(config.ao3_username),
                data,
                now,
            )
        except Exception as e:
            self.logger.warning("ao3_session_db_save_failed", error=str(e))

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
                "Retrying AO3 login... this may take a moment (it retries with backoff).",
                ephemeral=True,
            )

            asyncio.create_task(self._initialize_ao3_session())

            await asyncio.sleep(2)

            if self.ao3_login_successful:
                await interaction.edit_original_response(
                    content="AO3 login successful!"
                )
            elif self.ao3_login_in_progress:
                # Defensive: flag is set True by the background init task,
                # which mypy cannot see across the create_task boundary.
                await interaction.edit_original_response(  # type: ignore[unreachable]
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

    def _fetch_work_data(self, ao3_url: str) -> dict[str, Any]:
        """Fetch an AO3 work and materialize its fields into plain values.

        BLOCKING: this performs synchronous network I/O via the AO3 library —
        the token refresh, the work fetch, *and* the attribute reads (AO3's
        work attributes are lazy and can issue requests on first access). It
        must therefore always run in a worker thread (``asyncio.to_thread``),
        never directly on the event loop.

        Args:
            ao3_url: A validated AO3 work URL.

        Returns:
            A dict of plain (non-lazy) values describing the work.

        Raises:
            ValidationError: If the URL does not resolve to an AO3 work.
            ExternalServiceError: If authentication or the fetch fails.
        """
        try:
            self.ao3_session.refresh_auth_token()
        except Exception as e:
            logging.error(f"EXTERNAL AO3 ERROR: Failed to refresh auth token: {e}")
            raise ExternalServiceError(message="Failed to authenticate with AO3") from e

        try:
            ao3_id = AO3.utils.workid_from_url(ao3_url)
            work = AO3.Work(ao3_id)
            work.set_session(self.ao3_session)
        except AO3.utils.InvalidIdError:
            raise ValidationError(
                message="Could not find that work on AO3. Please check the URL and try again."
            ) from None
        except Exception as e:
            logging.error(f"EXTERNAL AO3 ERROR: Failed to create work object: {e}")
            raise ExternalServiceError(
                message="Failed to retrieve work information from AO3"
            ) from e

        # Eagerly materialize every attribute we need while still on the
        # worker thread, so the async side only ever touches plain values.
        def grab(name: str) -> Any:
            try:
                return getattr(work, name, None)
            except Exception as e:
                logging.warning(
                    f"EXTERNAL AO3 WARNING: Failed to read work.{name}: {e}"
                )
                return None

        data: dict[str, Any] = {
            name: grab(name)
            for name in (
                "title",
                "summary",
                "url",
                "rating",
                "categories",
                "language",
                "fandoms",
                "relationships",
                "characters",
                "warnings",
                "words",
                "nchapters",
                "expected_chapters",
                "comments",
                "kudos",
                "bookmarks",
                "hits",
                "date_published",
                "date_updated",
                "status",
            )
        }

        authors: list[dict[str, str | None]] = []
        for author in grab("authors") or []:
            try:
                authors.append(
                    {"url": getattr(author, "url", None), "text": str(author)}
                )
            except Exception:
                authors.append({"url": None, "text": "Unknown Author"})
        data["authors"] = authors

        return data

    @app_commands.command(name="ao3", description="Posts information about a ao3 work")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
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

            # All blocking AO3 network I/O (auth refresh, work fetch, lazy
            # attribute reads) happens inside this single worker-thread call;
            # only plain values come back to the event loop.
            work_data = await asyncio.to_thread(self._fetch_work_data, ao3_url)

            try:
                embed = discord.Embed(
                    title=work_data["title"] or "Unknown Title",
                    description=(work_data["summary"] or "No summary available")[:4096],
                    color=discord.Color(0x3CD63D),
                    url=work_data["url"],
                    timestamp=discord.utils.utcnow(),
                )

                try:
                    authors = []
                    for author in work_data["authors"]:
                        try:
                            author_match = re.search(
                                r"https?://archiveofourown\.org/users/(\w+)",
                                author["url"] or "",
                            )
                            if author_match:
                                author_name = author_match.group(1)
                                authors.append(f"[{author_name}]({author['url']})")
                            else:
                                authors.append(author["text"])
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
                        name="Rating",
                        value=work_data["rating"] or "Not Rated",
                        inline=True,
                    )
                    embed.add_field(
                        name="Category",
                        value=", ".join(work_data["categories"])
                        if work_data["categories"]
                        else "None",
                        inline=True,
                    )
                    embed.add_field(
                        name="Language",
                        value=work_data["language"] or "Unknown",
                        inline=True,
                    )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process basic info for user {interaction.user.id}: {e}"
                    )

                try:
                    if work_data["fandoms"]:
                        fandoms_text = "\n".join(work_data["fandoms"])[:1024]
                        embed.add_field(
                            name="Fandoms", value=fandoms_text, inline=False
                        )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process fandoms for user {interaction.user.id}: {e}"
                    )

                try:
                    if work_data["relationships"]:
                        relationships_text = "\n".join(work_data["relationships"])[
                            :1024
                        ]
                        embed.add_field(
                            name="Relationships",
                            value=relationships_text,
                            inline=False,
                        )

                    if work_data["characters"]:
                        characters_text = "\n".join(work_data["characters"])[:1024]
                        embed.add_field(
                            name="Characters", value=characters_text, inline=False
                        )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process relationships/characters for user {interaction.user.id}: {e}"
                    )

                try:
                    if work_data["warnings"]:
                        warnings_text = "\n".join(work_data["warnings"])
                        embed.add_field(
                            name="Warnings", value=warnings_text[:1024], inline=False
                        )
                except Exception as e:
                    logging.warning(
                        f"EXTERNAL AO3 WARNING: Failed to process warnings for user {interaction.user.id}: {e}"
                    )

                try:
                    stats_text = []
                    if work_data["words"]:
                        stats_text.append(f"**Words:** {int(work_data['words']):,}")
                    if work_data["nchapters"]:
                        expected = work_data["expected_chapters"] or "?"
                        stats_text.append(
                            f"**Chapters:** {work_data['nchapters']}/{expected}"
                        )
                    if work_data["comments"] is not None:
                        stats_text.append(f"**Comments:** {work_data['comments']}")
                    if work_data["kudos"] is not None:
                        stats_text.append(f"**Kudos:** {work_data['kudos']}")
                    if work_data["bookmarks"] is not None:
                        stats_text.append(f"**Bookmarks:** {work_data['bookmarks']}")
                    if work_data["hits"] is not None:
                        stats_text.append(f"**Hits:** {work_data['hits']}")

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
                    if work_data["date_published"]:
                        date_text.append(
                            f"**Published:** {work_data['date_published'].strftime('%Y-%m-%d')}"
                        )
                    if work_data["date_updated"]:
                        date_text.append(
                            f"**Updated:** {work_data['date_updated'].strftime('%Y-%m-%d')}"
                        )
                    if work_data["status"]:
                        date_text.append(f"**Status:** {work_data['status']}")

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

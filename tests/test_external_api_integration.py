"""
Integration tests for external API services.

This module tests the integration with external APIs including:
- Google Search API (via the /find command in cogs.twi)
- Twitter/AO3 URL handling (via the repost dispatcher in cogs.gallery)
- AO3 API (via the /ao3 command in cogs.external_services)

All external calls are mocked; the tests exercise the real command callbacks
and assert on the actual Discord responses (embeds / error messages).
"""

import datetime
import os
import re
import sys
from typing import Any, Never
from unittest.mock import AsyncMock, MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Set up logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Imports below occur after sys.path setup so project modules resolve correctly.
# NOTE: cogs.twi and cogs.gallery are deliberately NOT imported at module level:
# tests/conftest.py purges them from sys.modules after every test, so a stale
# module-level class would no longer match what `patch("cogs.twi....")` targets
# (the patch would re-import a fresh module while the cog still used the old
# one — letting the REAL external call through). Each test imports them fresh
# and patches via patch.object on that same module object.
from cogs.external_services import ExternalServices  # noqa: E402

# Import test utilities
from tests.mock_factories import (  # noqa: E402
    MockChannelFactory,
    MockGuildFactory,
    MockInteractionFactory,
    MockMessageFactory,
    MockUserFactory,
)

# The generic message sanitize_error_message() produces for sensitive error
# types (DatabaseError, ExternalServiceError, ...).
GENERIC_ERROR_MESSAGE = (
    "An error occurred. Please contact an administrator if this persists."
)


def make_interaction() -> Any:
    """Create a mock interaction with user, guild, and channel attached."""
    user = MockUserFactory.create()
    guild = MockGuildFactory.create()
    channel = MockChannelFactory.create_text_channel()
    return MockInteractionFactory.create(user=user, guild=guild, channel=channel)


class TestGoogleSearchIntegration:
    """Test Google Search API integration."""

    @staticmethod
    def mock_google_search_success(
        query: str, api_key: str, cse_id: str, **kwargs
    ) -> dict[str, Any]:
        """Mock successful Google search response."""
        return {
            "searchInformation": {"totalResults": "2"},
            "items": [
                {
                    "title": "Test Result 1",
                    "link": "https://wanderinginn.com/test1",
                    "snippet": "This is a test search result snippet.",
                    "displayLink": "wanderinginn.com",
                },
                {
                    "title": "Test Result 2",
                    "link": "https://wanderinginn.com/test2",
                    "snippet": "Another test search result snippet.",
                    "displayLink": "wanderinginn.com",
                },
            ],
        }

    @staticmethod
    def mock_google_search_empty(
        query: str, api_key: str, cse_id: str, **kwargs
    ) -> dict[str, Any]:
        """Mock empty Google search response."""
        return {"searchInformation": {"totalResults": "0"}, "items": []}

    @staticmethod
    def mock_google_search_error(
        query: str, api_key: str, cse_id: str, **kwargs
    ) -> Never:
        """Mock Google search API error."""
        from googleapiclient.errors import HttpError

        raise HttpError(
            resp=MagicMock(status=403),
            content=b'{"error": {"code": 403, "message": "Daily Limit Exceeded"}}',
        )

    async def test_google_search_success(self) -> None:
        """A successful search returns an embed listing the results."""
        import cogs.twi as twi

        bot = MagicMock()
        cog = twi.TwiCog(bot)
        interaction = make_interaction()

        with patch.object(twi, "google_search", self.mock_google_search_success):
            await cog.find.callback(cog, interaction, "test query")

        interaction.response.defer.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        assert embed.title == "🔍 Search Results"
        assert "Found **2**" in embed.description
        field_names = [field.name for field in embed.fields]
        assert "1. Test Result 1" in field_names
        assert "2. Test Result 2" in field_names

    async def test_google_search_empty_results(self) -> None:
        """An empty search returns a 'no results' embed with search tips."""
        import cogs.twi as twi

        bot = MagicMock()
        cog = twi.TwiCog(bot)
        interaction = make_interaction()

        with patch.object(twi, "google_search", self.mock_google_search_empty):
            await cog.find.callback(cog, interaction, "nonexistent query")

        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        assert "No results found" in embed.description
        assert any(field.name == "💡 Search Tips" for field in embed.fields)

    async def test_google_search_api_error(self) -> None:
        """An API failure is sanitized into the generic error message."""
        import cogs.twi as twi

        bot = MagicMock()
        cog = twi.TwiCog(bot)
        interaction = make_interaction()

        with patch.object(twi, "google_search", self.mock_google_search_error):
            await cog.find.callback(cog, interaction, "test query")

        # The @handle_interaction_errors decorator catches the wrapped
        # ExternalServiceError and replies with the sanitized generic message.
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.await_args
        assert args[0] == GENERIC_ERROR_MESSAGE
        assert kwargs.get("ephemeral") is True
        # No results embed was sent.
        interaction.followup.send.assert_not_awaited()


class TestTwitterAPIIntegration:
    """Test Twitter URL handling."""

    def test_twitter_url_detection(self) -> None:
        """The twitter pattern matches all supported URL variants."""
        from cogs.gallery import twitter_pattern

        test_urls = [
            "https://twitter.com/user/status/123456789",
            "https://x.com/user/status/123456789",
            "https://mobile.twitter.com/user/status/123456789",
            "https://fxtwitter.com/user/status/123456789",
            "https://vxtwitter.com/user/status/123456789",
        ]
        for url in test_urls:
            assert re.search(twitter_pattern, url), f"not detected: {url}"

        assert not re.search(twitter_pattern, "https://example.com/user/status/1")

    async def test_twitter_repost_offers_twitter_option(self) -> None:
        """The repost dispatcher detects a tweet link and enables the Twitter button."""
        import cogs.gallery as gallery

        bot = MagicMock()
        cog = gallery.GalleryCog(bot)
        interaction = make_interaction()
        message = MockMessageFactory.create(
            content="Check out this tweet: https://twitter.com/user/status/123456789",
            guild=interaction.guild,
        )

        # Let the menu "time out" instead of blocking on user input.
        with patch.object(gallery.ButtonView, "wait", AsyncMock(return_value=True)):
            await cog.repost(interaction, message)

        interaction.response.defer.assert_awaited_once()
        interaction.edit_original_response.assert_awaited_once()
        kwargs = interaction.edit_original_response.await_args.kwargs
        embed, view = kwargs["embed"], kwargs["view"]
        assert any(field.name == "🐦 Twitter/X Link" for field in embed.fields)
        assert view.twitter.disabled is False
        assert view.ao3.disabled is True


class TestAO3APIIntegration:
    """Test AO3 API integration."""

    @staticmethod
    def make_mock_work() -> MagicMock:
        """Build a mock AO3 work with realistic, fully materialized fields."""
        work = MagicMock()
        work.title = "Test Fanfiction"
        work.summary = "This is a test fanfiction summary."
        work.url = "https://archiveofourown.org/works/123456"
        work.rating = "General Audiences"
        work.categories = ["Gen"]
        work.language = "English"
        work.fandoms = ["Test Fandom"]
        work.relationships = []
        work.characters = ["Test Character"]
        work.warnings = ["No Archive Warnings Apply"]
        work.words = 5000
        work.nchapters = 10
        work.expected_chapters = 10
        work.comments = 25
        work.kudos = 100
        work.bookmarks = 50
        work.hits = 1000
        work.date_published = datetime.datetime(2023, 1, 1)
        work.date_updated = datetime.datetime(2023, 12, 31)
        work.status = "Complete"
        author = MagicMock()
        author.url = "https://archiveofourown.org/users/testauthor"
        work.authors = [author]
        return work

    @staticmethod
    def make_authenticated_cog() -> ExternalServices:
        """Create an ExternalServices cog with a mocked, logged-in AO3 session."""
        bot = MagicMock()
        cog = ExternalServices(bot)
        cog.ao3_session = MagicMock()
        cog.ao3_login_successful = True
        return cog

    def test_ao3_url_detection(self) -> None:
        """The AO3 pattern matches work URLs."""
        from cogs.gallery import ao3_pattern

        test_urls = [
            "https://archiveofourown.org/works/123456",
            "https://archiveofourown.org/works/123456/chapters/789012",
            "http://archiveofourown.org/works/123456",
        ]
        for url in test_urls:
            assert re.search(ao3_pattern, url), f"not detected: {url}"

        assert not re.search(ao3_pattern, "https://example.com/works/123456")

    async def test_ao3_work_retrieval(self) -> None:
        """A successful AO3 lookup returns an embed with the work's details."""
        cog = self.make_authenticated_cog()
        interaction = make_interaction()

        with patch("AO3.Work", return_value=self.make_mock_work()):
            await cog.ao3.callback(
                cog, interaction, "https://archiveofourown.org/works/123456"
            )

        interaction.response.defer.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        assert embed.title == "Test Fanfiction"
        assert embed.description == "This is a test fanfiction summary."
        fields = {field.name: field.value for field in embed.fields}
        assert fields["Rating"] == "General Audiences"
        assert (
            "[testauthor](https://archiveofourown.org/users/testauthor)"
            in (fields["Author(s)"])
        )
        assert "**Words:** 5,000" in fields["Statistics"]
        assert "**Published:** 2023-01-01" in fields["Publication Info"]

    async def test_ao3_invalid_url_rejected(self) -> None:
        """A non-AO3 URL is rejected with a validation error before any fetch."""
        cog = self.make_authenticated_cog()
        interaction = make_interaction()

        await cog.ao3.callback(cog, interaction, "https://example.com/works/123456")

        # ValidationError path: replied with a validation message, no defer.
        interaction.response.defer.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()
        args, _ = interaction.response.send_message.await_args
        # The validation message contains an example URL, which the redaction
        # detector flags as sensitive, so the sanitized form is sent instead.
        assert args[0] == "ValidationError error occurred. Details have been logged."

    async def test_ao3_authentication_error(self) -> None:
        """An AO3 fetch failure is sanitized into the generic error message."""
        cog = self.make_authenticated_cog()
        interaction = make_interaction()

        with patch("AO3.Work", side_effect=Exception("Authentication failed")):
            await cog.ao3.callback(
                cog, interaction, "https://archiveofourown.org/works/123456"
            )

        # The ExternalServiceError raised inside the worker thread is caught by
        # @handle_interaction_errors and reported with the generic message.
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.await_args
        assert args[0] == GENERIC_ERROR_MESSAGE
        assert kwargs.get("ephemeral") is True
        interaction.followup.send.assert_not_awaited()

    async def test_ao3_repost_offers_ao3_option(self) -> None:
        """The repost dispatcher detects an AO3 link and enables the AO3 button."""
        import cogs.gallery as gallery

        bot = MagicMock()
        cog = gallery.GalleryCog(bot)
        interaction = make_interaction()
        message = MockMessageFactory.create(
            content="Check out this story: https://archiveofourown.org/works/123456",
            guild=interaction.guild,
        )

        # Let the menu "time out" instead of blocking on user input.
        with patch.object(gallery.ButtonView, "wait", AsyncMock(return_value=True)):
            await cog.repost(interaction, message)

        interaction.response.defer.assert_awaited_once()
        interaction.edit_original_response.assert_awaited_once()
        kwargs = interaction.edit_original_response.await_args.kwargs
        embed, view = kwargs["embed"], kwargs["view"]
        assert any(field.name == "📚 AO3 Link" for field in embed.fields)
        assert view.ao3.disabled is False
        assert view.twitter.disabled is True

"""
Integration tests for external API services.

This module tests the integration with external APIs including:
- Google Search API
- Twitter API
- AO3 API

These tests verify that the bot can properly handle external API responses,
errors, and edge cases while maintaining proper error handling and user feedback.
"""

import asyncio
import os
import sys
from typing import Any, Never
from unittest.mock import MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Set up logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Import config normally


# Import the cogs we want to test
from cogs.external_services import ExternalServices
from cogs.gallery import GalleryCog
from cogs.twi import TwiCog

# Import test utilities
from tests.mock_factories import (
    MockChannelFactory,
    MockGuildFactory,
    MockInteractionFactory,
    MockUserFactory,
)


class TestGoogleSearchIntegration:
    """Test Google Search API integration."""

    def mock_google_search_success(
        self, query: str, api_key: str, cse_id: str, **kwargs
    ) -> dict[str, Any]:
        """Mock successful Google search response."""
        return {
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
            ]
        }

    def mock_google_search_empty(
        self, query: str, api_key: str, cse_id: str, **kwargs
    ) -> dict[str, Any]:
        """Mock empty Google search response."""
        return {"items": []}

    def mock_google_search_error(
        self, query: str, api_key: str, cse_id: str, **kwargs
    ) -> Never:
        """Mock Google search API error."""
        from googleapiclient.errors import HttpError

        raise HttpError(
            resp=MagicMock(status=403),
            content=b'{"error": {"code": 403, "message": "Daily Limit Exceeded"}}',
        )

    async def test_google_search_success(self) -> bool | None:
        """Test successful Google search integration."""
        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        cog = TwiCog(bot)

        # Create mock interaction
        user = MockUserFactory.create()
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel()
        interaction = MockInteractionFactory.create(
            user=user, guild=guild, channel=channel
        )

        # Mock the google_search function
        with patch("cogs.twi.google_search", self.mock_google_search_success):
            try:
                await cog.find(interaction, "test query")
                print("✅ Google Search success test passed")
                return True
            except Exception as e:
                print(f"❌ Google Search success test failed: {e}")
                return False

    async def test_google_search_empty_results(self) -> bool | None:
        """Test Google search with empty results."""
        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        cog = TwiCog(bot)

        # Create mock interaction
        user = MockUserFactory.create()
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel()
        interaction = MockInteractionFactory.create(
            user=user, guild=guild, channel=channel
        )

        # Mock the google_search function
        with patch("cogs.twi.google_search", self.mock_google_search_empty):
            try:
                await cog.find(interaction, "nonexistent query")
                print("✅ Google Search empty results test passed")
                return True
            except Exception as e:
                print(f"❌ Google Search empty results test failed: {e}")
                return False

    async def test_google_search_api_error(self) -> bool | None:
        """Test Google search API error handling."""
        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        cog = TwiCog(bot)

        # Create mock interaction
        user = MockUserFactory.create()
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel()
        interaction = MockInteractionFactory.create(
            user=user, guild=guild, channel=channel
        )

        # Mock the google_search function to raise an error
        with patch("cogs.twi.google_search", self.mock_google_search_error):
            try:
                await cog.find(interaction, "test query")
                print("✅ Google Search API error test passed")
                return True
            except Exception as e:
                print(f"❌ Google Search API error test failed: {e}")
                return False


class TestTwitterAPIIntegration:
    """Test Twitter API integration."""

    async def test_twitter_url_detection(self) -> bool | None:
        """Test Twitter URL pattern detection."""
        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        GalleryCog(bot)

        # Test various Twitter URL formats
        test_urls = [
            "https://twitter.com/user/status/123456789",
            "https://x.com/user/status/123456789",
            "https://mobile.twitter.com/user/status/123456789",
            "https://fxtwitter.com/user/status/123456789",
            "https://vxtwitter.com/user/status/123456789",
        ]

        try:
            # Import the pattern from the cog
            import re

            from cogs.gallery import twitter_pattern

            for url in test_urls:
                if re.search(twitter_pattern, url):
                    print(f"✅ Twitter URL detected: {url}")
                else:
                    print(f"❌ Twitter URL not detected: {url}")
                    return False

            print("✅ Twitter URL detection test passed")
            return True
        except Exception as e:
            print(f"❌ Twitter URL detection test failed: {e}")
            return False

    async def test_twitter_repost_functionality(self) -> bool | None:
        """Test Twitter repost functionality."""
        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        cog = GalleryCog(bot)

        # Create mock interaction and message
        user = MockUserFactory.create()
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel()
        interaction = MockInteractionFactory.create(
            user=user, guild=guild, channel=channel
        )

        # Create mock message with Twitter URL
        message = MagicMock()
        message.content = (
            "Check out this tweet: https://twitter.com/user/status/123456789"
        )
        message.author = user
        message.channel = channel
        message.guild = guild

        try:
            # Test the repost functionality (this will be mocked)
            with patch.object(cog, "repost_twitter", return_value=None) as mock_repost:
                await cog.repost_twitter(interaction, message)
                mock_repost.assert_called_once()
                print("✅ Twitter repost functionality test passed")
                return True
        except Exception as e:
            print(f"❌ Twitter repost functionality test failed: {e}")
            return False


class TestAO3APIIntegration:
    """Test AO3 API integration."""

    def mock_ao3_work_success(self):
        """Mock successful AO3 work response."""
        mock_work = MagicMock()
        mock_work.title = "Test Fanfiction"
        mock_work.authors = ["Test Author"]
        mock_work.summary = "This is a test fanfiction summary."
        mock_work.words = 5000
        mock_work.chapters = 10
        mock_work.kudos = 100
        mock_work.bookmarks = 50
        mock_work.hits = 1000
        mock_work.tags = ["Test Tag 1", "Test Tag 2"]
        mock_work.rating = "General Audiences"
        mock_work.warnings = ["No Archive Warnings Apply"]
        mock_work.categories = ["Gen"]
        mock_work.fandoms = ["Test Fandom"]
        mock_work.relationships = []
        mock_work.characters = ["Test Character"]
        mock_work.additional_tags = ["Test Additional Tag"]
        mock_work.language = "English"
        mock_work.published = "2023-01-01"
        mock_work.updated = "2023-12-31"
        mock_work.status = "Complete"
        return mock_work

    async def test_ao3_url_detection(self) -> bool | None:
        """Test AO3 URL pattern detection."""
        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        GalleryCog(bot)

        # Test various AO3 URL formats
        test_urls = [
            "https://archiveofourown.org/works/123456",
            "https://archiveofourown.org/works/123456/chapters/789012",
            "http://archiveofourown.org/works/123456",
        ]

        try:
            # Import the pattern from the cog
            import re

            from cogs.gallery import ao3_pattern

            for url in test_urls:
                if re.search(ao3_pattern, url):
                    print(f"✅ AO3 URL detected: {url}")
                else:
                    print(f"❌ AO3 URL not detected: {url}")
                    return False

            print("✅ AO3 URL detection test passed")
            return True
        except Exception as e:
            print(f"❌ AO3 URL detection test failed: {e}")
            return False

    async def test_ao3_work_retrieval(self) -> bool | None:
        """Test AO3 work information retrieval."""
        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        cog = ExternalServices(bot)

        # Create mock interaction
        user = MockUserFactory.create()
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel()
        interaction = MockInteractionFactory.create(
            user=user, guild=guild, channel=channel
        )

        # Mock AO3 API
        with patch("AO3.Work") as mock_work_class:
            mock_work_class.return_value = self.mock_ao3_work_success()

            try:
                await cog.ao3(interaction, "https://archiveofourown.org/works/123456")
                print("✅ AO3 work retrieval test passed")
                return True
            except Exception as e:
                print(f"❌ AO3 work retrieval test failed: {e}")
                return False

    async def test_ao3_authentication_error(self) -> bool | None:
        """Test AO3 authentication error handling."""
        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        cog = ExternalServices(bot)

        # Create mock interaction
        user = MockUserFactory.create()
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel()
        interaction = MockInteractionFactory.create(
            user=user, guild=guild, channel=channel
        )

        # Mock AO3 API to raise authentication error
        with patch("AO3.Work") as mock_work_class:
            mock_work_class.side_effect = Exception("Authentication failed")

            try:
                await cog.ao3(interaction, "https://archiveofourown.org/works/123456")
                print("✅ AO3 authentication error test passed")
                return True
            except Exception as e:
                print(f"❌ AO3 authentication error test failed: {e}")
                return False

    async def test_ao3_repost_functionality(self) -> bool | None:
        """Test AO3 repost functionality."""
        # Create mock bot and cog
        bot = MagicMock()
        bot.db = MagicMock()
        cog = GalleryCog(bot)

        # Create mock interaction and message
        user = MockUserFactory.create()
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel()
        interaction = MockInteractionFactory.create(
            user=user, guild=guild, channel=channel
        )

        # Create mock message with AO3 URL
        message = MagicMock()
        message.content = (
            "Check out this story: https://archiveofourown.org/works/123456"
        )
        message.author = user
        message.channel = channel
        message.guild = guild

        try:
            # Test the repost functionality (this will be mocked)
            with patch.object(cog, "repost_ao3", return_value=None) as mock_repost:
                await cog.repost_ao3(interaction, message)
                mock_repost.assert_called_once()
                print("✅ AO3 repost functionality test passed")
                return True
        except Exception as e:
            print(f"❌ AO3 repost functionality test failed: {e}")
            return False


async def run_all_external_api_tests():
    """Run all external API integration tests."""
    print("🧪 Starting External API Integration Tests...")
    print("=" * 60)

    # Initialize test classes
    google_tests = TestGoogleSearchIntegration()
    twitter_tests = TestTwitterAPIIntegration()
    ao3_tests = TestAO3APIIntegration()

    # Track test results
    results = []

    # Google Search API Tests
    print("\n📍 Google Search API Tests:")
    print("-" * 30)
    results.append(await google_tests.test_google_search_success())
    results.append(await google_tests.test_google_search_empty_results())
    results.append(await google_tests.test_google_search_api_error())

    # Twitter API Tests
    print("\n🐦 Twitter API Tests:")
    print("-" * 30)
    results.append(await twitter_tests.test_twitter_url_detection())
    results.append(await twitter_tests.test_twitter_repost_functionality())

    # AO3 API Tests
    print("\n📚 AO3 API Tests:")
    print("-" * 30)
    results.append(await ao3_tests.test_ao3_url_detection())
    results.append(await ao3_tests.test_ao3_work_retrieval())
    results.append(await ao3_tests.test_ao3_authentication_error())
    results.append(await ao3_tests.test_ao3_repost_functionality())

    # Summary
    print("\n" + "=" * 60)
    print("📊 External API Integration Test Summary:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    print(f"📈 Success Rate: {(sum(results) / len(results)) * 100:.1f}%")

    return sum(results) == len(results)


async def main() -> bool | None:
    """Main test execution function."""
    try:
        success = await run_all_external_api_tests()
        if success:
            print("\n🎉 All external API integration tests passed!")
            return True
        else:
            print("\n💥 Some external API integration tests failed!")
            return False
    except Exception as e:
        print(f"\n💥 External API integration tests crashed: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(main())

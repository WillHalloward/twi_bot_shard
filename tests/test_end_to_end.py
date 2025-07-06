"""
Test script for end-to-end testing of critical bot commands.

This script tests the functionality of critical bot commands by simulating
Discord interactions and verifying the expected responses.
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import discord
from discord import app_commands
from discord.ext import commands

# Import the cogs we want to test
from cogs.twi import TwiCog

# Import test utilities
from tests.test_cogs import MockDatabase, MockAsyncSession, TestBot


# Mock classes for Discord objects
class MockUser:
    """Mock user class for testing."""

    def __init__(self, user_id=123456789, name="TestUser", discriminator="1234"):
        self.id = user_id
        self.name = name
        self.discriminator = discriminator
        self.display_name = name
        self.mention = f"<@{user_id}>"
        self.avatar = None
        self.bot = False


class MockGuild:
    """Mock guild class for testing."""

    def __init__(self, guild_id=987654321, name="TestGuild"):
        self.id = guild_id
        self.name = name
        self.roles = []
        self.members = []
        self.channels = []
        self.emojis = []


class MockChannel:
    """Mock channel class for testing."""

    def __init__(self, channel_id=111222333, name="test-channel"):
        self.id = channel_id
        self.name = name
        self.type = discord.ChannelType.text
        self.guild = None
        self.mention = f"<#{channel_id}>"
        self.send = AsyncMock()


class MockResponse:
    """Mock response class for testing."""

    def __init__(self):
        self.send_message = AsyncMock()
        self.defer = AsyncMock()
        self.edit_message = AsyncMock()

    def is_done(self):
        return False


class MockInteraction:
    """Mock interaction class for testing."""

    def __init__(self, user_id=123456789, guild_id=987654321, channel_id=111222333):
        self.user = MockUser(user_id)
        self.guild = MockGuild(guild_id)
        self.channel = MockChannel(channel_id)
        self.response = MockResponse()
        self.followup = MagicMock()
        self.followup.send = AsyncMock()
        self.client = MagicMock()
        self.command = MagicMock()
        self.command.name = "test_command"
        self.extras = {}
        self.command_failed = False


# Mock classes for external API responses
class MockClientSession:
    """Mock aiohttp.ClientSession for testing."""

    def __init__(self, responses=None):
        self.responses = responses or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, url, *args, **kwargs):
        if url in self.responses:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=self.responses[url])
            return mock_response
        else:
            mock_response = MagicMock()
            mock_response.status = 404
            mock_response.text = AsyncMock(return_value="Not found")
            return mock_response


# Mock function for Google search
def mock_google_search(query, api_key, cse_id, **kwargs):
    """Mock function for Google search."""
    if "test_query" in query:
        return {
            "searchInformation": {"totalResults": "1"},
            "items": [
                {
                    "title": "Test Result",
                    "snippet": "This is a test result snippet.",
                    "link": "https://wanderinginn.com/test-result",
                }
            ],
        }
    else:
        return {"searchInformation": {"totalResults": "0"}}


# Test functions
async def test_wiki_command():
    """Test the wiki command."""
    print("\nTesting wiki command...")

    # Create a test bot
    bot = TestBot()

    # Create the TwiCog
    cog = TwiCog(bot)

    # Create a mock interaction
    interaction = MockInteraction()

    # Mock responses for aiohttp.ClientSession
    wiki_search_response = json.dumps(
        {
            "query": {
                "pages": {
                    "1": {
                        "index": 1,
                        "title": "Test Article",
                        "fullurl": "https://thewanderinginn.fandom.com/wiki/Test_Article",
                        "images": [{"title": "Test_Image.jpg"}],
                    }
                }
            }
        }
    )

    wiki_image_response = json.dumps(
        {
            "query": {
                "pages": {
                    "1": {"imageinfo": [{"url": "https://example.com/test_image.jpg"}]}
                }
            }
        }
    )

    # Test with results
    async def mock_fetch_func(session, url):
        if "generator=search" in url:
            return wiki_search_response
        else:
            return wiki_image_response

    mock_fetch = AsyncMock(side_effect=mock_fetch_func)
    with patch("cogs.twi.fetch", mock_fetch):
        # Call the command's callback directly
        await cog.wiki.callback(cog, interaction, "test_query")

        # Verify the response - wiki command uses defer() then followup.send()
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()
        args, kwargs = interaction.followup.send.call_args
        assert kwargs.get("embed") is not None
        embed = kwargs.get("embed")
        assert "Wiki Search Results" in embed.title

        # Print the actual values for debugging
        print(f"Embed field value: {embed.fields[0].value}")
        print(f"Thumbnail URL: {embed.thumbnail.url}")

        # Check if the field contains the expected title and link
        assert "Test Article" in embed.fields[0].name
        assert (
            "https://thewanderinginn.fandom.com/wiki/Test_Article"
            in embed.fields[0].value
        )

        # Just check that a thumbnail URL exists, don't check the exact value
        assert embed.thumbnail.url is not None

    # Reset the mocks
    interaction.response.defer.reset_mock()
    interaction.followup.send.reset_mock()

    # Test with no results
    mock_fetch_no_results = AsyncMock()
    mock_fetch_no_results.return_value = json.dumps({"error": "no results"})
    with patch("cogs.twi.fetch", mock_fetch_no_results):

        # Reset the mocks before calling the command
        interaction.response.defer.reset_mock()
        interaction.followup.send.reset_mock()

        # Call the command's callback directly
        await cog.wiki.callback(cog, interaction, "nonexistent_query")

        # Verify the response
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()
        args, kwargs = interaction.followup.send.call_args

        # Check that the "not found" embed is sent
        assert kwargs.get("embed") is not None
        embed = kwargs.get("embed")
        assert "No articles found matching" in embed.description
        assert "nonexistent_query" in embed.description

    print("✅ wiki command test passed")
    return True


async def test_find_command():
    """Test the find command."""
    print("\nTesting find command...")

    # Create a test bot
    bot = TestBot()

    # Create the TwiCog
    cog = TwiCog(bot)

    # Create a mock interaction
    interaction = MockInteraction()

    # Test with results
    with (
        patch("cogs.twi.google_search", mock_google_search),
        patch("utils.permissions.is_bot_channel", return_value=True),
    ):
        # Call the command's callback directly
        await cog.find.callback(cog, interaction, "test_query")

        # Verify the response - find command uses defer() then followup.send()
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()
        args, kwargs = interaction.followup.send.call_args
        assert kwargs.get("embed") is not None
        embed = kwargs.get("embed")
        assert "Search Results" in embed.title
        assert "test_query" in embed.description
        assert "1. Test Result" in embed.fields[0].name
        assert "This is a test result snippet." in embed.fields[0].value

    # Reset the mocks
    interaction.response.defer.reset_mock()
    interaction.followup.send.reset_mock()

    # Test with no results
    with (
        patch("cogs.twi.google_search", mock_google_search),
        patch("utils.permissions.is_bot_channel", return_value=True),
    ):
        # Call the command's callback directly
        await cog.find.callback(cog, interaction, "nonexistent_query")

        # Verify the response
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()
        args, kwargs = interaction.followup.send.call_args
        assert kwargs.get("embed") is not None
        embed = kwargs.get("embed")
        assert "No results found on wanderinginn.com" in embed.description
        assert "nonexistent_query" in embed.description

    print("✅ find command test passed")
    return True


async def test_invis_text_command():
    """Test the invis_text command."""
    print("\nTesting invis_text command...")

    # Create a test bot
    bot = TestBot()

    # Mock the database fetch method
    bot.db.fetch = AsyncMock()

    # Create the TwiCog
    cog = TwiCog(bot)

    # Create a mock interaction
    interaction = MockInteraction()

    # Test with no chapter specified (list all chapters)
    bot.db.fetch.return_value = [
        {"title": "Chapter 1", "count": 2},
        {"title": "Chapter 2", "count": 1},
    ]

    # Call the command's callback directly
    await cog.invis_text.callback(cog, interaction)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("embed") is not None
    embed = kwargs.get("embed")
    assert "Chapters with Invisible Text" in embed.title
    assert "Chapter 1" in embed.fields[0].name
    assert "2" in embed.fields[0].value
    assert "Chapter 2" in embed.fields[1].name
    assert "1" in embed.fields[1].value

    # Reset the mocks
    interaction.response.send_message.reset_mock()
    bot.db.fetch.reset_mock()

    # Test with a specific chapter
    bot.db.fetch.return_value = [
        {"title": "Chapter 1", "content": "This is invisible text 1"},
        {"title": "Chapter 1", "content": "This is invisible text 2"},
    ]

    # Call the command's callback directly
    await cog.invis_text.callback(cog, interaction, "Chapter 1")

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("embed") is not None
    embed = kwargs.get("embed")
    assert "Invisible Text Found" in embed.title
    assert "This is invisible text 1" in embed.fields[0].value
    assert "This is invisible text 2" in embed.fields[1].value

    # Reset the mocks
    interaction.response.send_message.reset_mock()
    bot.db.fetch.reset_mock()

    # Test with a chapter that has no invisible text
    bot.db.fetch.return_value = []

    # Call the command's callback directly
    await cog.invis_text.callback(cog, interaction, "Chapter 3")

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    # Check if it's in content or embed
    content = kwargs.get("content", "")
    embed = kwargs.get("embed")
    if embed:
        assert "No invisible text found" in embed.description
    else:
        assert "No invisible text found" in content

    print("✅ invis_text command test passed")
    return True


async def main():
    """Run all tests."""
    print("Testing critical bot commands...")

    try:
        # Run tests
        tests = [test_wiki_command(), test_find_command(), test_invis_text_command()]

        results = await asyncio.gather(*tests)

        if all(results):
            print("\nAll command tests passed!")
            return True
        else:
            print("\nSome command tests failed.")
            return False

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

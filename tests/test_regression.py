"""
Regression test suite for Twi Bot Shard.

This module contains regression tests for critical functionality to ensure
that it continues to work as expected after changes are made to the codebase.
"""

import asyncio
import importlib
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select

from cogs.gallery import GalleryCog

# Import project components
from cogs.twi import TwiCog

# Import test utilities
from tests.mock_factories import (
    MockChannelFactory,
    MockGuildFactory,
    MockInteractionFactory,
)
from tests.test_utils import TestSetup, TestTeardown


@pytest.fixture(autouse=True)
def reload_twi_module():
    """Reload cogs.twi module before each test to ensure clean state."""
    if "cogs.twi" in sys.modules:
        importlib.reload(sys.modules["cogs.twi"])
    yield
    # Clean up after test
    if "cogs.twi" in sys.modules:
        del sys.modules["cogs.twi"]


# Test TwiCog commands


async def test_wiki_command() -> bool:
    """Test the wiki command."""
    print("\nTesting wiki command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

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

        # Check that the embed contains fields
        assert len(embed.fields) > 0

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

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ wiki command test passed")
    return True


@pytest.mark.asyncio
async def test_find_command() -> bool:
    """Test the find command."""
    print("\nTesting find command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Mock the google_search function
    def mock_google_search(query, api_key, cse_id, **kwargs):
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

    # Test with results - patch google_search directly using patch.object
    import cogs.twi
    with (
        patch.object(cogs.twi, "google_search", mock_google_search),
        patch("utils.permissions.app_is_bot_channel", new=AsyncMock(return_value=True)),
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

    # Test with no results - google_search will return no results for nonexistent_query
    with (
        patch.object(cogs.twi, "google_search", mock_google_search),
        patch("utils.permissions.app_is_bot_channel", new=AsyncMock(return_value=True)),
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

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ find command test passed")
    return True


async def test_invis_text_command() -> bool:
    """Test the invis_text command."""
    print("\nTesting invis_text command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Mock the database fetch method
    bot.db.fetch = AsyncMock()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

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

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ invis_text command test passed")
    return True


async def test_password_command() -> bool:
    """Test the password command."""
    print("\nTesting password command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Mock the database fetchrow method
    bot.db.fetchrow = AsyncMock(
        return_value={
            "password": "test_password",
            "link": "https://example.com/chapter",
        }
    )

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Call the command's callback directly - it should always return some response
    await cog.password.callback(cog, interaction)

    # Verify that a response was sent
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args

    # Check that we got either content or an embed
    content = kwargs.get("content", "")
    embed = kwargs.get("embed")
    if args:
        content = args[0]

    # Build response text from all parts
    response_text = content
    if embed and hasattr(embed, "description") and embed.description:
        response_text += " " + embed.description
    if embed and hasattr(embed, "fields"):
        for field in embed.fields:
            if hasattr(field, "value"):
                response_text += " " + str(field.value)

    # Verify we got some response (either password or instructions)
    assert len(response_text) > 0, "Expected some response from password command"
    # The response should contain password-related content
    assert ("password" in response_text.lower() or "patreon" in response_text.lower()), \
        f"Expected password-related content in response. Got: {response_text[:200]}"

    # Reset the mock
    interaction.response.send_message.reset_mock()

    # Test again to ensure command can be called multiple times
    await cog.password.callback(cog, interaction)

    # Verify the response
    interaction.response.send_message.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ password command test passed")
    return True


async def test_colored_text_command() -> bool:
    """Test the colored_text command."""
    print("\nTesting colored_text command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Call the command's callback directly
    await cog.colored_text.callback(cog, interaction)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("embed") is not None
    embed = kwargs.get("embed")
    assert "Twi's different colored text" in embed.title
    assert len(embed.fields) > 0

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ colored_text command test passed")
    return True


# Test GalleryCog functionality


async def test_set_repost_command() -> bool:
    """Test the set_repost command."""
    print("\nTesting set_repost command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Set up database fixture
    db_fixture, test_data = await TestSetup.setup_database()

    # Create the GalleryCog
    cog = await TestSetup.setup_cog(bot, GalleryCog)

    # Create a mock guild and interaction
    mock_guild = MockGuildFactory.create()
    interaction = MockInteractionFactory.create(guild=mock_guild)

    # Create a mock channel
    channel = MockChannelFactory.create_text_channel(
        channel_id=111222333, name="test-channel", guild=mock_guild
    )

    # Mock the gallery repository
    cog.gallery_repo.get_by_field = AsyncMock(return_value=[])
    cog.gallery_repo.create = AsyncMock()
    cog.gallery_repo.get_all = AsyncMock(
        return_value=[
            MagicMock(
                channel_name="test-channel",
                channel_id=111222333,
                guild_id=interaction.guild.id,
            )
        ]
    )

    # Test adding a new channel
    await cog.set_repost.callback(cog, interaction, channel)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    # The command sends an embed, not a text message
    assert kwargs.get("embed") is not None
    embed = kwargs.get("embed")
    assert (
        f"Successfully added {channel.mention} to repost channels" in embed.description
    )
    assert kwargs.get("ephemeral") is True

    # Verify that the repository methods were called
    cog.gallery_repo.get_by_field.assert_called_once_with("channel_id", channel.id)
    cog.gallery_repo.create.assert_called_once_with(
        channel_name=channel.name, channel_id=channel.id, guild_id=channel.guild.id
    )
    cog.gallery_repo.get_all.assert_called_once()

    # Reset the mocks
    interaction.response.send_message.reset_mock()
    cog.gallery_repo.get_by_field.reset_mock()
    cog.gallery_repo.create.reset_mock()
    cog.gallery_repo.get_all.reset_mock()

    # Mock the gallery repository for removing a channel
    gallery_memento = MagicMock(channel_name="test-channel")
    cog.gallery_repo.get_by_field = AsyncMock(return_value=[gallery_memento])
    cog.gallery_repo.delete = AsyncMock()
    cog.gallery_repo.get_all = AsyncMock(return_value=[])

    # Test removing an existing channel
    await cog.set_repost.callback(cog, interaction, channel)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    # The command sends an embed, not a text message
    assert kwargs.get("embed") is not None
    embed = kwargs.get("embed")
    assert (
        f"Successfully removed {channel.mention} from repost channels"
        in embed.description
    )
    assert kwargs.get("ephemeral") is True

    # Verify that the repository methods were called
    cog.gallery_repo.get_by_field.assert_called_once_with("channel_id", channel.id)
    cog.gallery_repo.delete.assert_called_once_with(gallery_memento.channel_name)
    cog.gallery_repo.get_all.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "Gallery & Mementos")
    await TestTeardown.teardown_bot(bot)
    await TestTeardown.teardown_database(db_fixture)

    print("✅ set_repost command test passed")
    return True


# Test database operations


async def test_database_operations() -> bool:
    """Test database operations."""
    print("\nTesting database operations...")

    # Set up database fixture
    db_fixture, test_data = await TestSetup.setup_database()

    # Load test data
    gallery_mementos = await test_data.load_gallery_mementos()
    command_history = await test_data.load_command_history()
    creator_links = await test_data.load_creator_links()

    # Verify that the data was loaded
    print(f"Created {len(gallery_mementos)} gallery mementos")
    print(f"Created {len(command_history)} command history entries")
    print(f"Created {len(creator_links)} creator links")

    # Query the data
    session = await db_fixture.create_session()
    async with session:
        # Test gallery mementos
        from models.tables.gallery import GalleryMementos

        result = await session.execute(select(GalleryMementos))
        galleries = result.scalars().all()
        assert len(galleries) == len(gallery_mementos)

        # Test command history
        from models.tables.commands import CommandHistory

        result = await session.execute(select(CommandHistory))
        commands = result.scalars().all()
        assert len(commands) == len(command_history)

        # Test creator links
        from models.tables.creator_links import CreatorLink

        result = await session.execute(select(CreatorLink))
        links = result.scalars().all()
        assert len(links) == len(creator_links)

    # Clean up
    await TestTeardown.teardown_database(db_fixture)

    print("✅ database operations test passed")
    return True


# Test bot lifecycle


async def test_bot_lifecycle() -> bool:
    """Test bot lifecycle."""
    print("\nTesting bot lifecycle...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Verify that the bot was initialized correctly
    assert bot.db is not None
    assert bot.container is not None
    assert bot.repo_factory is not None

    # Test loading a cog
    await TestSetup.setup_cog(bot, TwiCog)
    assert bot.get_cog("The Wandering Inn") is not None

    # Test unloading a cog
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    assert bot.get_cog("The Wandering Inn") is None

    # Clean up
    await TestTeardown.teardown_bot(bot)

    print("✅ bot lifecycle test passed")
    return True


# Main function to run all tests
async def main() -> None:
    """Run all regression tests."""
    print("Running regression tests...")

    # Run TwiCog command tests
    await test_wiki_command()
    await test_find_command()
    await test_invis_text_command()
    await test_password_command()
    await test_colored_text_command()

    # Run GalleryCog functionality tests
    await test_set_repost_command()

    # Run database operations tests
    await test_database_operations()

    # Run bot lifecycle tests
    await test_bot_lifecycle()

    print("\nAll regression tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

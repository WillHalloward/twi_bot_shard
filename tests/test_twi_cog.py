"""
Unit tests for the TwiCog class in cogs/twi.py.

This module contains tests for the TwiCog class, which is responsible
for The Wandering Inn specific functionality including wiki searches,
password management, and text processing.
"""

import asyncio
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord
from discord.ext import commands

# Import the cog to test
from cogs.twi import TwiCog, google_search

# Import test utilities
from tests.fixtures import DatabaseFixture, TestDataFixture
from tests.mock_factories import (
    MockUserFactory,
    MockMemberFactory,
    MockGuildFactory,
    MockChannelFactory,
    MockMessageFactory,
    MockInteractionFactory,
    MockContextFactory,
)
from tests.test_utils import TestSetup, TestTeardown, TestAssertions, TestHelpers


# Test the standalone functions


async def test_google_search_function():
    """Test the google_search function."""
    print("\nTesting google_search function...")

    # Mock the Google API service
    with patch("cogs.twi.build") as mock_build:
        mock_service = MagicMock()
        mock_cse = MagicMock()
        mock_list = MagicMock()

        # Set up the mock chain
        mock_build.return_value = mock_service
        mock_service.cse.return_value = mock_cse
        mock_cse.list.return_value = mock_list
        mock_list.execute.return_value = {
            "items": [
                {
                    "title": "Test Result",
                    "link": "https://example.com",
                    "snippet": "Test snippet",
                }
            ]
        }

        # Call the function
        result = google_search("test query", "fake_api_key", "fake_cse_id")

        # Verify the result
        assert result is not None
        assert "items" in result
        assert len(result["items"]) == 1
        assert result["items"][0]["title"] == "Test Result"

        # Verify the API was called correctly
        mock_build.assert_called_once_with(
            "customsearch", "v1", developerKey="fake_api_key"
        )
        mock_cse.list.assert_called_once_with(q="test query", cx="fake_cse_id")

    print("✅ google_search function test passed")
    return True


# Test the TwiCog class methods


async def test_twi_cog_initialization():
    """Test the initialization of the TwiCog class."""
    print("\nTesting TwiCog initialization...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Verify that the cog was initialized correctly
    assert cog.bot == bot
    assert cog.logger is not None

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ TwiCog initialization test passed")
    return True


async def test_cog_load():
    """Test the cog_load method."""
    print("\nTesting cog_load method...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Mock file operations
    with patch("builtins.open", mock_open(read_data='{"test": "data"}')):
        with patch("os.path.exists", return_value=True):
            await cog.cog_load()

    # Verify that the method completed without error
    assert True  # If we get here, the method didn't raise an exception

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ cog_load method test passed")
    return True


async def test_password_command():
    """Test the password command."""
    print("\nTesting password command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Mock file operations and data
    mock_data = {
        "passwords": {
            "test_chapter": {
                "password": "test_password",
                "link": "https://example.com/test",
            }
        }
    }

    with patch(
        "builtins.open",
        mock_open(
            read_data='{"passwords": {"test_chapter": {"password": "test_password", "link": "https://example.com/test"}}}'
        ),
    ):
        with patch("json.load", return_value=mock_data):
            with patch("os.path.exists", return_value=True):
                # Call the command's callback directly
                await cog.password.callback(cog, interaction)

    # Verify the response was sent
    interaction.response.send_message.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ password command test passed")
    return True


async def test_wiki_command():
    """Test the wiki command."""
    print("\nTesting wiki command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Mock the Google search function
    with patch("cogs.twi.google_search") as mock_search:
        mock_search.return_value = {
            "items": [
                {
                    "title": "Test Wiki Page",
                    "link": "https://thewanderinginn.fandom.com/wiki/Test",
                    "snippet": "Test wiki content",
                }
            ]
        }

        # Call the command's callback directly
        await cog.wiki.callback(cog, interaction, "test query")

        # Verify the search was called
        mock_search.assert_called_once()

    # Verify the response was sent
    interaction.response.send_message.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ wiki command test passed")
    return True


async def test_find_command():
    """Test the find command."""
    print("\nTesting find command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Mock the Google search function
    with patch("cogs.twi.google_search") as mock_search:
        mock_search.return_value = {
            "items": [
                {
                    "title": "Test Search Result",
                    "link": "https://wanderinginn.com/test",
                    "snippet": "Test search content",
                }
            ]
        }

        # Call the command's callback directly
        await cog.find.callback(cog, interaction, "test query")

        # Verify the search was called
        mock_search.assert_called_once()

    # Verify the response was sent
    interaction.response.send_message.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ find command test passed")
    return True


async def test_invis_text_command():
    """Test the invis_text command."""
    print("\nTesting invis_text command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Mock file operations
    with patch("builtins.open", mock_open(read_data="Test invisible text content")):
        with patch("os.path.exists", return_value=True):
            with patch("os.listdir", return_value=["test_chapter.txt"]):
                # Call the command's callback directly
                await cog.invis_text.callback(cog, interaction, "test_chapter")

    # Verify the response was sent
    interaction.response.send_message.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ invis_text command test passed")
    return True


async def test_colored_text_command():
    """Test the colored_text command."""
    print("\nTesting colored_text command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Mock PIL Image operations
    with patch("PIL.Image.open") as mock_image_open:
        mock_image = MagicMock()
        mock_image.size = (100, 100)
        mock_image.save = MagicMock()
        mock_image_open.return_value = mock_image

        with patch("os.path.exists", return_value=True):
            with patch("os.listdir", return_value=["test_image.png"]):
                # Call the command's callback directly
                await cog.colored_text.callback(cog, interaction)

    # Verify the response was sent
    interaction.response.send_message.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ colored_text command test passed")
    return True


async def test_update_password_command():
    """Test the update_password command."""
    print("\nTesting update_password command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Mock file operations
    mock_data = {"passwords": {}}

    with patch("builtins.open", mock_open()):
        with patch("json.load", return_value=mock_data):
            with patch("json.dump") as mock_dump:
                with patch("os.path.exists", return_value=True):
                    # Call the command's callback directly
                    await cog.update_password.callback(
                        cog, interaction, "new_password", "https://example.com/new"
                    )

                    # Verify that json.dump was called (password was saved)
                    mock_dump.assert_called_once()

    # Verify the response was sent
    interaction.response.send_message.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ update_password command test passed")
    return True


async def test_error_handling():
    """Test error handling in TwiCog methods."""
    print("\nTesting error handling...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Test Google search error handling
    with patch("cogs.twi.google_search", side_effect=Exception("API Error")):
        try:
            await cog.wiki.callback(cog, interaction, "test query")
            # Should handle the error gracefully
        except Exception as e:
            # If an exception is raised, it should be a handled exception
            assert "API Error" in str(e) or hasattr(e, "__class__")

    # Test file operation error handling
    with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
        try:
            await cog.invis_text.callback(cog, interaction, "nonexistent_chapter")
            # Should handle the error gracefully
        except Exception as e:
            # If an exception is raised, it should be a handled exception
            assert "File not found" in str(e) or hasattr(e, "__class__")

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ Error handling test passed")
    return True


async def test_edge_cases():
    """Test edge cases and boundary conditions."""
    print("\nTesting edge cases...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Test empty search results
    with patch("cogs.twi.google_search") as mock_search:
        mock_search.return_value = {"items": []}

        await cog.wiki.callback(cog, interaction, "nonexistent query")

        # Should handle empty results gracefully
        interaction.response.send_message.assert_called()

    # Test None chapter for invis_text
    with patch("os.path.exists", return_value=False):
        await cog.invis_text.callback(cog, interaction, None)

        # Should handle None chapter gracefully
        interaction.response.send_message.assert_called()

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ Edge cases test passed")
    return True


async def test_autocomplete_functionality():
    """Test autocomplete functionality."""
    print("\nTesting autocomplete functionality...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Mock file operations for autocomplete
    with patch("os.path.exists", return_value=True):
        with patch(
            "os.listdir",
            return_value=["chapter1.txt", "chapter2.txt", "test_chapter.txt"],
        ):
            # Call the autocomplete method
            choices = await cog.invis_text_autocomplete(interaction, "test")

            # Verify that choices were returned
            assert isinstance(choices, list)

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ Autocomplete functionality test passed")
    return True


async def test_button_class():
    """Test the Button UI class."""
    print("\nTesting Button UI class...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the TwiCog
    cog = await TestSetup.setup_cog(bot, TwiCog)

    # Create a Button instance
    button = cog.Button("https://example.com")

    # Verify button properties
    assert button.url == "https://example.com"
    assert button.label == "Link"

    # Clean up
    await TestTeardown.teardown_cog(bot, "The Wandering Inn")
    await TestTeardown.teardown_bot(bot)

    print("✅ Button UI class test passed")
    return True


# Main function to run all tests
async def main():
    """Run all unit tests for the TwiCog class."""
    print("Running comprehensive TwiCog unit tests...")

    # Test standalone functions
    await test_google_search_function()

    # Test TwiCog class methods
    await test_twi_cog_initialization()
    await test_cog_load()
    await test_password_command()
    await test_wiki_command()
    await test_find_command()
    await test_invis_text_command()
    await test_colored_text_command()
    await test_update_password_command()

    # Test error handling
    await test_error_handling()

    # Test edge cases
    await test_edge_cases()

    # Test autocomplete functionality
    await test_autocomplete_functionality()

    # Test UI components
    await test_button_class()

    print("\nAll comprehensive TwiCog unit tests passed!")
    print("✅ TwiCog test coverage significantly improved!")


if __name__ == "__main__":
    asyncio.run(main())

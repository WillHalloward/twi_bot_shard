"""
Unit tests for the InteractiveHelp class in cogs/interactive_help.py.

This module contains tests for the InteractiveHelp class, which provides
an interactive help system for the bot's commands.
"""

import asyncio
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
from unittest.mock import AsyncMock, MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord
from discord.ext import commands

# Import the cog to test
from cogs.interactive_help import InteractiveHelp, HelpView

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


# Test the HelpView class and its components


async def test_help_view_initialization():
    """Test the initialization of the HelpView class."""
    print("\nTesting HelpView initialization...")

    # Create a mock InteractiveHelp cog
    cog = MagicMock(spec=InteractiveHelp)
    cog.command_categories = ["General", "Moderation", "Fun"]
    cog.category_descriptions = {
        "General": "General commands",
        "Moderation": "Moderation commands",
        "Fun": "Fun commands",
    }
    cog.commands_by_category = {
        "General": [
            {"name": "help", "description": "Shows this help message"},
            {"name": "ping", "description": "Checks the bot's latency"},
        ],
        "Moderation": [
            {"name": "kick", "description": "Kicks a member"},
            {"name": "ban", "description": "Bans a member"},
        ],
        "Fun": [
            {"name": "roll", "description": "Rolls a dice"},
            {"name": "8ball", "description": "Ask the magic 8ball"},
        ],
    }

    # Create the HelpView
    view = HelpView(cog)

    # Verify that the view was initialized correctly
    assert view.cog == cog
    assert len(view.children) == 1  # Should have the category select
    assert isinstance(view.children[0], discord.ui.Select)

    print("✅ HelpView initialization test passed")
    return True


async def test_category_select():
    """Test the CategorySelect component."""
    print("\nTesting CategorySelect component...")

    # Create a test bot and real InteractiveHelp cog
    bot = await TestSetup.create_test_bot()
    cog = await TestSetup.setup_cog(bot, InteractiveHelp)

    # Create the HelpView
    view = HelpView(cog)

    # Get the CategorySelect component
    category_select = view.children[0]

    # Verify that the select has the correct options (should match the actual categories)
    expected_categories = len(cog.command_categories)
    assert len(category_select.options) == expected_categories

    # Verify that the first few categories are present
    category_labels = [option.label for option in category_select.options]
    assert "Moderation" in category_labels
    assert "Utility" in category_labels

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Mock the response methods
    interaction.response.edit_message = AsyncMock()

    # Set the selected values
    category_select.values = ["General"]

    # Call the callback
    await category_select.callback(interaction)

    # Verify that the interaction response was edited
    interaction.response.edit_message.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "Help")
    await TestTeardown.teardown_bot(bot)

    print("✅ CategorySelect component test passed")
    return True


# Test the InteractiveHelp class methods


async def test_interactive_help_initialization():
    """Test the initialization of the InteractiveHelp class."""
    print("\nTesting InteractiveHelp initialization...")

    # Create a test bot with some commands
    bot = await TestSetup.create_test_bot()

    # Add some commands to the bot
    @bot.command(name="ping", help="Checks the bot's latency")
    async def ping(ctx):
        await ctx.send("Pong!")

    @bot.command(name="echo", help="Echoes your message", category="Utility")
    async def echo(ctx, *, message):
        await ctx.send(message)

    # Create the InteractiveHelp cog
    cog = await TestSetup.setup_cog(bot, InteractiveHelp)

    # Verify that the cog was initialized correctly
    assert cog.bot == bot
    assert len(cog.command_categories) > 0
    assert "Utility" in cog.command_categories
    assert "Utility" in cog.category_descriptions
    assert len(cog.commands_by_category["Utility"]) > 0

    # Clean up
    await TestTeardown.teardown_cog(bot, "Help")
    await TestTeardown.teardown_bot(bot)

    print("✅ InteractiveHelp initialization test passed")
    return True


async def test_get_commands_for_category():
    """Test the get_commands_for_category method."""
    print("\nTesting get_commands_for_category method...")

    # Create a test bot with some commands
    bot = await TestSetup.create_test_bot()

    # Create the InteractiveHelp cog
    cog = await TestSetup.setup_cog(bot, InteractiveHelp)

    # Call the method
    utility_commands = cog.get_commands_for_category("Utility")

    # Verify the result
    assert len(utility_commands) > 0
    assert any(cmd["name"] == "ping" for cmd in utility_commands)

    # Clean up
    await TestTeardown.teardown_cog(bot, "Help")
    await TestTeardown.teardown_bot(bot)

    print("✅ get_commands_for_category method test passed")
    return True


async def test_help_command():
    """Test the help_command method."""
    print("\nTesting help_command method...")

    # Create a test bot with some commands
    bot = await TestSetup.create_test_bot()

    # Add some commands to the bot
    @bot.command(name="ping", help="Checks the bot's latency")
    async def ping(ctx):
        await ctx.send("Pong!")

    @bot.command(name="echo", help="Echoes your message", category="Utility")
    async def echo(ctx, *, message):
        await ctx.send(message)

    # Create the InteractiveHelp cog
    cog = await TestSetup.setup_cog(bot, InteractiveHelp)

    # Create a mock context
    ctx = MockContextFactory.create()

    # Mock the send method
    ctx.send = AsyncMock()

    # Call the method without a command name (should show categories)
    await cog.help_command(ctx)

    # Verify the response
    ctx.send.assert_called_once()
    args, kwargs = ctx.send.call_args
    assert kwargs.get("embed") is not None
    assert kwargs.get("view") is not None

    # Reset the mock
    ctx.send.reset_mock()

    # Call the method with a command name
    await cog.help_command(ctx, command_name="ping")

    # Verify the response
    ctx.send.assert_called_once()
    args, kwargs = ctx.send.call_args
    assert kwargs.get("embed") is not None
    assert "ping" in kwargs.get("embed").title.lower()

    # Clean up
    await TestTeardown.teardown_cog(bot, "Help")
    await TestTeardown.teardown_bot(bot)

    print("✅ help_command method test passed")
    return True


async def test_help_slash():
    """Test the help_slash method."""
    print("\nTesting help_slash method...")

    # Create a test bot with some commands
    bot = await TestSetup.create_test_bot()

    # Add some commands to the bot
    @bot.command(name="ping", help="Checks the bot's latency")
    async def ping(ctx):
        await ctx.send("Pong!")

    @bot.command(name="echo", help="Echoes your message", category="Utility")
    async def echo(ctx, *, message):
        await ctx.send(message)

    # Create the InteractiveHelp cog
    cog = await TestSetup.setup_cog(bot, InteractiveHelp)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Call the method without a command name (should show categories)
    await cog.help_slash.callback(cog, interaction)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("embed") is not None
    assert kwargs.get("view") is not None

    # Reset the mock
    interaction.response.send_message.reset_mock()

    # Call the method with a command name
    await cog.help_slash.callback(cog, interaction, command="ping")

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("embed") is not None
    assert "ping" in kwargs.get("embed").title.lower()

    # Clean up
    await TestTeardown.teardown_cog(bot, "Help")
    await TestTeardown.teardown_bot(bot)

    print("✅ help_slash method test passed")
    return True


# Main function to run all tests
async def main():
    """Run all unit tests for the InteractiveHelp class."""
    print("Running InteractiveHelp unit tests...")

    # Test HelpView and its components
    await test_help_view_initialization()
    await test_category_select()

    # Test InteractiveHelp class methods
    await test_interactive_help_initialization()
    await test_get_commands_for_category()
    await test_help_command()
    await test_help_slash()

    print("\nAll InteractiveHelp unit tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

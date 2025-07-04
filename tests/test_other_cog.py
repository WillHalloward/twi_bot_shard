"""
Unit tests for the OtherCogs class in cogs/other.py.

This module contains tests for the OtherCogs class, which provides
various utility commands for server management and user interaction.
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
from cogs.other import OtherCogs, user_info_function

# Import test utilities
from tests.fixtures import DatabaseFixture, TestDataFixture
from tests.mock_factories import (
    MockUserFactory,
    MockMemberFactory,
    MockGuildFactory,
    MockChannelFactory,
    MockMessageFactory,
    MockRoleFactory,
    MockInteractionFactory,
    MockContextFactory,
)
from tests.test_utils import TestSetup, TestTeardown, TestAssertions, TestHelpers


# Test the standalone functions


async def test_user_info_function():
    """Test the user_info_function."""
    print("\nTesting user_info_function...")

    # Create mock objects
    interaction = MockInteractionFactory.create()
    member = MockMemberFactory.create()

    # Call the function
    await user_info_function(interaction, member)

    # Verify the result
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("embed") is not None
    embed = kwargs.get("embed")
    assert member.display_name in embed.title

    print("✅ user_info_function test passed")
    return True


# Test the OtherCogs class methods


async def test_other_cog_initialization():
    """Test the initialization of the OtherCogs class."""
    print("\nTesting OtherCogs initialization...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the OtherCogs
    cog = await TestSetup.setup_cog(bot, OtherCogs)

    # Verify that the cog was initialized correctly
    assert cog.bot == bot
    assert cog.logger is not None

    # Clean up
    await TestTeardown.teardown_cog(bot, "Other")
    await TestTeardown.teardown_bot(bot)

    print("✅ OtherCogs initialization test passed")
    return True


async def test_ping_command():
    """Test the ping command."""
    print("\nTesting ping command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the OtherCogs
    cog = await TestSetup.setup_cog(bot, OtherCogs)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Call the command's callback directly
    await cog.ping.callback(cog, interaction)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "ms" in args[0]

    # Clean up
    await TestTeardown.teardown_cog(bot, "Other")
    await TestTeardown.teardown_bot(bot)

    print("✅ ping command test passed")
    return True


async def test_av_command():
    """Test the av (avatar) command."""
    print("\nTesting av command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the OtherCogs
    cog = await TestSetup.setup_cog(bot, OtherCogs)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Create a mock member
    member = MockMemberFactory.create()

    # Set up the avatar URL
    member.display_avatar.url = "https://example.com/avatar.png"

    # Call the command's callback directly
    await cog.av.callback(cog, interaction, member)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("embed") is not None
    embed = kwargs.get("embed")
    assert "Avatar" in embed.title
    assert member.display_avatar.url in embed.image.url

    # Clean up
    await TestTeardown.teardown_cog(bot, "Other")
    await TestTeardown.teardown_bot(bot)

    print("✅ av command test passed")
    return True


async def test_info_user_command():
    """Test the info_user command."""
    print("\nTesting info_user command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the OtherCogs
    cog = await TestSetup.setup_cog(bot, OtherCogs)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Create a mock member
    member = MockMemberFactory.create()

    # Call the command's callback directly
    await cog.info_user.callback(cog, interaction, member)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("embed") is not None

    # Clean up
    await TestTeardown.teardown_cog(bot, "Other")
    await TestTeardown.teardown_bot(bot)

    print("✅ info_user command test passed")
    return True


async def test_info_server_command():
    """Test the info_server command."""
    print("\nTesting info_server command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the OtherCogs
    cog = await TestSetup.setup_cog(bot, OtherCogs)

    # Create a mock guild and interaction
    guild = MockGuildFactory.create()
    guild.member_count = 100
    guild.created_at = discord.utils.utcnow()
    guild.owner = MockMemberFactory.create()
    guild.channels = [MockChannelFactory.create_text_channel() for _ in range(5)]
    guild.roles = [MockRoleFactory.create() for _ in range(3)]

    interaction = MockInteractionFactory.create(guild=guild)

    # Call the command's callback directly
    await cog.info_server.callback(cog, interaction)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("embed") is not None
    embed = kwargs.get("embed")
    assert guild.name in embed.title

    # Clean up
    await TestTeardown.teardown_cog(bot, "Other")
    await TestTeardown.teardown_bot(bot)

    print("✅ info_server command test passed")
    return True


async def test_roll_command():
    """Test the roll command."""
    print("\nTesting roll command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the OtherCogs
    cog = await TestSetup.setup_cog(bot, OtherCogs)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Call the command's callback directly with default parameters
    await cog.roll.callback(cog, interaction)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "Rolled" in args[0]

    # Reset the mock
    interaction.response.send_message.reset_mock()

    # Call the command with custom parameters
    await cog.roll.callback(cog, interaction, dice=6, amount=3, modifier=2)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "Rolled" in args[0]
    assert "d6" in args[0]
    assert "3" in args[0]
    assert "+ 2" in args[0]

    # Clean up
    await TestTeardown.teardown_cog(bot, "Other")
    await TestTeardown.teardown_bot(bot)

    print("✅ roll command test passed")
    return True


async def test_say_command():
    """Test the say command."""
    print("\nTesting say command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the OtherCogs
    cog = await TestSetup.setup_cog(bot, OtherCogs)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Call the command's callback directly
    await cog.say.callback(cog, interaction, "Hello, world!")

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "Sent message" in args[0]

    # Clean up
    await TestTeardown.teardown_cog(bot, "Other")
    await TestTeardown.teardown_bot(bot)

    print("✅ say command test passed")
    return True


# Main function to run all tests
async def main():
    """Run all unit tests for the OtherCogs class."""
    print("Running OtherCogs unit tests...")

    # Test standalone functions
    await test_user_info_function()

    # Test OtherCogs class methods
    await test_other_cog_initialization()
    await test_ping_command()
    await test_av_command()
    await test_info_user_command()
    await test_info_server_command()
    await test_roll_command()
    await test_say_command()

    print("\nAll OtherCogs unit tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

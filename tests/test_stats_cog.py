"""
Unit tests for the StatsCogs class in cogs/stats.py.

This module contains tests for the StatsCogs class, which is responsible
for collecting and storing statistics about Discord servers, users, and events.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from unittest.mock import AsyncMock, MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord
from discord.ext import commands

# Import the cog to test
from cogs.stats import StatsCogs, save_message, save_reaction

# Import test utilities
from tests.fixtures import DatabaseFixture, TestDataFixture
from tests.mock_factories import (
    MockUserFactory,
    MockMemberFactory,
    MockGuildFactory,
    MockChannelFactory,
    MockMessageFactory,
    MockReactionFactory,
    MockInteractionFactory,
    MockContextFactory,
)
from tests.test_utils import TestSetup, TestTeardown, TestAssertions, TestHelpers


# Test the standalone functions


async def test_save_message():
    """Test the save_message method."""
    print("\nTesting save_message method...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the StatsCogs
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Create mock objects
    message = MockMessageFactory.create()

    # Mock the database methods
    bot.db.prepare_statement = AsyncMock()
    bot.db.transaction = AsyncMock()
    bot.db.execute_many = AsyncMock()

    # Mock the prepared statement
    mock_stmt = AsyncMock()
    mock_stmt.execute = AsyncMock()
    bot.db.prepare_statement.return_value = mock_stmt

    # Mock the transaction context manager
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()
    bot.db.transaction.return_value = mock_transaction

    # Call the function
    await save_message(cog, message)

    # Verify that prepare_statement was called
    assert bot.db.prepare_statement.call_count >= 1

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ save_message method test passed")
    return True


async def test_save_reaction():
    """Test the save_reaction method."""
    print("\nTesting save_reaction method...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the StatsCogs
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Create mock objects
    reaction = MockReactionFactory.create()

    # Mock the database methods
    bot.db.execute_many = AsyncMock()

    # Call the function
    await save_reaction(cog, reaction)

    # Verify that db.execute_many was called
    bot.db.execute_many.assert_called_once()

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ save_reaction method test passed")
    return True


# Test the StatsCogs class methods


async def test_stats_cog_initialization():
    """Test the initialization of the StatsCogs class."""
    print("\nTesting StatsCogs initialization...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Create the StatsCogs
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Verify that the cog was initialized correctly
    assert cog.bot == bot
    assert cog.logger is not None

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ StatsCogs initialization test passed")
    return True


async def test_save_users():
    """Test the save_users method."""
    print("\nTesting save_users method...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Mock the database methods
    bot.db.fetch = AsyncMock(return_value=[])  # No existing users
    bot.db.execute_many = AsyncMock()

    # Create the StatsCogs
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Create a mock context
    ctx = MockContextFactory.create()

    # Create mock guild members
    members = [MockMemberFactory.create() for _ in range(3)]

    # Create a mock guild with the members
    mock_guild = MockGuildFactory.create()
    mock_guild.members = members

    # Set up the bot's guilds to include our mock guild
    bot.guilds = [mock_guild]

    # Call the method
    await cog.save_users(ctx)

    # Verify that db.fetch was called to check existing users
    assert bot.db.fetch.call_count >= 1
    # Verify that db.execute_many was called to insert new users
    assert bot.db.execute_many.call_count >= 1

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ save_users method test passed")
    return True


async def test_save_servers():
    """Test the save_servers method."""
    print("\nTesting save_servers method...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Mock the database connection
    bot.db.execute = AsyncMock()

    # Create the StatsCogs
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Create a mock context
    ctx = MockContextFactory.create()

    # Create mock guilds
    mock_guilds = [MockGuildFactory.create() for _ in range(2)]

    # Set up the bot's guilds
    bot.guilds = mock_guilds

    # Call the method
    await cog.save_servers(ctx)

    # Verify that db.execute was called for each guild
    assert bot.db.execute.call_count == len(mock_guilds)

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ save_servers method test passed")
    return True


async def test_save_channels():
    """Test the save_channels method."""
    print("\nTesting save_channels method...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Mock the database connection
    bot.db.execute = AsyncMock()

    # Create the StatsCogs
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Create a mock context
    ctx = MockContextFactory.create()

    # Create mock channels
    channels = [MockChannelFactory.create_text_channel() for _ in range(3)]

    # Create a mock guild with the channels
    mock_guild = MockGuildFactory.create()
    mock_guild.text_channels = channels

    # Set up the bot's guilds to include our mock guild
    bot.guilds = [mock_guild]

    # Call the method
    await cog.save_channels(ctx)

    # Verify that db.execute was called for each channel
    assert bot.db.execute.call_count == len(channels)

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ save_channels method test passed")
    return True


async def test_message_count_command():
    """Test the message_count command."""
    print("\nTesting message_count command...")

    # Create a test bot
    bot = await TestSetup.create_test_bot()

    # Mock the database connection
    bot.db.fetchrow = AsyncMock(return_value={"total": 42})

    # Create the StatsCogs
    cog = await TestSetup.setup_cog(bot, StatsCogs)

    # Create a mock interaction
    interaction = MockInteractionFactory.create()

    # Create a mock channel with proper mention
    channel = MockChannelFactory.create_text_channel()
    channel.mention = f"<#{channel.id}>"

    # Call the command's callback directly
    await cog.message_count.callback(cog, interaction, channel, 24)

    # Verify the response
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    content = kwargs.get("content", "")
    embed = kwargs.get("embed")
    if args:
        content = args[0]

    # Check content or embed for the response
    response_text = content
    if embed and hasattr(embed, 'description') and embed.description:
        response_text += " " + embed.description
    if embed and hasattr(embed, 'fields'):
        for field in embed.fields:
            if hasattr(field, 'value'):
                response_text += " " + str(field.value)

    assert "42" in response_text  # Check that the count is in the response
    assert channel.mention in response_text or str(channel.id) in response_text  # Check that the channel is in the response
    assert "24" in response_text  # Check that the hours are in the response

    # Clean up
    await TestTeardown.teardown_cog(bot, "stats")
    await TestTeardown.teardown_bot(bot)

    print("✅ message_count command test passed")
    return True


# Main function to run all tests
async def main():
    """Run all unit tests for the StatsCogs class."""
    print("Running StatsCogs unit tests...")

    # Test standalone functions
    await test_save_message()
    await test_save_reaction()

    # Test StatsCogs class methods
    await test_stats_cog_initialization()
    await test_save_users()
    await test_save_servers()
    await test_save_channels()
    await test_message_count_command()

    print("\nAll StatsCogs unit tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

"""
Test utilities for Twi Bot Shard.

This module provides utility functions for setting up and tearing down
test environments, including functions for creating test bots, loading
test data, and cleaning up after tests.
"""

import asyncio
import os
import sys
from typing import Any
from unittest.mock import MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord
from discord.ext import commands

# Import SQLAlchemy components
from sqlalchemy.ext.asyncio import AsyncSession

# Import project components
from tests.fixtures import DatabaseFixture, TestDataFixture
from tests.mock_factories import (
    MockChannelFactory,
    MockContextFactory,
    MockGuildFactory,
    MockInteractionFactory,
    MockMessageFactory,
    MockUserFactory,
)
from tests.test_cogs import TestBot


class TestSetup:
    """
    Utility class for setting up test environments.

    This class provides methods for setting up test environments,
    including creating test bots, loading test data, and setting up
    mock objects.
    """

    @staticmethod
    async def create_test_bot() -> TestBot:
        """
        Create a test bot instance.

        Returns:
            A TestBot instance.
        """
        bot = TestBot()
        return bot

    @staticmethod
    async def create_test_database():
        """
        Create a test database instance for transaction testing.

        Returns:
            A Database instance with a mock pool for testing.
        """
        from unittest.mock import AsyncMock

        from utils.db import Database

        # Create a mock pool
        mock_pool = AsyncMock()

        # Create a Database instance with the mock pool
        db = Database(mock_pool)

        return db

    @staticmethod
    async def setup_database() -> tuple[DatabaseFixture, TestDataFixture]:
        """
        Set up a test database and load test data.

        Returns:
            A tuple containing a DatabaseFixture and a TestDataFixture.
        """
        db_fixture = DatabaseFixture()
        await db_fixture.setup()
        test_data = TestDataFixture(db_fixture)
        return db_fixture, test_data

    @staticmethod
    async def setup_discord_mocks() -> dict[str, Any]:
        """
        Set up mock Discord objects for testing.

        Returns:
            A dictionary containing mock Discord objects.
        """
        user = MockUserFactory.create()
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        message = MockMessageFactory.create(author=user, channel=channel, guild=guild)
        interaction = MockInteractionFactory.create(
            user=user, guild=guild, channel=channel
        )
        ctx = MockContextFactory.create(author=user, guild=guild, channel=channel)

        return {
            "user": user,
            "guild": guild,
            "channel": channel,
            "message": message,
            "interaction": interaction,
            "ctx": ctx,
        }

    @staticmethod
    async def setup_cog(bot: TestBot, cog_class: type[commands.Cog]) -> commands.Cog:
        """
        Set up a cog for testing.

        Args:
            bot: The test bot instance.
            cog_class: The cog class to instantiate.

        Returns:
            An instance of the cog.
        """
        cog = cog_class(bot)
        await bot.add_cog(cog)
        return cog


class TestTeardown:
    """
    Utility class for tearing down test environments.

    This class provides methods for tearing down test environments,
    including cleaning up test bots, databases, and mock objects.
    """

    @staticmethod
    async def teardown_bot(bot: TestBot) -> None:
        """
        Clean up a test bot instance.

        Args:
            bot: The test bot instance to clean up.
        """
        await bot.close()

    @staticmethod
    async def teardown_database(db_fixture: DatabaseFixture) -> None:
        """
        Clean up a test database.

        Args:
            db_fixture: The database fixture to clean up.
        """
        await db_fixture.teardown()

    @staticmethod
    async def teardown_cog(bot: TestBot, cog_name: str) -> None:
        """
        Clean up a cog.

        Args:
            bot: The test bot instance.
            cog_name: The name of the cog to remove.
        """
        await bot.remove_cog(cog_name)


class TestAssertions:
    """
    Utility class for test assertions.

    This class provides methods for making assertions in tests,
    particularly for async code and Discord-specific assertions.
    """

    @staticmethod
    async def assert_message_sent(
        channel: discord.abc.Messageable, content: str
    ) -> None:
        """
        Assert that a message with the given content was sent to the channel.

        Args:
            channel: The channel to check.
            content: The message content to check for.
        """
        channel.send.assert_called_with(content)

    @staticmethod
    async def assert_interaction_response(
        interaction: discord.Interaction, content: str
    ) -> None:
        """
        Assert that an interaction response with the given content was sent.

        Args:
            interaction: The interaction to check.
            content: The response content to check for.
        """
        interaction.response.send_message.assert_called_with(content)

    @staticmethod
    async def assert_database_contains(
        session: AsyncSession, model_class: Any, **filters: Any
    ) -> None:
        """
        Assert that the database contains a record matching the given filters.

        Args:
            session: The database session.
            model_class: The model class to query.
            **filters: The filters to apply to the query.
        """
        from sqlalchemy.future import select

        # Build the query
        query = select(model_class)
        for attr, value in filters.items():
            query = query.where(getattr(model_class, attr) == value)

        # Execute the query
        result = await session.execute(query)
        record = result.scalars().first()

        # Assert that a record was found
        assert record is not None, (
            f"No {model_class.__name__} record found matching {filters}"
        )


class TestHelpers:
    """
    Utility class for test helpers.

    This class provides helper methods for tests, such as creating
    test data, simulating events, and other common test operations.
    """

    @staticmethod
    async def simulate_message(
        bot: TestBot,
        content: str,
        author: discord.User | discord.Member | None = None,
        channel: discord.abc.Messageable | None = None,
        guild: discord.Guild | None = None,
    ) -> discord.Message:
        """
        Simulate a message being sent.

        Args:
            bot: The test bot instance.
            content: The message content.
            author: The message author.
            channel: The channel the message was sent in.
            guild: The guild the message was sent in.

        Returns:
            The simulated message.
        """
        # Create default objects if not provided
        if author is None:
            author = MockUserFactory.create()

        if channel is None:
            channel = MockChannelFactory.create_text_channel()

        if guild is None and hasattr(channel, "guild"):
            guild = channel.guild

        # Create the message
        message = MockMessageFactory.create(
            content=content, author=author, channel=channel, guild=guild
        )

        # Simulate the on_message event
        if hasattr(bot, "on_message"):
            await bot.on_message(message)

        return message

    @staticmethod
    async def simulate_command(
        bot: TestBot,
        command_name: str,
        *args: Any,
        author: discord.User | discord.Member | None = None,
        channel: discord.abc.Messageable | None = None,
        guild: discord.Guild | None = None,
        prefix: str = "!",
    ) -> commands.Context:
        """
        Simulate a command being invoked.

        Args:
            bot: The test bot instance.
            command_name: The name of the command.
            *args: The command arguments.
            author: The command author.
            channel: The channel the command was invoked in.
            guild: The guild the command was invoked in.
            prefix: The command prefix.

        Returns:
            The command context.
        """
        # Create default objects if not provided
        if author is None:
            author = MockUserFactory.create()

        if channel is None:
            channel = MockChannelFactory.create_text_channel()

        if guild is None and hasattr(channel, "guild"):
            guild = channel.guild

        # Create the context
        ctx = MockContextFactory.create(
            author=author,
            guild=guild,
            channel=channel,
            command_name=command_name,
            prefix=prefix,
        )

        # Get the command
        command = bot.get_command(command_name)
        if command is None:
            raise ValueError(f"Command '{command_name}' not found")

        # Set the command on the context
        ctx.command = command

        # Invoke the command
        await bot.invoke(ctx)

        return ctx

    @staticmethod
    async def simulate_interaction(
        bot: TestBot,
        command_name: str,
        options: dict[str, Any] | None = None,
        user: discord.User | discord.Member | None = None,
        channel: discord.abc.Messageable | None = None,
        guild: discord.Guild | None = None,
    ) -> discord.Interaction:
        """
        Simulate a slash command interaction.

        Args:
            bot: The test bot instance.
            command_name: The name of the command.
            options: The command options.
            user: The user who triggered the interaction.
            channel: The channel the interaction was triggered in.
            guild: The guild the interaction was triggered in.

        Returns:
            The interaction.
        """
        # Create default objects if not provided
        if user is None:
            user = MockUserFactory.create()

        if channel is None:
            channel = MockChannelFactory.create_text_channel()

        if guild is None and hasattr(channel, "guild"):
            guild = channel.guild

        if options is None:
            options = {}

        # Create the interaction
        interaction = MockInteractionFactory.create(
            user=user, guild=guild, channel=channel, command_name=command_name
        )

        # Find the command
        command = None
        for cmd in bot.tree.get_commands():
            if cmd.name == command_name:
                command = cmd
                break

        if command is None:
            raise ValueError(f"Slash command '{command_name}' not found")

        # Set the command on the interaction
        interaction.command = command

        # Set the options on the interaction
        interaction.namespace = MagicMock()
        for name, value in options.items():
            setattr(interaction.namespace, name, value)

        # Invoke the command
        await command._invoke(interaction)

        return interaction


# Example usage
async def example_usage() -> None:
    """Example of how to use the test utilities."""
    # Set up a test environment
    bot = await TestSetup.create_test_bot()
    db_fixture, test_data = await TestSetup.setup_database()
    mocks = await TestSetup.setup_discord_mocks()

    try:
        # Load some test data
        await test_data.load_gallery_mementos()
        await test_data.load_command_history()

        # Set up a cog for testing
        from cogs.gallery import GalleryCog

        await TestSetup.setup_cog(bot, GalleryCog)

        # Simulate a command
        ctx = await TestHelpers.simulate_command(
            bot,
            "gallery",
            "list",
            author=mocks["user"],
            channel=mocks["channel"],
            guild=mocks["guild"],
        )

        # Make assertions
        await TestAssertions.assert_message_sent(ctx.channel, "Gallery list:")

        # Simulate an interaction
        interaction = await TestHelpers.simulate_interaction(
            bot,
            "gallery",
            {"action": "list"},
            user=mocks["user"],
            channel=mocks["channel"],
            guild=mocks["guild"],
        )

        # Make assertions
        await TestAssertions.assert_interaction_response(interaction, "Gallery list:")

        # Check the database
        async with db_fixture.create_session() as session:
            from models.tables.gallery import GalleryMementos

            await TestAssertions.assert_database_contains(
                session, GalleryMementos, channel_name="test-gallery-0"
            )

    finally:
        # Clean up
        await TestTeardown.teardown_cog(bot, "Gallery")
        await TestTeardown.teardown_database(db_fixture)
        await TestTeardown.teardown_bot(bot)


if __name__ == "__main__":
    # Run the example usage
    asyncio.run(example_usage())

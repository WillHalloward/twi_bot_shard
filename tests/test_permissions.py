"""
Test script for permission utilities.

This script tests the permission functions in utils/permissions.py.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock the config module before importing permissions
sys.modules["config"] = MagicMock()
sys.modules["config"].bot_channel_id = 111222333
sys.modules["config"].logfile = "test"


# Import permissions utilities
from utils.permissions import (
    admin_or_me_check,
    admin_or_me_check_wrapper,
    app_admin_or_me_check,
    app_is_bot_channel,
    init_permission_manager,
    is_bot_channel,
    is_bot_channel_wrapper,
)


class MockRole:
    """Mock role class for testing."""

    def __init__(self, role_id) -> None:
        self.id = role_id


class MockUser:
    """Mock user class for testing."""

    def __init__(self, user_id, roles=None) -> None:
        self.id = user_id
        self.roles = roles or []


class MockGuild:
    """Mock guild class for testing."""

    def __init__(self, guild_id) -> None:
        self.id = guild_id
        self.roles = []


class MockChannel:
    """Mock channel class for testing."""

    def __init__(self, channel_id) -> None:
        self.id = channel_id


class MockContext:
    """Mock context class for testing traditional commands."""

    def __init__(self, user_id, guild_id, channel_id, roles=None) -> None:
        self.message = MagicMock()
        self.message.author = MockUser(user_id, roles)
        self.guild = MockGuild(guild_id)
        self.channel = MockChannel(channel_id)
        self.bot = MagicMock()


class MockInteraction:
    """Mock interaction class for testing app commands."""

    def __init__(self, user_id, guild_id, channel_id, roles=None) -> None:
        self.user = MockUser(user_id, roles)
        self.guild = MockGuild(guild_id)
        self.channel = MockChannel(channel_id)
        self.client = MagicMock()
        # Add bot attribute that points to the same object as client
        self.bot = self.client
        # Add message attribute with author property that points to the same object as user
        # This is needed because admin_or_me_check uses isinstance to check if it's an Interaction
        # but our mock won't be recognized as a discord.Interaction
        self.message = MagicMock()
        self.message.author = self.user


class MockSettingsCog:
    """Mock settings cog for testing."""

    def __init__(self, is_admin_result=True) -> None:
        self.is_admin = AsyncMock(return_value=is_admin_result)


async def test_admin_or_me_check() -> bool:
    """Test the admin_or_me_check function."""
    print("\nTesting admin_or_me_check function...")

    # Create a mock bot and initialize permission manager
    mock_bot = MagicMock()
    mock_bot.db = MagicMock()

    # Initialize the permission manager
    init_permission_manager(mock_bot)

    # Create mock roles
    admin_role = MockRole(346842813687922689)
    regular_role = MockRole(123456789)

    # Test with context and admin user
    ctx = MockContext(
        user_id=123456789,
        guild_id=987654321,
        channel_id=111222333,
        roles=[regular_role, admin_role],
    )

    # Mock the settings cog
    settings_cog = MockSettingsCog(is_admin_result=True)
    ctx.bot.get_cog.return_value = settings_cog

    # Test admin check with context
    result = await admin_or_me_check(ctx)
    assert result is True
    settings_cog.is_admin.assert_called_once()

    # Reset mock
    settings_cog.is_admin.reset_mock()

    # Test with interaction and admin user
    interaction = MockInteraction(
        user_id=123456789,
        guild_id=987654321,
        channel_id=111222333,
        roles=[regular_role, admin_role],
    )

    # Mock the settings cog
    interaction.client.get_cog.return_value = settings_cog

    # Test admin check with interaction
    result = await admin_or_me_check(interaction)
    assert result is True
    settings_cog.is_admin.assert_called_once()

    # Test with bot owner
    ctx = MockContext(
        user_id=268608466690506753,  # Bot owner ID
        guild_id=987654321,
        channel_id=111222333,
        roles=[regular_role],
    )

    # Mock no settings cog to test fallback
    ctx.bot.get_cog.return_value = None

    # Test admin check with context
    result = await admin_or_me_check(ctx)
    assert result is True

    # Test with non-admin user
    ctx = MockContext(
        user_id=999999999,
        guild_id=987654321,
        channel_id=111222333,
        roles=[regular_role],
    )

    # Mock no settings cog to test fallback
    ctx.bot.get_cog.return_value = None

    # Test admin check with context
    result = await admin_or_me_check(ctx)
    assert result is False

    print("✅ admin_or_me_check test passed")
    return True


async def test_admin_check_wrappers() -> bool:
    """Test the admin check wrapper functions."""
    print("\nTesting admin check wrapper functions...")

    # Create a mock bot and initialize permission manager
    mock_bot = MagicMock()
    mock_bot.db = MagicMock()
    mock_bot.get_cog.return_value = None

    # Initialize the permission manager
    init_permission_manager(mock_bot)

    # Test admin_or_me_check_wrapper
    with patch("utils.permissions.admin_or_me_check", AsyncMock(return_value=True)):
        # Create a context
        ctx = MockContext(user_id=123456789, guild_id=987654321, channel_id=111222333)

        # Get the check function
        check_func = admin_or_me_check_wrapper(ctx)

        # Verify it's a command check by checking its attributes
        # commands.check returns a function that has a predicate attribute
        assert hasattr(check_func, "predicate")

        # Test app_admin_or_me_check
        interaction = MockInteraction(
            user_id=123456789, guild_id=987654321, channel_id=111222333
        )

        # Call the app check function
        # app_admin_or_me_check returns admin_or_me_check(interaction), which is a coroutine
        # So we need to await it
        result = await app_admin_or_me_check(interaction)

        # Verify it calls admin_or_me_check and returns True
        assert result is True

    print("✅ admin check wrapper tests passed")
    return True


async def test_is_bot_channel() -> bool:
    """Test the is_bot_channel function."""
    print("\nTesting is_bot_channel function...")

    # Import config module and patch it directly
    import config

    # Patch the config.bot_channel_id directly
    with patch.object(config, "bot_channel_id", 111222333):
        # Test with context in bot channel
        ctx = MockContext(user_id=123456789, guild_id=987654321, channel_id=111222333)

        # Test bot channel check with context (is_bot_channel is async)
        result = await is_bot_channel(ctx)
        assert result is True

        # Test with interaction in bot channel
        interaction = MockInteraction(
            user_id=123456789, guild_id=987654321, channel_id=111222333
        )

        # Test bot channel check with interaction (is_bot_channel is async)
        result = await is_bot_channel(interaction)
        assert result is True

        # Test with context not in bot channel
        ctx = MockContext(user_id=123456789, guild_id=987654321, channel_id=999999999)

        # Test bot channel check with context (is_bot_channel is async)
        result = await is_bot_channel(ctx)
        assert result is False

    print("✅ is_bot_channel test passed")
    return True


async def test_bot_channel_wrappers() -> bool:
    """Test the bot channel wrapper functions."""
    print("\nTesting bot channel wrapper functions...")

    # Import config module and patch it directly
    import config

    # Test is_bot_channel_wrapper
    with patch.object(config, "bot_channel_id", 111222333):
        # Create a context
        ctx = MockContext(user_id=123456789, guild_id=987654321, channel_id=111222333)

        # Get the check function
        check_func = is_bot_channel_wrapper(ctx)

        # Verify it's a command check by checking its attributes
        # commands.check returns a function that has a predicate attribute
        assert hasattr(check_func, "predicate")

        # Test app_is_bot_channel
        interaction = MockInteraction(
            user_id=123456789, guild_id=987654321, channel_id=111222333
        )

        # Call the app check function
        # app_is_bot_channel is now async and returns await is_bot_channel(interaction)
        # So we need to await it
        result = await app_is_bot_channel(interaction)

        # Verify it calls is_bot_channel and returns True
        assert result is True

    print("✅ bot channel wrapper tests passed")
    return True


async def main() -> bool | None:
    """Run all tests."""
    print("Testing permission utilities...")

    try:
        # Run tests
        tests = [
            test_admin_or_me_check(),
            test_admin_check_wrappers(),
            test_is_bot_channel(),
            test_bot_channel_wrappers(),
        ]

        results = await asyncio.gather(*tests)

        if all(results):
            print("\nAll permission tests passed!")
            return True
        else:
            print("\nSome permission tests failed.")
            return False

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

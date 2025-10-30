"""
Test script for permission utilities.

This script tests the permission functions in utils/permissions.py with proper mocking.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


@pytest.fixture
def mock_config():
    """Fixture to mock config module with bot_channel_id."""
    with patch.dict(sys.modules, {'config': MagicMock(bot_channel_id=111222333, logfile='test')}):
        yield


@pytest.fixture
def mock_permission_manager():
    """Fixture to mock permission manager."""
    with patch('utils.permissions.get_permission_manager') as mock_get_pm:
        mock_pm = MagicMock()
        mock_pm.check_permission = AsyncMock(return_value=True)
        mock_get_pm.return_value = mock_pm
        yield mock_pm


class MockRole:
    """Mock role class for testing."""

    def __init__(self, role_id):
        self.id = role_id


class MockUser:
    """Mock user class for testing."""

    def __init__(self, user_id, roles=None):
        self.id = user_id
        self.roles = roles or []


class MockGuild:
    """Mock guild class for testing."""

    def __init__(self, guild_id):
        self.id = guild_id
        self.roles = []


class MockChannel:
    """Mock channel class for testing."""

    def __init__(self, channel_id):
        self.id = channel_id


class MockContext:
    """Mock context class for testing traditional commands."""

    def __init__(self, user_id, guild_id, channel_id, roles=None):
        self.message = MagicMock()
        self.message.author = MockUser(user_id, roles)
        self.author = MockUser(user_id, roles)
        self.guild = MockGuild(guild_id)
        self.channel = MockChannel(channel_id)
        self.bot = MagicMock()


class MockInteraction:
    """Mock interaction class for testing app commands."""

    def __init__(self, user_id, guild_id, channel_id, roles=None):
        self.user = MockUser(user_id, roles)
        self.guild = MockGuild(guild_id)
        self.channel = MockChannel(channel_id)
        self.client = MagicMock()
        self.bot = self.client


@pytest.mark.asyncio
async def test_admin_or_me_check(mock_permission_manager):
    """Test the admin_or_me_check function."""
    from utils.permissions import admin_or_me_check

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

    # Mock the bot's get_cog to return a settings cog with is_admin
    mock_settings_cog = MagicMock()
    mock_settings_cog.is_admin = AsyncMock(return_value=True)
    ctx.bot.get_cog = MagicMock(return_value=mock_settings_cog)

    # Test admin check with context
    result = await admin_or_me_check(ctx)
    assert result is True

    # Test with bot owner (should pass without checking settings cog)
    mock_permission_manager.check_permission = AsyncMock(return_value=True)
    ctx = MockContext(
        user_id=268608466690506753,  # Bot owner ID
        guild_id=987654321,
        channel_id=111222333,
        roles=[regular_role],
    )
    ctx.bot.get_cog = MagicMock(return_value=None)

    result = await admin_or_me_check(ctx)
    assert result is True


@pytest.mark.asyncio
async def test_admin_check_wrappers(mock_permission_manager):
    """Test the admin check wrapper functions."""
    from utils.permissions import admin_or_me_check_wrapper, app_admin_or_me_check

    # Create a context
    ctx = MockContext(user_id=123456789, guild_id=987654321, channel_id=111222333)

    # Get the check function
    check_func = admin_or_me_check_wrapper(ctx)

    # Verify it's a command check by checking its attributes
    assert hasattr(check_func, "predicate")

    # Test app_admin_or_me_check
    interaction = MockInteraction(
        user_id=123456789, guild_id=987654321, channel_id=111222333
    )

    # Mock the interaction's client get_cog
    mock_settings_cog = MagicMock()
    mock_settings_cog.is_admin = AsyncMock(return_value=True)
    interaction.client.get_cog = MagicMock(return_value=mock_settings_cog)

    # Call the app check function
    result = await app_admin_or_me_check(interaction)

    # Verify it returns True (mocked permission manager always returns True)
    assert result is True


@pytest.mark.asyncio
async def test_is_bot_channel():
    """Test the is_bot_channel function."""
    # Mock config at module level before importing the function
    with patch('utils.permissions.config') as mock_config:
        mock_config.bot_channel_id = 111222333

        from utils.permissions import is_bot_channel

        # Test with context in bot channel
        ctx = MockContext(user_id=123456789, guild_id=987654321, channel_id=111222333)
        result = await is_bot_channel(ctx)
        assert result is True

        # Test with interaction in bot channel
        interaction = MockInteraction(
            user_id=123456789, guild_id=987654321, channel_id=111222333
        )
        result = await is_bot_channel(interaction)
        assert result is True

        # Test with context in wrong channel
        ctx = MockContext(user_id=123456789, guild_id=987654321, channel_id=999999999)
        result = await is_bot_channel(ctx)
        assert result is False


@pytest.mark.asyncio
async def test_bot_channel_wrappers():
    """Test the bot channel wrapper functions."""
    with patch('utils.permissions.config') as mock_config:
        mock_config.bot_channel_id = 111222333

        from utils.permissions import is_bot_channel_wrapper, app_is_bot_channel

        # Create a context
        ctx = MockContext(user_id=123456789, guild_id=987654321, channel_id=111222333)

        # Get the check function
        check_func = is_bot_channel_wrapper(ctx)

        # Verify it's a command check by checking its attributes
        assert hasattr(check_func, "predicate")

        # Test app_is_bot_channel
        interaction = MockInteraction(
            user_id=123456789, guild_id=987654321, channel_id=111222333
        )

        # Call the app check function
        result = await app_is_bot_channel(interaction)

        # Verify it calls is_bot_channel and returns True
        assert result is True


def main():
    """Run tests with pytest."""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    main()

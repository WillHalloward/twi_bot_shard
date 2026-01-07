"""Test script for permission utilities.

This script tests the permission functions in utils/permissions.py with proper mocking.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


class MockRole:
    """Mock role class for testing."""

    def __init__(self, role_id):
        self.id = role_id


class MockGuildPermissions:
    """Mock guild permissions for testing."""

    def __init__(self, administrator=False, ban_members=False):
        self.administrator = administrator
        self.ban_members = ban_members


class MockMember:
    """Mock member class for testing."""

    def __init__(self, user_id, roles=None, administrator=False, ban_members=False):
        self.id = user_id
        self.roles = roles or []
        self.guild_permissions = MockGuildPermissions(administrator, ban_members)


class MockUser:
    """Mock user class for testing."""

    def __init__(self, user_id, roles=None):
        self.id = user_id
        self.roles = roles or []


class MockGuild:
    """Mock guild class for testing."""

    def __init__(self, guild_id, members=None):
        self.id = guild_id
        self.roles = []
        self._members = members or {}

    def get_member(self, user_id):
        return self._members.get(user_id)


class MockChannel:
    """Mock channel class for testing."""

    def __init__(self, channel_id):
        self.id = channel_id


class MockContext:
    """Mock context class for testing traditional commands."""

    def __init__(self, user_id, guild, channel_id, roles=None, bot=None):
        self.author = MockUser(user_id, roles)
        self.guild = guild
        self.channel = MockChannel(channel_id)
        self.bot = bot or MagicMock()


class MockInteraction:
    """Mock interaction class for testing app commands."""

    def __init__(self, user_id, guild, channel_id, roles=None, client=None):
        self.user = MockUser(user_id, roles)
        self.guild = guild
        self.channel = MockChannel(channel_id)
        self.client = client or MagicMock()


@pytest.fixture
def mock_bot():
    """Create a mock bot with settings cog."""
    bot = MagicMock()
    mock_settings_cog = MagicMock()
    mock_settings_cog.is_admin = AsyncMock(return_value=False)
    bot.get_cog = MagicMock(return_value=mock_settings_cog)
    return bot


@pytest.fixture
def mock_config():
    """Fixture to mock config module."""
    with patch("utils.permissions.config") as cfg:
        cfg.bot_owner_id = 268608466690506753
        cfg.bot_channel_id = 111222333
        yield cfg


@pytest.mark.asyncio
async def test_is_bot_owner(mock_config):
    """Test the is_bot_owner function."""
    from utils.permissions import is_bot_owner

    assert is_bot_owner(268608466690506753) is True
    assert is_bot_owner(123456789) is False


@pytest.mark.asyncio
async def test_is_admin_bot_owner(mock_config, mock_bot):
    """Test is_admin returns True for bot owner."""
    from utils.permissions import is_admin

    result = await is_admin(mock_bot, 987654321, 268608466690506753)
    assert result is True


@pytest.mark.asyncio
async def test_is_admin_discord_admin(mock_config, mock_bot):
    """Test is_admin returns True for Discord administrators."""
    from utils.permissions import is_admin

    # Create member with administrator permission
    member = MockMember(123456789, administrator=True)
    guild = MockGuild(987654321, members={123456789: member})
    mock_bot.get_guild = MagicMock(return_value=guild)

    result = await is_admin(mock_bot, 987654321, 123456789)
    assert result is True


@pytest.mark.asyncio
async def test_is_admin_settings_cog(mock_config, mock_bot):
    """Test is_admin delegates to settings cog for non-Discord admins."""
    from utils.permissions import is_admin

    # Create regular member
    member = MockMember(123456789, administrator=False)
    guild = MockGuild(987654321, members={123456789: member})
    mock_bot.get_guild = MagicMock(return_value=guild)

    # Settings cog says user is admin
    mock_bot.get_cog.return_value.is_admin = AsyncMock(return_value=True)

    result = await is_admin(mock_bot, 987654321, 123456789)
    assert result is True


@pytest.mark.asyncio
async def test_is_admin_regular_user(mock_config, mock_bot):
    """Test is_admin returns False for regular users."""
    from utils.permissions import is_admin

    # Create regular member
    member = MockMember(123456789, administrator=False)
    guild = MockGuild(987654321, members={123456789: member})
    mock_bot.get_guild = MagicMock(return_value=guild)

    # Settings cog says user is not admin
    mock_bot.get_cog.return_value.is_admin = AsyncMock(return_value=False)

    result = await is_admin(mock_bot, 987654321, 123456789)
    assert result is False


@pytest.mark.asyncio
async def test_is_moderator_bot_owner(mock_config, mock_bot):
    """Test is_moderator returns True for bot owner."""
    from utils.permissions import is_moderator

    result = await is_moderator(mock_bot, 987654321, 268608466690506753)
    assert result is True


@pytest.mark.asyncio
async def test_is_moderator_ban_members(mock_config, mock_bot):
    """Test is_moderator returns True for users with ban_members permission."""
    from utils.permissions import is_moderator

    member = MockMember(123456789, ban_members=True)
    guild = MockGuild(987654321, members={123456789: member})
    mock_bot.get_guild = MagicMock(return_value=guild)

    result = await is_moderator(mock_bot, 987654321, 123456789)
    assert result is True


@pytest.mark.asyncio
async def test_admin_or_me_check_admin(mock_config, mock_bot):
    """Test admin_or_me_check passes for admins."""
    from utils.permissions import admin_or_me_check

    # Create admin member
    admin_role = MockRole(346842813687922689)
    member = MockMember(123456789, roles=[admin_role], administrator=True)
    guild = MockGuild(987654321, members={123456789: member})
    mock_bot.get_guild = MagicMock(return_value=guild)

    ctx = MockContext(
        user_id=123456789,
        guild=guild,
        channel_id=111222333,
        roles=[admin_role],
        bot=mock_bot,
    )

    result = await admin_or_me_check(ctx)
    assert result is True


@pytest.mark.asyncio
async def test_admin_or_me_check_bot_owner(mock_config, mock_bot):
    """Test admin_or_me_check passes for bot owner."""
    from utils.permissions import admin_or_me_check

    guild = MockGuild(987654321)
    mock_bot.get_guild = MagicMock(return_value=guild)

    ctx = MockContext(
        user_id=268608466690506753,  # Bot owner
        guild=guild,
        channel_id=111222333,
        bot=mock_bot,
    )

    result = await admin_or_me_check(ctx)
    assert result is True


@pytest.mark.asyncio
async def test_admin_or_me_check_no_permission(mock_config, mock_bot):
    """Test admin_or_me_check raises for regular users."""
    from utils.exceptions import PermissionError
    from utils.permissions import admin_or_me_check

    # Create regular member
    member = MockMember(123456789, administrator=False)
    guild = MockGuild(987654321, members={123456789: member})
    mock_bot.get_guild = MagicMock(return_value=guild)
    mock_bot.get_cog.return_value.is_admin = AsyncMock(return_value=False)

    ctx = MockContext(
        user_id=123456789,
        guild=guild,
        channel_id=111222333,
        bot=mock_bot,
    )

    with pytest.raises(PermissionError):
        await admin_or_me_check(ctx)


@pytest.mark.asyncio
async def test_admin_check_wrappers(mock_config, mock_bot):
    """Test the admin check wrapper functions."""
    from utils.permissions import admin_or_me_check_wrapper, app_admin_or_me_check

    # Create admin member
    member = MockMember(123456789, administrator=True)
    guild = MockGuild(987654321, members={123456789: member})
    mock_bot.get_guild = MagicMock(return_value=guild)

    # Test context wrapper
    ctx = MockContext(
        user_id=123456789, guild=guild, channel_id=111222333, bot=mock_bot
    )
    check_func = admin_or_me_check_wrapper(ctx)
    assert hasattr(check_func, "predicate")

    # Test interaction wrapper
    interaction = MockInteraction(
        user_id=123456789, guild=guild, channel_id=111222333, client=mock_bot
    )
    result = await app_admin_or_me_check(interaction)
    assert result is True


@pytest.mark.asyncio
async def test_is_bot_channel(mock_config):
    """Test the is_bot_channel function."""
    from utils.permissions import is_bot_channel

    guild = MockGuild(987654321)

    # Test in bot channel
    ctx = MockContext(user_id=123456789, guild=guild, channel_id=111222333)
    result = await is_bot_channel(ctx)
    assert result is True

    # Test in wrong channel
    ctx = MockContext(user_id=123456789, guild=guild, channel_id=999999999)
    result = await is_bot_channel(ctx)
    assert result is False


@pytest.mark.asyncio
async def test_bot_channel_wrappers(mock_config):
    """Test the bot channel wrapper functions."""
    from utils.permissions import app_is_bot_channel, is_bot_channel_wrapper

    guild = MockGuild(987654321)

    # Test context wrapper
    ctx = MockContext(user_id=123456789, guild=guild, channel_id=111222333)
    check_func = is_bot_channel_wrapper(ctx)
    assert hasattr(check_func, "predicate")

    # Test app wrapper
    interaction = MockInteraction(user_id=123456789, guild=guild, channel_id=111222333)
    result = await app_is_bot_channel(interaction)
    assert result is True


@pytest.mark.asyncio
async def test_owner_only_check(mock_config):
    """Test owner_only_check function."""
    from utils.exceptions import OwnerOnlyError
    from utils.permissions import owner_only_check

    guild = MockGuild(987654321)

    # Test with owner
    ctx = MockContext(user_id=268608466690506753, guild=guild, channel_id=111222333)
    result = await owner_only_check(ctx)
    assert result is True

    # Test with non-owner
    ctx = MockContext(user_id=123456789, guild=guild, channel_id=111222333)
    with pytest.raises(OwnerOnlyError):
        await owner_only_check(ctx)


def main():
    """Run tests with pytest."""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    main()

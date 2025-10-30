"""
Unit tests for Mods Cog commands and event listeners.

This module tests the moderation commands and event listeners in the ModCogs,
including reset, state, log_attachment, dm_watch, find_links, and filter_new_users.
"""

import os
import sys
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord

# Import the cog to test
from cogs.mods import ModCogs

# Import test utilities
from tests.mock_factories import (
    MockInteractionFactory,
    MockMessageFactory,
    MockChannelFactory,
    MockUserFactory,
    MockGuildFactory,
    MockMemberFactory,
)
from tests.test_utils import TestSetup, TestTeardown
from utils.exceptions import ValidationError, ResourceNotFoundError


class TestResetCommand:
    """Tests for /mod reset command."""

    @pytest.mark.asyncio
    async def test_reset_success(self):
        """Test successfully resetting a command cooldown."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        guild = MockGuildFactory.create()
        interaction = MockInteractionFactory.create(guild=guild)

        # Create a mock command with cooldown
        mock_command = MagicMock()
        mock_command.name = "test_command"
        mock_command._buckets = MagicMock()  # Has cooldown
        mock_command.reset_cooldown = MagicMock()

        bot.get_command = MagicMock(return_value=mock_command)

        await cog.reset.callback(cog, interaction, command="test_command")

        interaction.response.send_message.assert_called_once()
        args = interaction.response.send_message.call_args[0]
        assert "Successfully reset" in args[0]
        mock_command.reset_cooldown.assert_called_once()


class TestStateCommand:
    """Tests for /mod state command."""

    @pytest.mark.asyncio
    async def test_state_success(self):
        """Test successfully posting a moderator message."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        guild = MockGuildFactory.create()
        user = MockUserFactory.create()
        interaction = MockInteractionFactory.create(guild=guild, user=user)

        await cog.state.callback(cog, interaction, message="Test moderator message")

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args.kwargs.get('embed')

        assert embed is not None
        assert "MODERATOR MESSAGE" in embed.title
        assert "Test moderator message" in embed.description


class TestLogAttachmentListener:
    """Tests for log_attachment event listener."""

    @pytest.mark.asyncio
    async def test_log_attachment_success(self):
        """Test logging an attachment to webhook."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        user = MockUserFactory.create(bot=False)
        message = MockMessageFactory.create(channel=channel, author=user)

        # Add mock attachment
        mock_attachment = MagicMock()
        mock_attachment.filename = "test.png"
        mock_attachment.is_spoiler = MagicMock(return_value=False)
        mock_attachment.to_file = AsyncMock()
        message.attachments = [mock_attachment]

        # Mock webhook manager
        mock_webhook = AsyncMock()
        mock_webhook.send = AsyncMock()
        cog.webhook_manager.get_webhook = MagicMock(
            return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_webhook), __aexit__=AsyncMock())
        )

        await cog.log_attachment(message)

        # Verify webhook was called
        assert cog.webhook_manager.get_webhook.called

    @pytest.mark.asyncio
    async def test_log_attachment_ignores_bot_messages(self):
        """Test that bot messages are ignored."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        bot_user = MockUserFactory.create(bot=True)
        message = MockMessageFactory.create(channel=channel, author=bot_user)

        mock_attachment = MagicMock()
        message.attachments = [mock_attachment]

        # Mock webhook manager
        cog.webhook_manager.get_webhook = MagicMock()

        await cog.log_attachment(message)

        # Webhook should not be called for bot messages
        cog.webhook_manager.get_webhook.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_attachment_no_attachments(self):
        """Test that messages without attachments are ignored."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        user = MockUserFactory.create(bot=False)
        message = MockMessageFactory.create(channel=channel, author=user)
        message.attachments = []

        # Mock webhook manager
        cog.webhook_manager.get_webhook = MagicMock()

        await cog.log_attachment(message)

        # Webhook should not be called without attachments
        cog.webhook_manager.get_webhook.assert_not_called()


class TestDMWatchListener:
    """Tests for dm_watch event listener."""

    @pytest.mark.asyncio
    async def test_dm_watch_webhook_manager_called(self):
        """Test that webhook manager is called for DM messages."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        # Create DM channel mock that passes isinstance check
        dm_channel = MagicMock(spec=discord.DMChannel)
        user = MockUserFactory.create(bot=False)
        message = MockMessageFactory.create(channel=dm_channel, author=user, content="Test DM message")
        message.attachments = []
        dm_channel.recipient = None

        # Mock webhook manager
        mock_webhook = AsyncMock()
        mock_webhook.send = AsyncMock()
        cog.webhook_manager.get_webhook = MagicMock(
            return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_webhook), __aexit__=AsyncMock())
        )

        await cog.dm_watch(message)

        # Verify webhook was called
        assert cog.webhook_manager.get_webhook.called


class TestFindLinksListener:
    """Tests for find_links event listener."""

    @pytest.mark.asyncio
    async def test_find_links_detects_link(self):
        """Test detecting links in messages from the correct guild."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        # Create message with specific guild ID (346842016480755724)
        guild = MockGuildFactory.create()
        guild.id = 346842016480755724
        channel = MockChannelFactory.create_text_channel(guild=guild)
        user = MockUserFactory.create(bot=False)
        message = MockMessageFactory.create(
            channel=channel,
            author=user,
            content="Check out http://example.com"
        )
        message.guild = guild  # Set guild on message

        # Mock webhook manager
        mock_webhook = AsyncMock()
        mock_webhook.send = AsyncMock()
        cog.webhook_manager.get_webhook = MagicMock(
            return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_webhook), __aexit__=AsyncMock())
        )

        await cog.find_links(message)

        # Verify webhook was called
        assert cog.webhook_manager.get_webhook.called

    @pytest.mark.asyncio
    async def test_find_links_no_link_in_message(self):
        """Test that messages without links are ignored."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        guild = MockGuildFactory.create()
        guild.id = 346842016480755724
        channel = MockChannelFactory.create_text_channel(guild=guild)
        user = MockUserFactory.create(bot=False)
        message = MockMessageFactory.create(
            channel=channel,
            author=user,
            content="Just a regular message without links"
        )
        message.guild = guild  # Set guild on message

        # Mock webhook manager
        cog.webhook_manager.get_webhook = MagicMock()

        await cog.find_links(message)

        # Webhook should not be called without links
        cog.webhook_manager.get_webhook.assert_not_called()


class TestFilterNewUsersListener:
    """Tests for filter_new_users event listener."""

    @pytest.mark.asyncio
    async def test_filter_new_users_adds_verified_role(self):
        """Test auto-verifying users with accounts older than 72 hours."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        guild = MockGuildFactory.create()

        # Mock verified role
        verified_role = MagicMock()
        verified_role.id = 945388135355924571
        guild.get_role = MagicMock(return_value=verified_role)

        # Create member with old account
        member = MockMemberFactory.create()
        member.guild = guild
        old_date = datetime.now(UTC) - timedelta(hours=100)
        member.created_at = old_date.replace(tzinfo=UTC)
        member.add_roles = AsyncMock()

        await cog.filter_new_users(member)

        # Verify role was added
        member.add_roles.assert_called_once_with(verified_role)

    @pytest.mark.asyncio
    async def test_filter_new_users_skips_new_accounts(self):
        """Test that new accounts (< 72 hours) are not auto-verified."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        guild = MockGuildFactory.create()

        # Mock verified role
        verified_role = MagicMock()
        verified_role.id = 945388135355924571
        guild.get_role = MagicMock(return_value=verified_role)

        # Create member with new account (24 hours old)
        member = MockMemberFactory.create()
        member.guild = guild
        new_date = datetime.now(UTC) - timedelta(hours=24)
        member.created_at = new_date.replace(tzinfo=UTC)
        member.add_roles = AsyncMock()

        await cog.filter_new_users(member)

        # Verify role was NOT added
        member.add_roles.assert_not_called()


class TestModsEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_log_attachment_webhook_error(self):
        """Test handling of webhook errors in log_attachment."""
        bot = await TestSetup.create_test_bot()
        cog = ModCogs(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        user = MockUserFactory.create(bot=False)
        message = MockMessageFactory.create(channel=channel, author=user)

        mock_attachment = MagicMock()
        mock_attachment.filename = "test.png"
        message.attachments = [mock_attachment]

        # Mock webhook failure
        cog.webhook_manager.get_webhook = MagicMock(side_effect=Exception("Webhook error"))

        # Should not raise - errors are logged
        await cog.log_attachment(message)

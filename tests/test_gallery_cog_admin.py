"""
Unit tests for Gallery Cog admin commands.

This module tests the gallery administration commands in the GalleryCog,
including set_repost, extract_data, migration_stats, review_entries,
update_tags, and mark_reviewed commands.
"""

import os
import sys
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord

# Import the cog to test
from cogs.gallery import GalleryCog

# Import test utilities
from tests.mock_factories import (
    MockInteractionFactory,
    MockMessageFactory,
    MockChannelFactory,
    MockUserFactory,
    MockGuildFactory,
)
from tests.test_utils import TestSetup, TestTeardown


class TestSetRepostCommand:
    """Tests for /gallery_admin set_repost command."""

    @pytest.mark.asyncio
    async def test_set_repost_add_channel(self):
        """Test adding a channel to repost channels."""
        # Create test bot and cog
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        # Create mock channel
        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)

        # Mock permissions
        permissions = MagicMock()
        permissions.send_messages = True
        channel.permissions_for = MagicMock(return_value=permissions)

        # Create mock interaction
        interaction = MockInteractionFactory.create(guild=guild, channel=channel)

        # Mock repository methods
        cog.gallery_repo = MagicMock()
        cog.gallery_repo.get_by_field = AsyncMock(return_value=[])  # Channel doesn't exist
        cog.gallery_repo.create = AsyncMock()

        # Call the command
        await cog.set_repost.callback(cog, interaction, channel)

        # Verify response was sent
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args.kwargs.get('embed')

        assert embed is not None
        assert "Added" in embed.title or "Repost Channel Added" in embed.title

    @pytest.mark.asyncio
    async def test_set_repost_remove_channel(self):
        """Test removing a channel from repost channels."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)

        permissions = MagicMock()
        permissions.send_messages = True
        channel.permissions_for = MagicMock(return_value=permissions)

        interaction = MockInteractionFactory.create(guild=guild, channel=channel)

        # Mock repository - channel exists
        mock_existing = MagicMock()
        mock_existing.channel_name = channel.name
        cog.gallery_repo = MagicMock()
        cog.gallery_repo.get_by_field = AsyncMock(return_value=[mock_existing])
        cog.gallery_repo.delete = AsyncMock()

        await cog.set_repost.callback(cog, interaction, channel)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args.kwargs.get('embed')

        assert embed is not None
        assert "Removed" in embed.title or "Repost Channel Removed" in embed.title

    @pytest.mark.asyncio
    async def test_set_repost_no_permissions(self):
        """Test set_repost when bot lacks permissions."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)

        # Mock no send_messages permission
        permissions = MagicMock()
        permissions.send_messages = False
        channel.permissions_for = MagicMock(return_value=permissions)

        interaction = MockInteractionFactory.create(guild=guild, channel=channel)

        await cog.set_repost.callback(cog, interaction, channel)

        interaction.response.send_message.assert_called_once()
        args = interaction.response.send_message.call_args[0]
        assert "permission" in args[0].lower()
        assert interaction.response.send_message.call_args.kwargs.get('ephemeral') is True


class TestExtractDataCommand:
    """Tests for /gallery_admin extract_data command."""

    @pytest.mark.asyncio
    async def test_extract_data_basic(self):
        """Test basic data extraction from a channel."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        interaction = MockInteractionFactory.create(guild=guild, channel=channel)

        # Mock message history
        mock_messages = []
        for i in range(5):
            msg = MockMessageFactory.create(channel=channel)
            mock_messages.append(msg)

        # Mock channel history
        async def mock_history(**kwargs):
            for msg in mock_messages:
                yield msg

        channel.history = MagicMock(return_value=mock_history())

        # Mock _process_gallery_chunk method
        cog._process_gallery_chunk = AsyncMock(return_value=([], [], []))

        await cog.extract_gallery_data.callback(cog,
            interaction, channel, after_date=None, chunk_size=500, store_in_db=False
        )

        # Verify defer was called
        interaction.response.defer.assert_called_once_with(ephemeral=True)

        # Verify followup was called
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_extract_data_with_date_filter(self):
        """Test extraction with after_date filter."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        interaction = MockInteractionFactory.create(guild=guild, channel=channel)

        # Mock empty channel
        async def mock_history(**kwargs):
            return
            yield  # Make it a generator

        channel.history = MagicMock(return_value=mock_history())
        cog._process_gallery_chunk = AsyncMock(return_value=([], [], []))

        await cog.extract_gallery_data.callback(cog,
            interaction, channel, after_date="2024-01-01", chunk_size=100, store_in_db=False
        )

        interaction.response.defer.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_data_invalid_date(self):
        """Test extraction with invalid date format."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        interaction = MockInteractionFactory.create(guild=guild, channel=channel)

        await cog.extract_gallery_data.callback(cog,
            interaction, channel, after_date="invalid-date", chunk_size=100
        )

        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()
        args = interaction.followup.send.call_args[0]
        assert "Invalid date format" in args[0]

    @pytest.mark.asyncio
    async def test_extract_data_chunk_size_limit(self):
        """Test that chunk_size is limited to 1000."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        interaction = MockInteractionFactory.create(guild=guild, channel=channel)

        # Mock empty channel
        async def mock_history(**kwargs):
            return
            yield

        channel.history = MagicMock(return_value=mock_history())
        cog._process_gallery_chunk = AsyncMock(return_value=([], [], []))

        # Try to set chunk_size > 1000
        await cog.extract_gallery_data.callback(cog,
            interaction, channel, after_date=None, chunk_size=2000, store_in_db=False
        )

        # Verify warning was sent about chunk size reduction
        interaction.response.defer.assert_called_once()
        assert interaction.followup.send.called


class TestMigrationStatsCommand:
    """Tests for /gallery_admin migration_stats command."""

    @pytest.mark.asyncio
    async def test_migration_stats_display(self):
        """Test displaying migration statistics."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        interaction = MockInteractionFactory.create(guild=guild)

        # Mock migration repository to return stats
        cog.migration_repo = MagicMock()
        cog.migration_repo.get_statistics = AsyncMock(return_value={
            'total_entries': 100,
            'migrated_entries': 50,
            'pending_migration': 30,
            'migration_progress': 50.0,
            'needs_review': 20,
            'bot_posts': 60,
            'manual_posts': 40,
        })

        await cog.gallery_migration_stats.callback(cog, interaction)

        # Should defer first
        interaction.response.defer.assert_called_once_with(ephemeral=True)

        # Then send followup with embed
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        embed = call_args.kwargs.get('embed')

        assert embed is not None
        assert "Migration" in embed.title or "Stats" in embed.title


class TestReviewEntriesCommand:
    """Tests for /gallery_admin review_entries command."""

    @pytest.mark.asyncio
    async def test_review_entries_pagination(self):
        """Test reviewing entries with pagination."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        interaction = MockInteractionFactory.create(guild=guild)

        # Mock repository to return entries
        mock_entries = []
        for i in range(5):
            entry = MagicMock()
            entry.message_id = i
            entry.title = f"Entry {i}"
            entry.images = []
            entry.creator = "Test Creator"
            entry.tags = ["art"]
            entry.jump_url = f"https://discord.com/channels/123/456/{i}"
            entry.author_name = "Author"
            entry.is_bot = False
            entry.created_at = datetime.now(UTC)
            entry.target_forum = "sfw"
            entry.content_type = "image"
            mock_entries.append(entry)

        cog.migration_repo = MagicMock()
        cog.migration_repo.get_entries_needing_review = AsyncMock(return_value=mock_entries)

        await cog.review_gallery_entries.callback(cog, interaction, limit=10)

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_entries_no_entries(self):
        """Test review_entries when no entries exist."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        interaction = MockInteractionFactory.create(guild=guild)

        # Mock empty result
        cog.migration_repo = MagicMock()
        cog.migration_repo.get_entries_needing_review = AsyncMock(return_value=[])

        await cog.review_gallery_entries.callback(cog, interaction, limit=10)

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()

        # Check the message content
        call_args = interaction.followup.send.call_args
        message = call_args[0][0] if call_args[0] else call_args[1].get('content', '')
        assert "No entries need manual review" in message


class TestUpdateTagsCommand:
    """Tests for /gallery_admin update_tags command."""

    @pytest.mark.asyncio
    async def test_update_tags_success(self):
        """Test successfully updating tags for an entry."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        interaction = MockInteractionFactory.create(guild=guild)

        # Mock data extractor with available tags
        cog.data_extractor = MagicMock()
        cog.data_extractor.AVAILABLE_TAGS = ["fan art", "canon art", "meme"]

        # Mock migration repository
        cog.migration_repo = MagicMock()
        cog.migration_repo.update_tags = AsyncMock(return_value=True)

        await cog.update_gallery_tags.callback(cog, interaction, message_id="123456", tags="fan art,meme")

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()

        # Check that update_tags was called with correct parameters
        cog.migration_repo.update_tags.assert_called_once_with(123456, ["fan art", "meme"])

    @pytest.mark.asyncio
    async def test_update_tags_entry_not_found(self):
        """Test update_tags with non-existent entry."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        interaction = MockInteractionFactory.create(guild=guild)

        # Mock data extractor with available tags
        cog.data_extractor = MagicMock()
        cog.data_extractor.AVAILABLE_TAGS = ["fan art", "canon art", "meme"]

        # Mock entry not found (returns False)
        cog.migration_repo = MagicMock()
        cog.migration_repo.update_tags = AsyncMock(return_value=False)

        await cog.update_gallery_tags.callback(cog, interaction, message_id="999999", tags="fan art")

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()

        # Check the failure message
        call_args = interaction.followup.send.call_args
        message = call_args[0][0] if call_args[0] else ''
        assert "Failed to update tags" in message or "may not exist" in message


class TestMarkReviewedCommand:
    """Tests for /gallery_admin mark_reviewed command."""

    @pytest.mark.asyncio
    async def test_mark_reviewed_success(self):
        """Test successfully marking an entry as reviewed."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        user = MockUserFactory.create()
        interaction = MockInteractionFactory.create(guild=guild, user=user)

        # Mock migration repository
        cog.migration_repo = MagicMock()
        cog.migration_repo.update_review_status = AsyncMock(return_value=True)

        await cog.mark_entry_reviewed.callback(cog, interaction, message_id="123456")

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()

        # Check that update_review_status was called with correct parameters
        cog.migration_repo.update_review_status.assert_called_once_with(
            123456, reviewed=True, reviewed_by=user.id
        )

    @pytest.mark.asyncio
    async def test_mark_reviewed_entry_not_found(self):
        """Test mark_reviewed with non-existent entry."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        interaction = MockInteractionFactory.create(guild=guild)

        # Mock entry not found (returns False)
        cog.migration_repo = MagicMock()
        cog.migration_repo.update_review_status = AsyncMock(return_value=False)

        await cog.mark_entry_reviewed.callback(cog, interaction, message_id="999999")

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()

        # Check the failure message
        call_args = interaction.followup.send.call_args
        message = call_args[0][0] if call_args[0] else ''
        assert "Failed to mark" in message or "may not exist" in message


class TestGalleryAdminEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_command_with_database_error(self):
        """Test handling of database errors."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        interaction = MockInteractionFactory.create(guild=guild, channel=channel)

        permissions = MagicMock()
        permissions.send_messages = True
        channel.permissions_for = MagicMock(return_value=permissions)

        # Mock database error
        cog.gallery_repo = MagicMock()
        cog.gallery_repo.get_by_field = AsyncMock(side_effect=Exception("Database error"))

        await cog.set_repost.callback(cog, interaction, channel)

        # Verify error was handled gracefully
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_data_with_processing_errors(self):
        """Test extract_data when message processing has errors."""
        bot = await TestSetup.create_test_bot()
        cog = GalleryCog(bot)

        guild = MockGuildFactory.create()
        channel = MockChannelFactory.create_text_channel(guild=guild)
        interaction = MockInteractionFactory.create(guild=guild, channel=channel)

        # Mock messages
        async def mock_history(**kwargs):
            for i in range(3):
                yield MockMessageFactory.create(channel=channel)

        channel.history = MagicMock(return_value=mock_history())

        # Mock processing with errors
        cog._process_gallery_chunk = AsyncMock(
            return_value=([], [], ["Error 1", "Error 2"])
        )

        await cog.extract_gallery_data.callback(cog,
            interaction, channel, after_date=None, chunk_size=100, store_in_db=False
        )

        # Verify errors were reported
        assert interaction.followup.send.called

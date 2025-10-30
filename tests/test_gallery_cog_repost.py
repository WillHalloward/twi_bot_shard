"""
Unit tests for Gallery Cog repost functionality.

This module tests the repost detection and management system in the GalleryCog,
including RepostModal, RepostMenu UI components, and cache management.

Note: Full repost workflow tests are limited due to UI interaction requirements.
Focus is on testing component initialization and core logic.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord

# Import the cog to test
from cogs.gallery import GalleryCog, RepostMenu, RepostModal

# Import test utilities
from tests.mock_factories import MockInteractionFactory, MockMessageFactory, MockChannelFactory, MockUserFactory
from tests.test_utils import TestSetup, TestTeardown


class TestRepostModal:
    """Tests for RepostModal UI component."""

    @pytest.mark.asyncio
    async def test_repost_modal_initialization(self):
        """Test that RepostModal initializes correctly."""
        mention = "@testuser"
        jump_url = "https://discord.com/channels/123/456/789"
        title = "Test Title"

        modal = RepostModal(mention, jump_url, title)

        assert modal is not None
        assert modal.title_item is not None
        assert modal.description_item is not None
        assert title in modal.title_item.default

    @pytest.mark.asyncio
    async def test_repost_modal_with_extra_description(self):
        """Test RepostModal with extra description."""
        mention = "@testuser"
        jump_url = "https://discord.com/channels/123/456/789"
        title = "Test Title"
        extra = "Extra info"

        modal = RepostModal(mention, jump_url, title, extra_description=extra)

        assert modal.extra_description == extra
        assert extra in modal.description_item.default

    @pytest.mark.asyncio
    async def test_repost_modal_on_submit(self):
        """Test RepostModal submission."""
        mention = "@testuser"
        jump_url = "https://discord.com/channels/123/456/789"
        title = "Test Title"

        modal = RepostModal(mention, jump_url, title)

        # Mock interaction
        interaction = MockInteractionFactory.create()

        # Call on_submit
        await modal.on_submit(interaction)

        # Verify defer was called
        interaction.response.defer.assert_called_once()


class TestRepostMenu:
    """Tests for RepostMenu UI component."""

    @pytest.mark.asyncio
    async def test_repost_menu_initialization(self):
        """Test that RepostMenu initializes correctly."""
        mention = "@testuser"
        jump_url = "https://discord.com/channels/123/456/789"
        title = "Test Title"

        menu = RepostMenu(mention, jump_url, title)

        assert menu is not None
        assert menu.mention == mention
        assert menu.jump_url == jump_url
        assert menu.title == title
        assert menu.channel_select is not None
        assert menu.submit_button is not None
        assert menu.submit_button.disabled is True  # Initially disabled


class TestGalleryRepostCache:
    """Tests for gallery repost cache management."""

    @pytest.mark.asyncio
    async def test_repost_cache_initialization(self):
        """Test that repost cache exists and can be set."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the GalleryCog
        cog = GalleryCog(bot)

        # Verify repost_cache attribute exists (may be None initially)
        assert hasattr(cog, "repost_cache")

        # Initialize it as would happen during cog_load
        cog.repost_cache = []

        # Now verify it's a list
        assert isinstance(cog.repost_cache, list)

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_repost_cache_stores_data(self):
        """Test that repost cache can store channel data."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the GalleryCog
        cog = GalleryCog(bot)

        # Initialize cache
        cog.repost_cache = []

        # Add mock channel data
        channel_data = MagicMock()
        channel_data.guild_id = 123456789
        channel_data.channel_id = 999888777
        channel_data.channel_name = "gallery-test"
        cog.repost_cache.append(channel_data)

        # Verify data was added
        assert len(cog.repost_cache) == 1
        assert cog.repost_cache[0].channel_name == "gallery-test"

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestGalleryRepostValidation:
    """Tests for repost attachment validation."""

    @pytest.mark.asyncio
    async def test_repost_requires_attachments(self):
        """Test that repost fails gracefully with no attachments."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the GalleryCog
        cog = GalleryCog(bot)
        cog.repost_cache = []

        # Create message with no attachments
        message = MockMessageFactory.create()
        message.attachments = []

        # Mock interaction
        interaction = MockInteractionFactory.create()

        # Call repost_attachment
        await cog.repost_attachment(interaction, message)

        # Verify error message was sent
        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        response = str(args[0]) if args else str(kwargs.get("content", ""))
        assert "no attachments" in response.lower()

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_repost_requires_supported_content_type(self):
        """Test that repost validates content types."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the GalleryCog
        cog = GalleryCog(bot)
        cog.repost_cache = []

        # Create message with unsupported attachment (no content_type)
        message = MockMessageFactory.create()
        message.attachments = [
            MagicMock(
                url="https://example.com/file.xyz",
                filename="file.xyz",
                content_type=None  # Unsupported
            )
        ]

        # Mock interaction
        interaction = MockInteractionFactory.create()

        # Call repost_attachment
        await cog.repost_attachment(interaction, message)

        # Verify error message was sent
        interaction.response.send_message.assert_called_once()

        # Cleanup
        await TestTeardown.teardown_bot(bot)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main(["-v", __file__])

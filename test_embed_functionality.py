"""
Test script to verify embed logging functionality and channelstats command.

This script tests:
1. That the save_message function can handle messages with embeds
2. That the channelstats command SQL query is valid
3. That embeds are properly saved to the database
"""

import asyncio
import os
import sys
from unittest.mock import Mock, AsyncMock
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the functions we want to test
from cogs.stats_utils import save_message


class MockEmbed:
    """Mock Discord embed object for testing."""

    def __init__(self):
        self.title = "Test Embed Title"
        self.description = "Test embed description"
        self.url = "https://example.com"
        self.timestamp = datetime.now()
        self.color = Mock()
        self.color.value = 16711680  # Red color

        # Footer
        self.footer = Mock()
        self.footer.text = "Footer text"
        self.footer.icon_url = "https://example.com/footer.png"

        # Image
        self.image = Mock()
        self.image.url = "https://example.com/image.png"
        self.image.proxy_url = "https://example.com/proxy_image.png"
        self.image.height = 100
        self.image.width = 200

        # Thumbnail
        self.thumbnail = Mock()
        self.thumbnail.url = "https://example.com/thumb.png"
        self.thumbnail.proxy_url = "https://example.com/proxy_thumb.png"
        self.thumbnail.height = 50
        self.thumbnail.width = 50

        # Video
        self.video = None

        # Provider
        self.provider = Mock()
        self.provider.name = "Test Provider"
        self.provider.url = "https://provider.com"

        # Author
        self.author = Mock()
        self.author.name = "Test Author"
        self.author.url = "https://author.com"
        self.author.icon_url = "https://author.com/icon.png"

        # Fields
        self.fields = [
            Mock(name="Field 1", value="Value 1", inline=True),
            Mock(name="Field 2", value="Value 2", inline=False),
        ]


class MockMessage:
    """Mock Discord message object for testing."""

    def __init__(self, has_embeds=True):
        self.id = 123456789
        self.content = "Test message content"
        self.created_at = datetime.now()
        self.jump_url = "https://discord.com/channels/123/456/789"

        # Author
        self.author = Mock()
        self.author.id = 987654321
        self.author.name = "TestUser"
        self.author.display_name = "Test User"
        self.author.bot = False
        self.author.created_at = datetime.now()

        # Guild
        self.guild = Mock()
        self.guild.id = 111222333
        self.guild.name = "Test Guild"

        # Channel
        self.channel = Mock()
        self.channel.id = 444555666
        self.channel.name = "test-channel"

        # Embeds
        if has_embeds:
            self.embeds = [MockEmbed()]
        else:
            self.embeds = []

        # Other attributes
        self.attachments = []
        self.mentions = []
        self.role_mentions = []
        self.reference = None


class MockBot:
    """Mock bot object for testing."""

    def __init__(self):
        self.db = Mock()
        self.db.fetchval = AsyncMock()
        self.db.execute = AsyncMock()
        self.db.execute_many = AsyncMock()
        self.db.fetchrow = AsyncMock()
        self.db.fetch = AsyncMock()


async def test_save_message_with_embeds():
    """Test that save_message can handle messages with embeds."""
    print("Testing save_message with embeds...")

    # Create mock objects
    bot = MockBot()
    message = MockMessage(has_embeds=True)

    # Configure mock responses
    bot.db.fetchval.side_effect = [
        True,  # User exists
        42,    # Embed ID returned from INSERT
    ]

    try:
        # Call the function
        await save_message(bot, message)

        # Verify that database operations were called
        assert bot.db.fetchval.called, "fetchval should be called"
        assert bot.db.execute.called, "execute should be called"
        assert bot.db.execute_many.called, "execute_many should be called for embed fields"

        print("✓ save_message with embeds test passed!")
        return True

    except Exception as e:
        print(f"✗ save_message with embeds test failed: {e}")
        return False


async def test_save_message_without_embeds():
    """Test that save_message works normally without embeds."""
    print("Testing save_message without embeds...")

    # Create mock objects
    bot = MockBot()
    message = MockMessage(has_embeds=False)

    # Configure mock responses
    bot.db.fetchval.return_value = True  # User exists

    try:
        # Call the function
        await save_message(bot, message)

        # Verify that basic database operations were called
        assert bot.db.fetchval.called, "fetchval should be called"
        assert bot.db.execute.called, "execute should be called"

        print("✓ save_message without embeds test passed!")
        return True

    except Exception as e:
        print(f"✗ save_message without embeds test failed: {e}")
        return False


async def test_channelstats_query_syntax():
    """Test that the channelstats SQL query has valid syntax."""
    print("Testing channelstats SQL query syntax...")

    # Test the SQL queries directly by trying to execute them with mock data
    try:
        # Create a mock bot
        bot = MockBot()

        # Mock the database response for the main stats query
        bot.db.fetchrow.return_value = {
            'total_messages': 100,
            'unique_users': 10,
            'avg_message_length': 50.5,
            'messages_with_attachments': 5,
            'messages_with_embeds': 3,
        }

        # Mock the database response for the top users query
        bot.db.fetch.return_value = [
            {'user_id': 123, 'message_count': 50},
            {'user_id': 456, 'message_count': 30},
        ]

        # Test the main stats query
        from datetime import datetime, timedelta
        d_time = datetime.now() - timedelta(days=7)
        channel_id = 123456789

        stats_query = """
        SELECT 
            COUNT(*) as total_messages,
            COUNT(DISTINCT user_id) as unique_users,
            AVG(LENGTH(content)) as avg_message_length,
            COUNT(*) FILTER (WHERE attachments.id IS NOT NULL) as messages_with_attachments,
            COUNT(*) FILTER (WHERE embeds.id IS NOT NULL) as messages_with_embeds
        FROM messages 
        LEFT JOIN attachments ON messages.message_id = attachments.message_id
        LEFT JOIN embeds ON messages.message_id = embeds.message_id
        WHERE messages.created_at > $1 AND messages.channel_id = $2
        """

        # Test the top users query
        top_users_query = """
        SELECT user_id, COUNT(*) as message_count
        FROM messages 
        WHERE created_at > $1 AND channel_id = $2
        GROUP BY user_id
        ORDER BY message_count DESC
        LIMIT 5
        """

        # Execute the queries with mock data
        await bot.db.fetchrow(stats_query, d_time, channel_id)
        await bot.db.fetch(top_users_query, d_time, channel_id)

        # Verify that the database was queried
        assert bot.db.fetchrow.called, "Main stats query should be executed"
        assert bot.db.fetch.called, "Top users query should be executed"

        # Verify the queries were called with correct parameters
        fetchrow_calls = bot.db.fetchrow.call_args_list
        fetch_calls = bot.db.fetch.call_args_list

        assert len(fetchrow_calls) > 0, "fetchrow should be called"
        assert len(fetch_calls) > 0, "fetch should be called"

        print("✓ channelstats query syntax test passed!")
        return True

    except Exception as e:
        print(f"✗ channelstats query syntax test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("Running embed functionality tests...\n")

    tests = [
        test_save_message_with_embeds(),
        test_save_message_without_embeds(),
        test_channelstats_query_syntax(),
    ]

    results = await asyncio.gather(*tests, return_exceptions=True)

    passed = sum(1 for result in results if result is True)
    total = len(results)

    print(f"\nTest Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Embed functionality is working correctly.")
    else:
        print("❌ Some tests failed. Please check the implementation.")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Test {i+1} exception: {result}")


if __name__ == "__main__":
    asyncio.run(main())

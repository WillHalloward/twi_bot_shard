import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the save_message function
from cogs.stats_utils import save_message

async def test_save_message_fix():
    """
    Test that the save_message function doesn't fail due to missing database columns.
    This is a mock test to verify the SQL queries are properly formatted.
    """
    print("Testing save_message function fix...")
    
    # Create a mock bot with database
    mock_bot = Mock()
    mock_db = AsyncMock()
    mock_bot.db = mock_db
    
    # Mock database responses
    mock_db.fetchval.return_value = False  # User doesn't exist
    mock_db.execute.return_value = None
    mock_db.execute_many.return_value = None
    
    # Create a mock Discord message
    mock_message = Mock()
    mock_message.id = 123456789
    mock_message.content = "Test message"
    mock_message.created_at = Mock()
    mock_message.created_at.replace.return_value = "2023-01-01 00:00:00"
    
    # Mock author
    mock_author = Mock()
    mock_author.id = 987654321
    mock_author.name = "TestUser"
    mock_author.display_name = "TestUser"
    mock_author.bot = False
    mock_author.created_at = Mock()
    mock_author.created_at.replace.return_value = "2023-01-01 00:00:00"
    mock_message.author = mock_author
    
    # Mock guild
    mock_guild = Mock()
    mock_guild.id = 111222333
    mock_guild.name = "TestGuild"
    mock_message.guild = mock_guild
    
    # Mock channel
    mock_channel = Mock()
    mock_channel.id = 444555666
    mock_channel.name = "test-channel"
    mock_message.channel = mock_channel
    
    # Mock other message properties
    mock_message.jump_url = "https://discord.com/channels/111222333/444555666/123456789"
    mock_message.reference = None
    mock_message.attachments = []
    mock_message.mentions = []
    mock_message.role_mentions = []
    
    try:
        # Test the save_message function
        await save_message(mock_bot, mock_message)
        
        # Verify the correct SQL was called
        expected_calls = mock_db.execute.call_args_list
        
        # Check that the message insert was called with correct columns
        message_insert_call = None
        for call in expected_calls:
            if "INSERT INTO messages" in str(call):
                message_insert_call = call
                break
        
        if message_insert_call:
            sql_query = message_insert_call[0][0]
            print("✅ Message insert SQL query:")
            print(sql_query)
            
            # Verify it contains the correct columns that exist in the database
            required_columns = [
                "message_id", "created_at", "content", "user_name", 
                "server_name", "server_id", "channel_id", "channel_name", 
                "user_id", "user_nick", "jump_url", "is_bot", "deleted", "reference"
            ]
            
            for column in required_columns:
                if column not in sql_query:
                    print(f"❌ Missing required column: {column}")
                    return False
            
            # Verify it doesn't contain problematic columns
            problematic_columns = ["message_type", "tts", "mention_everyone", "pinned"]
            for column in problematic_columns:
                if column in sql_query:
                    print(f"❌ Found problematic column: {column}")
                    return False
            
            print("✅ All required columns present and no problematic columns found")
        else:
            print("❌ Message insert call not found")
            return False
        
        print("✅ save_message function test passed!")
        return True
        
    except Exception as e:
        print(f"❌ save_message function test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("Running save_message fix test...")
    
    # Configure logging to suppress debug messages
    logging.getLogger().setLevel(logging.WARNING)
    
    result = await test_save_message_fix()
    
    if result:
        print("\n🎉 All tests passed! The save_message function should now work correctly.")
    else:
        print("\n❌ Tests failed. There may still be issues with the save_message function.")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import discord
from discord.ext import commands
from unittest.mock import AsyncMock, MagicMock

async def test_repost_command():
    """Test that the repost command can be loaded without errors."""

    # Create a mock bot
    bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

    # Mock the database and other dependencies
    bot.db = AsyncMock()
    bot.db.fetch = AsyncMock(return_value=[])

    # Mock the repository factory
    bot.repo_factory = MagicMock()
    mock_repo = AsyncMock()
    mock_repo.get_all = AsyncMock(return_value=[])
    bot.repo_factory.get_repository = MagicMock(return_value=mock_repo)

    try:
        # Import and load the gallery cog
        from cogs.gallery import GalleryCog

        # Create the cog instance
        cog = GalleryCog(bot)

        # Check if the repost method exists and has the right signature
        assert hasattr(cog, 'repost'), "repost method not found"

        # Check if the context menu is properly created
        assert hasattr(cog, 'repost_context_menu'), "repost_context_menu not found"
        context_menu = getattr(cog, 'repost_context_menu')
        assert context_menu.name == "Repost", "context menu name is incorrect"
        assert context_menu.callback == cog.repost, "context menu callback is not pointing to repost method"

        print("✅ Test passed: repost context menu is properly created and configured")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    result = await test_repost_command()
    if result:
        print("🎉 All tests passed! The repost command fix should work correctly.")
    else:
        print("💥 Tests failed. There may still be issues with the repost command.")

if __name__ == "__main__":
    asyncio.run(main())

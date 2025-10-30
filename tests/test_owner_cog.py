"""
Unit tests for the OwnerCog class in cogs/owner.py.

This module contains comprehensive tests for the OwnerCog class, which provides
owner-only administrative commands for bot management, cog loading, SQL execution,
resource monitoring, and system commands.

Note: These tests focus on the command logic. Error handling is tested separately.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord

# Import the cog to test
from cogs.owner import OwnerCog

# Import test utilities
from tests.mock_factories import MockInteractionFactory
from tests.test_utils import TestSetup, TestTeardown


class TestOwnerCogLoad:
    """Tests for the /admin load command."""

    @pytest.mark.asyncio
    async def test_load_cog_success(self):
        """Test successfully loading a cog."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock load_extension
        bot.load_extension = AsyncMock()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock bot.extensions as empty dict (cog not loaded)
        with patch.object(type(bot), 'extensions', new_callable=PropertyMock, return_value={}):
            # Call the command using callback pattern for grouped commands
            await cog.load_cog.callback(cog, interaction, cog="cogs.test")

            # Verify load_extension was called
            bot.load_extension.assert_called_once_with("cogs.test")

            # Verify response was sent
            assert interaction.response.defer.called or interaction.followup.send.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_load_cog_already_loaded(self):
        """Test loading a cog that's already loaded."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock load_extension
        bot.load_extension = AsyncMock()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock bot.extensions with cog already loaded
        with patch.object(type(bot), 'extensions', new_callable=PropertyMock, return_value={"cogs.test": MagicMock()}):
            # Call the command using callback pattern
            await cog.load_cog.callback(cog, interaction, cog="cogs.test")

            # Verify load_extension was NOT called
            bot.load_extension.assert_not_called()

            # Verify warning message was sent
            if interaction.followup.send.called:
                args, kwargs = interaction.followup.send.call_args
                response = str(args[0]) if args else str(kwargs.get("content", ""))
                assert "already" in response.lower()

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_load_cog_validation(self):
        """Test load validation - empty cog name should send error message."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock bot.extensions
        with patch.object(type(bot), 'extensions', new_callable=PropertyMock, return_value={}):
            # Call with empty string - error handler will catch it
            await cog.load_cog.callback(cog, interaction, cog="")

            # Verify response was sent (error handled gracefully)
            assert interaction.response.defer.called or interaction.followup.send.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogUnload:
    """Tests for the /admin unload command."""

    @pytest.mark.asyncio
    async def test_unload_cog_success(self):
        """Test successfully unloading a cog."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock unload_extension
        bot.unload_extension = AsyncMock()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock bot.extensions with cog loaded
        with patch.object(type(bot), 'extensions', new_callable=PropertyMock, return_value={"cogs.test": MagicMock()}):
            # Call the command using callback pattern
            await cog.unload_cog.callback(cog, interaction, cog="cogs.test")

            # Verify unload_extension was called
            bot.unload_extension.assert_called_once_with("cogs.test")

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_unload_cog_not_loaded(self):
        """Test unloading a cog that's not loaded."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock unload_extension
        bot.unload_extension = AsyncMock()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock bot.extensions as empty
        with patch.object(type(bot), 'extensions', new_callable=PropertyMock, return_value={}):
            # Call the command using callback pattern
            await cog.unload_cog.callback(cog, interaction, cog="cogs.test")

            # Verify unload_extension was NOT called
            bot.unload_extension.assert_not_called()

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_unload_cannot_unload_owner(self):
        """Test that owner cog cannot unload itself."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock unload_extension
        bot.unload_extension = AsyncMock()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock bot.extensions with owner cog loaded
        with patch.object(type(bot), 'extensions', new_callable=PropertyMock, return_value={"cogs.owner": MagicMock()}):
            # Call the command using callback pattern
            await cog.unload_cog.callback(cog, interaction, cog="cogs.owner")

            # Verify unload_extension was NOT called
            bot.unload_extension.assert_not_called()

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogReload:
    """Tests for the /admin reload command."""

    @pytest.mark.asyncio
    async def test_reload_cog_success(self):
        """Test successfully reloading a cog."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock unload_extension and load_extension (reload does both)
        bot.unload_extension = AsyncMock()
        bot.load_extension = AsyncMock()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock bot.extensions with cog loaded
        with patch.object(type(bot), 'extensions', new_callable=PropertyMock, return_value={"cogs.test": MagicMock()}):
            # Call the command using callback pattern
            await cog.reload_cog.callback(cog, interaction, cog="cogs.test")

            # Verify unload and load were called (reload does both)
            bot.unload_extension.assert_called_once_with("cogs.test")
            bot.load_extension.assert_called_once_with("cogs.test")

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogCmd:
    """Tests for the /admin cmd command (shell execution)."""

    @pytest.mark.asyncio
    async def test_cmd_execution(self):
        """Test executing a shell command."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Test output",
                stderr=""
            )

            # Call the command using callback pattern
            await cog.cmd.callback(cog, interaction, args="echo test")

            # Verify subprocess was called
            assert mock_run.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogSync:
    """Tests for the /admin sync command."""

    @pytest.mark.asyncio
    async def test_sync_command(self):
        """Test syncing commands."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock tree.sync
        bot.tree.sync = AsyncMock(return_value=[])

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()
        interaction.guild = MagicMock()
        interaction.guild.id = 123456789

        # Call the command using callback pattern
        await cog.sync.callback(cog, interaction, all_guilds=False)

        # Verify tree.sync was called
        assert bot.tree.sync.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogExit:
    """Tests for the /admin exit command."""

    @pytest.mark.asyncio
    async def test_exit_command(self):
        """Test bot exit command."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock close
        bot.close = AsyncMock()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Call the command using callback pattern
        await cog.exit.callback(cog, interaction)

        # Verify close was called
        bot.close.assert_called_once()


class TestOwnerCogResources:
    """Tests for the /admin resources command."""

    @pytest.mark.asyncio
    async def test_resources_command(self):
        """Test resource monitoring command."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock resource_monitor on bot
        bot.resource_monitor = MagicMock()
        bot.resource_monitor.get_resource_stats.return_value = {
            "memory_mb": 100,
            "cpu_percent": 5.0,
            "uptime": 3600
        }
        bot.resource_monitor.get_summary_stats.return_value = {
            "avg_memory_mb": 95,
            "peak_memory_mb": 120,
            "avg_cpu_percent": 4.5
        }

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Call the command using callback pattern
        await cog.resources.callback(cog, interaction, detail_level="basic")

        # Verify resource_monitor was called
        bot.resource_monitor.get_resource_stats.assert_called_once()

        # Verify response sent
        assert interaction.response.defer.called or interaction.followup.send.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogSQL:
    """Tests for the /admin sql command."""

    @pytest.mark.asyncio
    async def test_sql_select_query(self):
        """Test executing a SELECT query."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock database fetch
        bot.db.fetch = AsyncMock(return_value=[
            {"id": 1, "name": "test1"},
            {"id": 2, "name": "test2"}
        ])

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Call the command using callback pattern (note: method name is sql_query, not sql)
        await cog.sql_query.callback(cog, interaction, query="SELECT * FROM test", allow_modifications=False)

        # Verify database fetch was called
        bot.db.fetch.assert_called_once()

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogAskDB:
    """Tests for the /admin ask_db command."""

    @pytest.mark.asyncio
    async def test_ask_db_basic(self):
        """Test asking database a natural language question."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock database fetch
        bot.db.fetch = AsyncMock(return_value=[{"count": 100}])

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock the FAISS query functions
        with patch("cogs.owner.query_faiss") as mock_query, \
             patch("cogs.owner.build_prompt") as mock_prompt, \
             patch("cogs.owner.generate_sql") as mock_generate, \
             patch("cogs.owner.extract_sql_from_response") as mock_extract:

            # Set up mocks
            mock_query.return_value = ["table: users", "column: id"]
            mock_prompt.return_value = "Generate SQL"
            mock_generate.return_value = "SQL response"
            mock_extract.return_value = "SELECT COUNT(*) FROM users"

            # Call the command using callback pattern (note: method name is ask_database)
            await cog.ask_database.callback(cog, interaction, question="how many users")

            # Verify some processing happened
            assert mock_query.called or mock_extract.called or interaction.response.defer.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main(["-v", __file__])

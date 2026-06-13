"""
Unit tests for the OwnerCog class in cogs/owner.py.

This module contains comprehensive tests for the OwnerCog class, which provides
owner-only administrative commands for bot management, cog loading, SQL execution,
resource monitoring, and system commands.

Note: These tests focus on the command logic. Error handling is tested separately.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components

# Import the cog to test.
# Keep a reference to the module object itself: earlier tests' teardown can
# unload the "cogs.owner" extension (which removes it from sys.modules), after
# which patch("cogs.owner.<name>") would patch a freshly re-imported module
# instead of the one OwnerCog (imported here) actually closes over.
import cogs.owner as owner_module
from cogs.owner import OwnerCog, validate_read_only_sql

# Import test utilities
from tests.mock_factories import MockInteractionFactory
from tests.test_utils import TestSetup, TestTeardown
from utils.exceptions import ValidationError


class TestOwnerCogLoad:
    """Tests for the /admin load command."""

    @pytest.mark.asyncio
    async def test_load_cog_success(self) -> None:
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
        with patch.object(
            type(bot), "extensions", new_callable=PropertyMock, return_value={}
        ):
            # Call the command using callback pattern for grouped commands
            await cog.load_cog.callback(cog, interaction, cog="cogs.test")

            # Verify load_extension was called
            bot.load_extension.assert_called_once_with("cogs.test")

            # Verify response was sent
            assert interaction.response.defer.called or interaction.followup.send.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_load_cog_already_loaded(self) -> None:
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
        with patch.object(
            type(bot),
            "extensions",
            new_callable=PropertyMock,
            return_value={"cogs.test": MagicMock()},
        ):
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
    async def test_load_cog_validation(self) -> None:
        """Test load validation - empty cog name should send error message."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock bot.extensions
        with patch.object(
            type(bot), "extensions", new_callable=PropertyMock, return_value={}
        ):
            # Call with empty string - error handler will catch it
            await cog.load_cog.callback(cog, interaction, cog="")

            # Verify response was sent (error handled gracefully)
            assert interaction.response.defer.called or interaction.followup.send.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogUnload:
    """Tests for the /admin unload command."""

    @pytest.mark.asyncio
    async def test_unload_cog_success(self) -> None:
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
        with patch.object(
            type(bot),
            "extensions",
            new_callable=PropertyMock,
            return_value={"cogs.test": MagicMock()},
        ):
            # Call the command using callback pattern
            await cog.unload_cog.callback(cog, interaction, cog="cogs.test")

            # Verify unload_extension was called
            bot.unload_extension.assert_called_once_with("cogs.test")

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_unload_cog_not_loaded(self) -> None:
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
        with patch.object(
            type(bot), "extensions", new_callable=PropertyMock, return_value={}
        ):
            # Call the command using callback pattern
            await cog.unload_cog.callback(cog, interaction, cog="cogs.test")

            # Verify unload_extension was NOT called
            bot.unload_extension.assert_not_called()

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_unload_cannot_unload_owner(self) -> None:
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
        with patch.object(
            type(bot),
            "extensions",
            new_callable=PropertyMock,
            return_value={"cogs.owner": MagicMock()},
        ):
            # Call the command using callback pattern
            await cog.unload_cog.callback(cog, interaction, cog="cogs.owner")

            # Verify unload_extension was NOT called
            bot.unload_extension.assert_not_called()

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogReload:
    """Tests for the /admin reload command."""

    @pytest.mark.asyncio
    async def test_reload_cog_success(self) -> None:
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
        with patch.object(
            type(bot),
            "extensions",
            new_callable=PropertyMock,
            return_value={"cogs.test": MagicMock()},
        ):
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
    async def test_cmd_execution(self) -> None:
        """Test executing a shell command."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock asyncio's subprocess (the command runs the child process via
        # asyncio.create_subprocess_exec so it never blocks the event loop)
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"Test output", b""))
        mock_process.returncode = 0
        with patch(
            "asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)
        ) as mock_exec:
            # Call the command using callback pattern
            await cog.cmd.callback(cog, interaction, args="echo test")

            # Verify subprocess was called
            assert mock_exec.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogSync:
    """Tests for the /admin sync command."""

    @pytest.mark.asyncio
    async def test_sync_command(self) -> None:
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
    async def test_exit_command(self) -> None:
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
    async def test_resources_command(self) -> None:
        """Test resource monitoring command."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock resource_monitor on bot (the command awaits the async wrapper
        # so the psutil collection runs off the event loop)
        bot.resource_monitor = MagicMock()
        bot.resource_monitor.get_resource_stats_async = AsyncMock(
            return_value={
                "memory_mb": 100,
                "cpu_percent": 5.0,
                "uptime": 3600,
            }
        )
        bot.resource_monitor.get_summary_stats.return_value = {
            "avg_memory_mb": 95,
            "peak_memory_mb": 120,
            "avg_cpu_percent": 4.5,
        }

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Call the command using callback pattern
        await cog.resources.callback(cog, interaction, detail_level="basic")

        # Verify resource_monitor was called
        bot.resource_monitor.get_resource_stats_async.assert_awaited_once()

        # Verify response sent
        assert interaction.response.defer.called or interaction.followup.send.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogSQL:
    """Tests for the /admin sql command."""

    @pytest.mark.asyncio
    async def test_sql_select_query(self) -> None:
        """Test executing a SELECT query."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock database fetch
        bot.db.fetch = AsyncMock(
            return_value=[{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]
        )

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Call the command using callback pattern (note: method name is sql_query, not sql)
        await cog.sql_query.callback(
            cog, interaction, query="SELECT * FROM test", allow_modifications=False
        )

        # Verify database fetch was called
        bot.db.fetch.assert_called_once()

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestOwnerCogAskDB:
    """Tests for the /admin ask_db command."""

    @pytest.mark.asyncio
    async def test_ask_db_basic(self) -> None:
        """Test asking database a natural language question."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Mock database fetch
        bot.db.fetch = AsyncMock(return_value=[{"count": 100}])

        # Create the OwnerCog
        cog = await TestSetup.setup_cog(bot, OwnerCog)

        # Create a mock interaction
        interaction = MockInteractionFactory.create()

        # Mock the schema search functions
        with (
            patch("cogs.owner.search_schema") as mock_search,
            patch("cogs.owner.generate_sql") as mock_generate,
            patch("cogs.owner.extract_sql_from_response") as mock_extract,
        ):
            # Set up mocks - search_schema is async
            mock_search.return_value = [{"table_name": "users", "column_name": "id"}]
            mock_generate.return_value = "SQL response"
            mock_extract.return_value = "SELECT COUNT(*) FROM users"

            # Call the command using callback pattern (note: method name is ask_database)
            await cog.ask_database.callback(cog, interaction, question="how many users")

            # Verify some processing happened
            assert (
                mock_search.called
                or mock_extract.called
                or interaction.response.defer.called
            )

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_ask_db_blocks_non_read_only_sql(self) -> None:
        """Generated non-SELECT SQL must be rejected before reaching the DB."""
        bot = await TestSetup.create_test_bot()
        bot.db.fetch = AsyncMock(return_value=[])

        cog = await TestSetup.setup_cog(bot, OwnerCog)
        interaction = MockInteractionFactory.create()

        with (
            patch.object(
                owner_module,
                "check_schema_embeddings_exist",
                AsyncMock(return_value=True),
            ),
            patch.object(
                owner_module,
                "search_schema",
                AsyncMock(return_value=[{"table_name": "users"}]),
            ),
            patch.object(
                owner_module, "generate_sql", AsyncMock(return_value="SQL response")
            ),
            patch.object(owner_module, "extract_sql_from_response") as mock_extract,
        ):
            mock_extract.return_value = "DROP TABLE users"

            await cog.ask_database.callback(
                cog, interaction, question="drop the users table"
            )

            # The dangerous query must never be executed
            bot.db.fetch.assert_not_called()
            # The user is told via an ephemeral followup
            assert any(
                call.kwargs.get("ephemeral") is True
                for call in interaction.followup.send.call_args_list
            )

        await TestTeardown.teardown_bot(bot)


class TestReadOnlySqlGuard:
    """Unit tests for the validate_read_only_sql helper (audit F2c)."""

    def test_accepts_plain_select(self) -> None:
        """A plain SELECT (with trailing semicolon) passes and is returned stripped."""
        assert (
            validate_read_only_sql("SELECT id, content FROM messages LIMIT 10;")
            == "SELECT id, content FROM messages LIMIT 10"
        )

    def test_accepts_read_only_cte(self) -> None:
        """A CTE without write keywords is allowed."""
        query = "WITH recent AS (SELECT * FROM messages) SELECT count(*) FROM recent"
        assert validate_read_only_sql(query) == query

    def test_rejects_update(self) -> None:
        """A first-word write statement is rejected."""
        with pytest.raises(ValidationError):
            validate_read_only_sql("UPDATE messages SET deleted = TRUE")

    def test_rejects_multi_statement(self) -> None:
        """A second statement hidden after a semicolon is rejected."""
        with pytest.raises(ValidationError):
            validate_read_only_sql("SELECT 1; DROP TABLE messages")

    def test_rejects_writable_cte(self) -> None:
        """A data-modifying CTE (first word WITH) is rejected."""
        with pytest.raises(ValidationError):
            validate_read_only_sql(
                "WITH doomed AS (DELETE FROM messages RETURNING id) "
                "SELECT count(*) FROM doomed"
            )

    def test_rejects_dangerous_function(self) -> None:
        """The regex blocklist (pg_sleep) still applies to SELECTs."""
        with pytest.raises(ValidationError):
            validate_read_only_sql("SELECT pg_sleep(60)")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main(["-v", __file__])


class TestAdminCommandGating:
    """Verify the owner-only vs moderator-OK split on /admin commands.

    Owner-only: cmd, sql, ask_db, exit (dangerous: host shell, arbitrary SQL,
    shutdown). Moderator-OK: load, loadall, unload, reload, sync, resources.
    The split was a deliberate policy decision (2026-06-13): keep destructive
    surfaces owner-locked while letting the trusted mod team run operational
    commands. Discord's per-guild Integration override is a separate, additional
    layer — these tests assert the in-code gate, which must hold regardless of
    server config.
    """

    OWNER_ONLY = {"cmd", "sql", "ask_db", "exit"}
    MOD_OK = {"load", "loadall", "unload", "reload", "sync", "resources"}

    # command-name -> OwnerCog method name (the @admin.command() Command objects
    # are stored as class attributes; reading checks off the captured OwnerCog
    # class is immune to the shared `admin` group being re-decorated by other
    # tests' cog reloads under the conftest sys.modules purge).
    _METHOD = {
        "cmd": "cmd",
        "sql": "sql_query",
        "ask_db": "ask_database",
        "exit": "exit",
        "load": "load_cog",
        "loadall": "load_all_cogs",
        "unload": "unload_cog",
        "reload": "reload_cog",
        "sync": "sync",
        "resources": "resources",
    }

    def _check_names(self, cmd_name: str) -> set[str]:
        cmd = OwnerCog.__dict__[self._METHOD[cmd_name]]
        return {getattr(f, "__name__", "") for f in cmd.checks}

    @pytest.mark.asyncio
    async def test_owner_only_commands_use_owner_check(self) -> None:
        for name in self.OWNER_ONLY:
            names = self._check_names(name)
            assert "_is_bot_owner" in names, (
                f"/admin {name} must be owner-only; has {names}"
            )
            assert "app_moderator_check" not in names, (
                f"/admin {name} must NOT be moderator-OK; has {names}"
            )

    @pytest.mark.asyncio
    async def test_mod_ok_commands_use_moderator_check(self) -> None:
        for name in self.MOD_OK:
            names = self._check_names(name)
            assert "app_moderator_check" in names, (
                f"/admin {name} must be moderator-OK; has {names}"
            )
            assert "_is_bot_owner" not in names, (
                f"/admin {name} should not also be owner-only; has {names}"
            )

    @pytest.mark.asyncio
    async def test_is_moderator_decision_logic(self) -> None:
        """is_moderator: owner True, ban_members mod True, plain user False."""
        import config
        from utils.permissions import is_moderator

        owner_id = config.bot_owner_id or 111

        class Perms:
            def __init__(self, ban: bool) -> None:
                self.ban_members = ban
                self.administrator = False

        class Member:
            def __init__(self, uid: int, ban: bool) -> None:
                self.id = uid
                self.guild_permissions = Perms(ban)
                self.roles: list[object] = []

        members = {
            owner_id: Member(owner_id, False),
            222: Member(222, True),
            333: Member(333, False),
        }

        class Guild:
            id = 999

            def get_member(self, uid: int) -> object:
                return members.get(uid)

        class Bot:
            def get_guild(self, gid: int) -> object:
                return Guild()

        bot = Bot()
        with patch(
            "utils.permissions.is_bot_owner", side_effect=lambda uid: uid == owner_id
        ):
            assert await is_moderator(bot, 999, owner_id) is True
            assert await is_moderator(bot, 999, 222) is True  # ban_members mod
            assert await is_moderator(bot, 999, 333) is False  # plain user

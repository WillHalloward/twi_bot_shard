"""
Unit tests for command groups integration.

This module tests the command group system that organizes bot commands under
parent groups (/admin, /mod, /gallery_admin). These groups allow multiple cogs
to share common command namespaces for better organization.
"""

import os
import sys

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components
import discord
from discord import app_commands
from discord.ext import commands

import cogs.gallery  # noqa: F401 - adds commands to gallery_admin group
import cogs.mods  # noqa: F401 - adds commands to mod group
import cogs.other  # noqa: F401 - adds commands to admin group

# Force import cogs to populate command groups with their commands
# This ensures the groups have their expected commands before tests run
# pylint: disable=unused-import
import cogs.owner  # noqa: F401 - adds commands to admin group

# Import test utilities
from tests.test_utils import TestSetup

# Import command groups
from utils.command_groups import admin, gallery_admin, mod


@pytest.fixture
def reset_command_groups():
    """Reset command groups before and after tests to prevent pollution.

    This fixture clears all commands from the groups before the test
    and after the test to ensure test isolation.
    """
    # Store original commands
    original_admin = list(admin.commands)
    original_mod = list(mod.commands)
    original_gallery_admin = list(gallery_admin.commands)

    yield

    # Clear all commands added during the test
    for cmd in list(admin.commands):
        if cmd not in original_admin:
            admin.remove_command(cmd.name)

    for cmd in list(mod.commands):
        if cmd not in original_mod:
            mod.remove_command(cmd.name)

    for cmd in list(gallery_admin.commands):
        if cmd not in original_gallery_admin:
            gallery_admin.remove_command(cmd.name)


class TestCommandGroupDefinitions:
    """Tests for command group definitions and structure."""

    def test_admin_group_exists(self):
        """Test that admin group is properly defined."""
        assert admin is not None
        assert isinstance(admin, app_commands.Group)
        assert admin.name == "admin"
        assert (
            "owner" in admin.description.lower()
            or "administration" in admin.description.lower()
        )

    def test_mod_group_exists(self):
        """Test that mod group is properly defined."""
        assert mod is not None
        assert isinstance(mod, app_commands.Group)
        assert mod.name == "mod"
        assert (
            "moderation" in mod.description.lower()
            or "server" in mod.description.lower()
        )

    def test_gallery_admin_group_exists(self):
        """Test that gallery_admin group is properly defined."""
        assert gallery_admin is not None
        assert isinstance(gallery_admin, app_commands.Group)
        assert gallery_admin.name == "gallery_admin"
        assert "gallery" in gallery_admin.description.lower()

    def test_groups_are_distinct(self):
        """Test that each group is a separate object."""
        assert admin is not mod
        assert admin is not gallery_admin
        assert mod is not gallery_admin


class TestCommandGroupRegistration:
    """Tests for command group registration with the bot."""

    @pytest.mark.asyncio
    async def test_groups_can_be_registered_to_tree(self):
        """Test that groups can be added to command tree."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Store initial command count
        initial_commands = len(bot.tree.get_commands())

        # Register groups
        bot.tree.add_command(admin)
        bot.tree.add_command(mod)
        bot.tree.add_command(gallery_admin)

        # Verify groups were added
        final_commands = len(bot.tree.get_commands())
        assert final_commands >= initial_commands + 3

        # Verify we can retrieve the groups
        commands_dict = {cmd.name: cmd for cmd in bot.tree.get_commands()}
        assert "admin" in commands_dict
        assert "mod" in commands_dict
        assert "gallery_admin" in commands_dict

        # Cleanup
        bot.tree.remove_command("admin")
        bot.tree.remove_command("mod")
        bot.tree.remove_command("gallery_admin")
        await bot.close()

    @pytest.mark.asyncio
    async def test_groups_registered_before_cogs(self):
        """Test that groups are registered before cog loading (as in main.py)."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Register groups first (simulating main.py setup_hook)
        bot.tree.add_command(admin)
        bot.tree.add_command(mod)
        bot.tree.add_command(gallery_admin)

        # Verify groups are in tree before any cogs are loaded
        commands_dict = {cmd.name: cmd for cmd in bot.tree.get_commands()}
        assert "admin" in commands_dict
        assert "mod" in commands_dict
        assert "gallery_admin" in commands_dict

        # Now we can load cogs that use these groups
        # (In actual bot, cogs would add commands to these groups)

        # Cleanup
        bot.tree.remove_command("admin")
        bot.tree.remove_command("mod")
        bot.tree.remove_command("gallery_admin")
        await bot.close()


@pytest.mark.usefixtures("reset_command_groups")
class TestCommandGroupUsage:
    """Tests for using command groups in cogs."""

    @pytest.mark.asyncio
    async def test_commands_can_be_added_to_admin_group(self):
        """Test that commands can be added to admin group."""

        # Create a simple test cog with a command in admin group
        class TestCog(commands.Cog):
            def __init__(self, bot):
                self.bot = bot

            @admin.command(name="test_cmd", description="Test command in admin group")
            async def test_command(self, interaction: discord.Interaction):
                """Test command."""
                await interaction.response.send_message("Test response")

        # Create bot and register group
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(admin)

        # Load the test cog
        test_cog = TestCog(bot)
        await bot.add_cog(test_cog)

        # Verify the command exists in the admin group
        admin_group = bot.tree.get_command("admin")
        assert admin_group is not None
        assert isinstance(admin_group, app_commands.Group)

        # Get commands from the group
        group_commands = admin_group.commands
        command_names = [cmd.name for cmd in group_commands]
        assert "test_cmd" in command_names

        # Cleanup
        await bot.remove_cog("TestCog")
        bot.tree.remove_command("admin")
        await bot.close()

    @pytest.mark.asyncio
    async def test_commands_can_be_added_to_mod_group(self):
        """Test that commands can be added to mod group."""

        # Create a simple test cog with a command in mod group
        class TestModCog(commands.Cog):
            def __init__(self, bot):
                self.bot = bot

            @mod.command(name="test_mod", description="Test moderation command")
            async def test_mod_command(self, interaction: discord.Interaction):
                """Test mod command."""
                await interaction.response.send_message("Mod test response")

        # Create bot and register group
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(mod)

        # Load the test cog
        test_cog = TestModCog(bot)
        await bot.add_cog(test_cog)

        # Verify the command exists in the mod group
        mod_group = bot.tree.get_command("mod")
        assert mod_group is not None

        # Get commands from the group
        group_commands = mod_group.commands
        command_names = [cmd.name for cmd in group_commands]
        assert "test_mod" in command_names

        # Cleanup
        await bot.remove_cog("TestModCog")
        bot.tree.remove_command("mod")
        await bot.close()

    @pytest.mark.asyncio
    async def test_multiple_cogs_can_use_same_group(self):
        """Test that multiple cogs can add commands to the same group."""

        # Create two cogs that both use the admin group
        class TestCog1(commands.Cog):
            def __init__(self, bot):
                self.bot = bot

            @admin.command(name="cmd1", description="Command from cog 1")
            async def command1(self, interaction: discord.Interaction):
                await interaction.response.send_message("Cog 1")

        class TestCog2(commands.Cog):
            def __init__(self, bot):
                self.bot = bot

            @admin.command(name="cmd2", description="Command from cog 2")
            async def command2(self, interaction: discord.Interaction):
                await interaction.response.send_message("Cog 2")

        # Create bot and register group
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(admin)

        # Load both cogs
        test_cog1 = TestCog1(bot)
        test_cog2 = TestCog2(bot)
        await bot.add_cog(test_cog1)
        await bot.add_cog(test_cog2)

        # Verify both commands exist in the admin group
        admin_group = bot.tree.get_command("admin")
        assert admin_group is not None

        group_commands = admin_group.commands
        command_names = [cmd.name for cmd in group_commands]
        assert "cmd1" in command_names
        assert "cmd2" in command_names
        assert len([n for n in command_names if n in ["cmd1", "cmd2"]]) == 2

        # Cleanup
        await bot.remove_cog("TestCog1")
        await bot.remove_cog("TestCog2")
        bot.tree.remove_command("admin")
        await bot.close()


class TestCommandGroupIntegration:
    """Integration tests for command groups in real cog scenarios."""

    @pytest.mark.asyncio
    async def test_owner_cog_uses_admin_group(self):
        """Test that OwnerCog commands are in admin group."""
        from cogs.owner import OwnerCog

        # Create bot and register groups
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(admin)

        # Load OwnerCog
        owner_cog = OwnerCog(bot)
        await bot.add_cog(owner_cog)

        # Verify admin group has owner commands
        admin_group = bot.tree.get_command("admin")
        assert admin_group is not None

        group_commands = admin_group.commands
        command_names = [cmd.name for cmd in group_commands]

        # Check for some expected owner commands
        expected_commands = ["load", "unload", "reload", "sync", "exit"]
        for expected in expected_commands:
            assert expected in command_names, (
                f"Expected '{expected}' command in admin group"
            )

        # Cleanup
        await bot.remove_cog("Owner")
        bot.tree.remove_command("admin")
        await bot.close()

    @pytest.mark.asyncio
    async def test_mods_cog_uses_mod_group(self):
        """Test that ModsCog commands are in mod group."""
        from cogs.mods import ModCogs

        # Create bot and register groups
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(mod)

        # Load ModCogs
        mod_cog = ModCogs(bot)
        await bot.add_cog(mod_cog)

        # Verify mod group has mod commands
        mod_group = bot.tree.get_command("mod")
        assert mod_group is not None

        group_commands = mod_group.commands
        command_names = [cmd.name for cmd in group_commands]

        # Check for expected mod commands
        expected_commands = ["reset", "state"]
        for expected in expected_commands:
            assert expected in command_names, (
                f"Expected '{expected}' command in mod group"
            )

        # Cleanup
        await bot.remove_cog("Mods")
        bot.tree.remove_command("mod")
        await bot.close()

    @pytest.mark.asyncio
    async def test_gallery_cog_uses_gallery_admin_group(self):
        """Test that GalleryCog commands are in gallery_admin group."""
        from cogs.gallery import GalleryCog

        # Create bot and register groups
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(gallery_admin)

        # Load GalleryCog
        gallery_cog = GalleryCog(bot)
        await bot.add_cog(gallery_cog)

        # Verify gallery_admin group has gallery commands
        gallery_group = bot.tree.get_command("gallery_admin")
        assert gallery_group is not None

        group_commands = gallery_group.commands
        command_names = [cmd.name for cmd in group_commands]

        # Check for expected gallery admin commands
        expected_commands = ["set_repost", "extract_data", "migration_stats"]
        for expected in expected_commands:
            assert expected in command_names, (
                f"Expected '{expected}' command in gallery_admin group"
            )

        # Cleanup
        await bot.remove_cog("Gallery")
        bot.tree.remove_command("gallery_admin")
        await bot.close()


@pytest.mark.usefixtures("reset_command_groups")
class TestCommandGroupInvocation:
    """Tests for invoking commands through groups."""

    @pytest.mark.asyncio
    async def test_grouped_command_callback_pattern(self):
        """Test the callback pattern for invoking grouped commands."""

        from tests.mock_factories import MockInteractionFactory

        # Create a test cog with a grouped command
        class TestInvokeCog(commands.Cog):
            def __init__(self, bot):
                self.bot = bot
                self.command_called = False

            @admin.command(name="invoke_test", description="Test invocation")
            async def test_invoke(self, interaction: discord.Interaction, value: str):
                """Test command invocation."""
                self.command_called = True
                await interaction.response.send_message(f"Received: {value}")

        # Create bot and register group
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(admin)

        # Load cog
        test_cog = TestInvokeCog(bot)
        await bot.add_cog(test_cog)

        # Create mock interaction
        interaction = MockInteractionFactory.create()

        # Invoke the command using callback pattern
        await test_cog.test_invoke.callback(test_cog, interaction, value="test_value")

        # Verify command was executed
        assert test_cog.command_called is True
        interaction.response.send_message.assert_called_once()

        # Cleanup
        await bot.remove_cog("TestInvokeCog")
        bot.tree.remove_command("admin")
        await bot.close()

    @pytest.mark.asyncio
    async def test_grouped_command_with_defer(self):
        """Test grouped command that defers response."""
        from tests.mock_factories import MockInteractionFactory

        # Create a test cog
        class TestDeferCog(commands.Cog):
            def __init__(self, bot):
                self.bot = bot

            @admin.command(name="defer_test", description="Test defer")
            async def test_defer(self, interaction: discord.Interaction):
                """Test deferred response."""
                await interaction.response.defer()
                await interaction.followup.send("Deferred response")

        # Create bot and register group
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(admin)

        # Load cog
        test_cog = TestDeferCog(bot)
        await bot.add_cog(test_cog)

        # Create mock interaction
        interaction = MockInteractionFactory.create()

        # Invoke command
        await test_cog.test_defer.callback(test_cog, interaction)

        # Verify defer and followup were called
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

        # Cleanup
        await bot.remove_cog("TestDeferCog")
        bot.tree.remove_command("admin")
        await bot.close()


@pytest.mark.usefixtures("reset_command_groups")
class TestCommandGroupBinding:
    """Tests for command binding to cog instances.

    Commands added to external groups via @group.command() don't automatically
    get bound to their cog instances. The cog_load() method must manually bind
    them to prevent TypeError when invoked.
    """

    @pytest.mark.asyncio
    async def test_external_group_commands_need_manual_binding(self):
        """Test that commands in external groups start with binding=None."""

        class TestCog(commands.Cog):
            def __init__(self, bot):
                self.bot = bot

            @admin.command(name="binding_test", description="Test binding")
            async def binding_test(self, interaction: discord.Interaction):
                await interaction.response.send_message("Test")

        # Create bot and register group
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(admin)

        # Before cog is loaded, find our command
        cmd = None
        for c in admin.commands:
            if c.name == "binding_test":
                cmd = c
                break

        assert cmd is not None, "Command should exist in group after decoration"
        # Command binding is None before cog_load sets it
        assert cmd.binding is None, "External group commands start with binding=None"

        # Cleanup
        admin.remove_command("binding_test")
        bot.tree.remove_command("admin")
        await bot.close()

    @pytest.mark.asyncio
    async def test_cog_load_binds_commands(self):
        """Test that cog_load() properly binds commands to cog instance."""

        class TestBindingCog(commands.Cog):
            def __init__(self, bot):
                self.bot = bot

            async def cog_load(self) -> None:
                """Bind commands to this cog instance."""
                for cmd in admin.commands:
                    if cmd.callback.__name__ == "bound_command":
                        cmd.binding = self

            @admin.command(name="bound_cmd", description="Test bound command")
            async def bound_command(self, interaction: discord.Interaction):
                await interaction.response.send_message("Bound!")

        # Create bot and register group
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(admin)

        # Create and load cog
        test_cog = TestBindingCog(bot)
        await bot.add_cog(test_cog)

        # Find our command
        cmd = None
        for c in admin.commands:
            if c.name == "bound_cmd":
                cmd = c
                break

        assert cmd is not None, "Command should exist"
        assert cmd.binding is test_cog, (
            "Command should be bound to cog instance after cog_load()"
        )

        # Cleanup
        await bot.remove_cog("TestBindingCog")
        admin.remove_command("bound_cmd")
        bot.tree.remove_command("admin")
        await bot.close()

    @pytest.mark.asyncio
    async def test_bound_command_can_access_self(self):
        """Test that properly bound commands can access self (cog instance)."""
        from tests.mock_factories import MockInteractionFactory

        class TestSelfAccessCog(commands.Cog):
            def __init__(self, bot):
                self.bot = bot
                self.was_called = False

            async def cog_load(self) -> None:
                for cmd in admin.commands:
                    if cmd.callback.__name__ == "self_access_cmd":
                        cmd.binding = self

            @admin.command(name="self_access", description="Test self access")
            async def self_access_cmd(self, interaction: discord.Interaction):
                # This should work because self is properly bound
                self.was_called = True
                await interaction.response.send_message(f"Bot: {self.bot}")

        # Create bot and register group
        bot = await TestSetup.create_test_bot()
        bot.tree.add_command(admin)

        # Create and load cog
        test_cog = TestSelfAccessCog(bot)
        await bot.add_cog(test_cog)

        # Create mock interaction and invoke via callback
        interaction = MockInteractionFactory.create()

        # Find command and invoke it properly (simulating discord.py's invocation)
        cmd = None
        for c in admin.commands:
            if c.name == "self_access":
                cmd = c
                break

        assert cmd is not None
        assert cmd.binding is test_cog

        # Invoke using the binding (this is what discord.py does internally)
        await cmd.callback(cmd.binding, interaction)

        assert test_cog.was_called is True, "Command should have accessed self"

        # Cleanup
        await bot.remove_cog("TestSelfAccessCog")
        admin.remove_command("self_access")
        bot.tree.remove_command("admin")
        await bot.close()


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main(["-v", __file__])

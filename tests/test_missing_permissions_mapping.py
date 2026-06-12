"""
Unit tests for the MissingPermissions error mapping (audit findings-09 L7).

Before the fix, every app_commands.CheckFailure — including MissingPermissions
— was answered with "This command can only be used in specific channels.",
telling a permission-denied user it was a *channel* problem. These tests pin
the new behaviour: MissingPermissions (both the prefix-command and the
app-command flavour) produces a "You need the following permissions: ..."
message, while the generic CheckFailure messages are unchanged.

NOTE: tests/conftest.py purges project modules from sys.modules after every
test, so utils.error_handling is imported fresh inside each test (never
patched by string path) — see tests/test_external_api_integration.py.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands
from discord.ext import commands

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


class TestMissingPermissionsResponse:
    """get_error_response maps MissingPermissions to a permission message."""

    def test_app_command_missing_permissions_lists_permissions(self) -> None:
        from utils.error_handling import get_error_response

        error = app_commands.MissingPermissions(["ban_members", "manage_messages"])
        response = get_error_response(error)

        message = response["message"]
        assert "You need the following permissions" in message
        assert "Ban Members" in message
        assert "Manage Messages" in message
        # The wrong-reason channel message must NOT be used.
        assert "specific channels" not in message
        assert response["ephemeral"] is True

    def test_prefix_command_missing_permissions_lists_permissions(self) -> None:
        from utils.error_handling import get_error_response

        error = commands.MissingPermissions(["ban_members"])
        response = get_error_response(error)

        message = response["message"]
        assert "You need the following permissions" in message
        assert "Ban Members" in message
        assert response["ephemeral"] is True

    def test_guild_prefix_rendered_as_server(self) -> None:
        from utils.error_handling import get_error_response

        error = app_commands.MissingPermissions(["manage_guild"])
        response = get_error_response(error)

        assert "Manage Server" in response["message"]

    def test_message_is_fully_rendered(self) -> None:
        """The {permissions} placeholder must be filled by get_error_response.

        The command handlers only run .format(error=error) on the template,
        which cannot fill {permissions} — so the response must come back with
        the placeholder already rendered.
        """
        from utils.error_handling import get_error_response

        error = app_commands.MissingPermissions(["ban_members"])
        response = get_error_response(error)

        assert "{permissions}" not in response["message"]
        # And the generic handler formatting must be a harmless no-op.
        assert response["message"].format(error=error) == response["message"]

    def test_generic_app_check_failure_keeps_channel_message(self) -> None:
        """The bot-channel check still gets the channel-specific message."""
        from utils.error_handling import get_error_response

        error = app_commands.CheckFailure("not in a bot channel")
        response = get_error_response(error)

        assert "specific channels" in response["message"]

    def test_generic_prefix_check_failure_keeps_permission_message(self) -> None:
        from utils.error_handling import get_error_response

        error = commands.CheckFailure("check failed")
        response = get_error_response(error)

        assert response["message"] == "You don't have permission to use this command."


class TestMissingPermissionsGlobalHandler:
    """End-to-end: the global app-command error handler sends the new text."""

    @pytest.mark.asyncio
    async def test_global_handler_sends_permission_message(self) -> None:
        from utils.error_handling import handle_global_app_command_error

        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.guild = None
        interaction.channel = None
        interaction.command = MagicMock()
        interaction.command.name = "ao3_status"
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        # track_error swallows its own failures, so a bare AsyncMock is enough.
        interaction.client = MagicMock()
        interaction.client.db.fetchval = AsyncMock(return_value=1)

        error = app_commands.MissingPermissions(["ban_members"])
        await handle_global_app_command_error(interaction, error)

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        assert "You need the following permissions" in args[0]
        assert "Ban Members" in args[0]
        assert "specific channels" not in args[0]
        assert kwargs.get("ephemeral") is True

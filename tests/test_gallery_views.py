"""
Unit tests for the gallery repost UI views (ButtonView / RepostMenu).

Covers the view-hygiene fixes from audit findings-09 L4:
- both views enforce the invoking user via interaction_check, with an
  ephemeral denial message for everyone else (no more silent
  "This interaction failed");
- both views have an explicit timeout and an on_timeout that disables the
  controls and pushes the disabled state to the message.

NOTE: tests/conftest.py purges project modules from sys.modules after every
test, so cogs.gallery is imported fresh inside each test (never patched by
string path) — see tests/test_external_api_integration.py for the rationale.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from tests.mock_factories import MockUserFactory  # noqa: E402


def make_interaction(user) -> MagicMock:
    """Create a minimal mock interaction for view-level checks."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = user
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


class TestButtonView:
    """Tests for ButtonView auth and timeout hygiene."""

    @pytest.mark.asyncio
    async def test_has_explicit_timeout(self) -> None:
        from cogs.gallery import VIEW_TIMEOUT, ButtonView

        view = ButtonView(invoker=MockUserFactory.create())
        assert view.timeout == VIEW_TIMEOUT

    @pytest.mark.asyncio
    async def test_interaction_check_allows_invoker(self) -> None:
        from cogs.gallery import ButtonView

        invoker = MockUserFactory.create()
        view = ButtonView(invoker=invoker)
        interaction = make_interaction(invoker)

        assert await view.interaction_check(interaction) is True
        interaction.response.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_user_with_ephemeral(self) -> None:
        from cogs.gallery import ButtonView

        view = ButtonView(invoker=MockUserFactory.create())
        interaction = make_interaction(MockUserFactory.create())

        assert await view.interaction_check(interaction) is False
        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        assert kwargs.get("ephemeral") is True
        assert "belongs to someone else" in args[0]

    @pytest.mark.asyncio
    async def test_button_press_records_choice_and_stops(self) -> None:
        from cogs.gallery import ButtonView

        invoker = MockUserFactory.create()
        view = ButtonView(invoker=invoker)
        interaction = make_interaction(invoker)

        await view.text.callback(interaction)

        assert view.repost_choice == 5
        assert view.interaction is interaction
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_on_timeout_disables_buttons_and_edits_message(self) -> None:
        from cogs.gallery import ButtonView

        view = ButtonView(invoker=MockUserFactory.create())
        message = MagicMock()
        message.edit = AsyncMock()
        view.message = message

        await view.on_timeout()

        assert all(
            item.disabled
            for item in view.children
            if isinstance(item, discord.ui.Button)
        )
        message.edit.assert_awaited_once_with(view=view)

    @pytest.mark.asyncio
    async def test_on_timeout_survives_deleted_message(self) -> None:
        from cogs.gallery import ButtonView

        view = ButtonView(invoker=MockUserFactory.create())
        message = MagicMock()
        message.edit = AsyncMock(
            side_effect=discord.NotFound(MagicMock(status=404), "deleted")
        )
        view.message = message

        # Must not raise even though the message is already gone.
        await view.on_timeout()

    @pytest.mark.asyncio
    async def test_on_timeout_without_message_is_noop(self) -> None:
        from cogs.gallery import ButtonView

        view = ButtonView(invoker=MockUserFactory.create())
        assert view.message is None
        await view.on_timeout()  # must not raise


class TestRepostMenu:
    """Tests for RepostMenu auth and timeout hygiene."""

    @pytest.mark.asyncio
    async def test_has_explicit_timeout(self) -> None:
        from cogs.gallery import VIEW_TIMEOUT, RepostMenu

        menu = RepostMenu(
            mention="@creator",
            jump_url="https://discord.com/channels/1/2/3",
            title="t",
            invoker=MockUserFactory.create(),
        )
        assert menu.timeout == VIEW_TIMEOUT

    @pytest.mark.asyncio
    async def test_interaction_check_allows_invoker(self) -> None:
        from cogs.gallery import RepostMenu

        invoker = MockUserFactory.create()
        menu = RepostMenu(
            mention="@creator",
            jump_url="https://discord.com/channels/1/2/3",
            title="t",
            invoker=invoker,
        )
        interaction = make_interaction(invoker)

        assert await menu.interaction_check(interaction) is True
        interaction.response.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_user_with_ephemeral(self) -> None:
        from cogs.gallery import RepostMenu

        menu = RepostMenu(
            mention="@creator",
            jump_url="https://discord.com/channels/1/2/3",
            title="t",
            invoker=MockUserFactory.create(),
        )
        interaction = make_interaction(MockUserFactory.create())

        assert await menu.interaction_check(interaction) is False
        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        assert kwargs.get("ephemeral") is True
        assert "belongs to someone else" in args[0]

    @pytest.mark.asyncio
    async def test_interaction_check_permissive_without_invoker(self) -> None:
        """Backwards-compat: a menu built without an invoker stays usable."""
        from cogs.gallery import RepostMenu

        menu = RepostMenu(
            mention="@creator",
            jump_url="https://discord.com/channels/1/2/3",
            title="t",
        )
        interaction = make_interaction(MockUserFactory.create())

        assert await menu.interaction_check(interaction) is True

    @pytest.mark.asyncio
    async def test_on_timeout_disables_controls_and_edits_message(self) -> None:
        from cogs.gallery import RepostMenu

        menu = RepostMenu(
            mention="@creator",
            jump_url="https://discord.com/channels/1/2/3",
            title="t",
            invoker=MockUserFactory.create(),
        )
        message = MagicMock()
        message.edit = AsyncMock()
        menu.message = message

        await menu.on_timeout()

        assert menu.channel_select.disabled
        assert menu.submit_button.disabled
        assert menu.title_button.disabled
        message.edit.assert_awaited_once_with(view=menu)

    @pytest.mark.asyncio
    async def test_on_timeout_survives_deleted_message(self) -> None:
        from cogs.gallery import RepostMenu

        menu = RepostMenu(
            mention="@creator",
            jump_url="https://discord.com/channels/1/2/3",
            title="t",
            invoker=MockUserFactory.create(),
        )
        message = MagicMock()
        message.edit = AsyncMock(
            side_effect=discord.NotFound(MagicMock(status=404), "deleted")
        )
        menu.message = message

        # Must not raise even though the message is already gone.
        await menu.on_timeout()

"""Behaviour when the bot runs without Discord's Message Content intent.

MESSAGE_CONTENT_INTENT=false lets the bot connect while Discord has the
privileged intent disabled. Message text then arrives empty, so the stats must
record "unknown" (NULL) rather than a length of 0, and the moderation log must
not present empty text as if the message really was empty.
"""

import os
import sys
import types
from unittest.mock import AsyncMock

import discord
import pytest

# conftest purges `config` from sys.modules after each test; make sure the repo
# root is importable so it can be re-imported (same pattern as test_owner_cog).
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


def _bot(*, message_content: bool) -> types.SimpleNamespace:
    intents = discord.Intents.default()
    intents.message_content = message_content
    return types.SimpleNamespace(intents=intents, db=AsyncMock())


def _message(content: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(content=content)


def test_content_length_recorded_when_intent_enabled() -> None:
    from cogs.stats_listeners import _content_length

    assert _content_length(_bot(message_content=True), _message("hello")) == 5


def test_content_length_unknown_when_intent_disabled() -> None:
    from cogs.stats_listeners import _content_length

    # Discord sends "" without the intent; that must not be stored as 0.
    assert _content_length(_bot(message_content=False), _message("")) is None


def test_content_length_defaults_to_enabled_without_intents_attr() -> None:
    from cogs.stats_listeners import _content_length

    bot = types.SimpleNamespace(db=AsyncMock())
    assert _content_length(bot, _message("abc")) == 3


@pytest.mark.asyncio
async def test_edit_does_not_touch_length_when_intent_disabled() -> None:
    from cogs.stats_listeners import StatsListenersMixin

    bot = _bot(message_content=False)
    payload = types.SimpleNamespace(
        data={
            "id": "123",
            "content": "",
            "edited_timestamp": "2026-01-01T12:05:00+00:00",
        }
    )
    await StatsListenersMixin.message_edited(
        types.SimpleNamespace(bot=bot),  # type: ignore[arg-type]
        payload,  # type: ignore[arg-type]
    )

    queries = [call.args[0] for call in bot.db.execute.await_args_list]
    assert any("INSERT INTO message_edit" in q for q in queries)
    assert not any("content_length" in q for q in queries)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, True), ("true", True), ("false", False), ("0", False), ("no", False)],
)
def test_config_parses_message_content_intent(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, expected: bool
) -> None:
    import config

    if raw is None:
        monkeypatch.delenv("MESSAGE_CONTENT_INTENT", raising=False)
    else:
        monkeypatch.setenv("MESSAGE_CONTENT_INTENT", raw)
    assert config.load_from_env().message_content_intent is expected

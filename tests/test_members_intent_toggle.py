"""Behaviour when the bot runs without Discord's Server Members intent.

MEMBERS_INTENT=false lets the bot connect while Discord has the privileged
intent disabled. The member cache is then nearly empty, so permission checks
must fall back to fetching the member over REST instead of denying everyone.
"""

import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

# conftest purges `config` from sys.modules after each test; make sure the repo
# root is importable so it can be re-imported (same pattern as test_owner_cog).
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


def _not_found() -> discord.NotFound:
    return discord.NotFound(MagicMock(status=404, reason="Not Found"), "Unknown Member")


def _guild(
    *, cached: object | None, fetched: object | BaseException | None
) -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.id = 1
    guild.get_member.return_value = cached
    if isinstance(fetched, BaseException):
        guild.fetch_member = AsyncMock(side_effect=fetched)
    else:
        guild.fetch_member = AsyncMock(return_value=fetched)
    return guild


@pytest.mark.asyncio
async def test_cache_hit_does_not_call_api() -> None:
    from utils.permissions import get_guild_member

    member = object()
    guild = _guild(cached=member, fetched=None)

    assert await get_guild_member(guild, 42) is member
    guild.fetch_member.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_miss_falls_back_to_rest() -> None:
    from utils.permissions import get_guild_member

    member = object()
    guild = _guild(cached=None, fetched=member)

    assert await get_guild_member(guild, 42) is member
    guild.fetch_member.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_unknown_member_returns_none() -> None:
    from utils.permissions import get_guild_member

    guild = _guild(cached=None, fetched=_not_found())

    assert await get_guild_member(guild, 42) is None


@pytest.mark.asyncio
async def test_is_moderator_works_with_empty_member_cache() -> None:
    from utils.permissions import is_moderator

    mod = types.SimpleNamespace(
        guild_permissions=types.SimpleNamespace(ban_members=True)
    )
    guild = _guild(cached=None, fetched=mod)
    bot = MagicMock()
    bot.get_guild.return_value = guild

    assert await is_moderator(bot, guild.id, 123456789) is True
    guild.fetch_member.assert_awaited_once()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, True), ("true", True), ("false", False), ("0", False), ("no", False)],
)
def test_config_parses_members_intent(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, expected: bool
) -> None:
    import config

    if raw is None:
        monkeypatch.delenv("MEMBERS_INTENT", raising=False)
    else:
        monkeypatch.setenv("MEMBERS_INTENT", raw)
    assert config.load_from_env().members_intent is expected

"""Patreon requests go through PATREON_PROXY_URL when it is set.

Patreon blocks Railway's IP ranges, so production routes these calls through
a residential-IP proxy. Unset means a direct connection (local dev, tests).
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

# conftest purges modules between tests; keep the repo root importable.
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


class _Response:
    async def text(self) -> str:
        return '{"data": []}'

    async def __aenter__(self) -> "_Response":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _session() -> MagicMock:
    session = MagicMock()
    session.get = MagicMock(return_value=_Response())
    return session


@pytest.mark.asyncio
@pytest.mark.parametrize("proxy_url", ["http://twibot:secret@203.0.113.7:48888", None])
async def test_fetch_passes_configured_proxy(
    monkeypatch: pytest.MonkeyPatch, proxy_url: str | None
) -> None:
    import cogs.patreon_poll as patreon_poll

    # patch.object-style on the module the cog actually uses (see memory:
    # string-path patching misses because conftest purges sys.modules).
    monkeypatch.setattr(patreon_poll.config, "patreon_proxy_url", proxy_url)
    session = _session()

    body = await patreon_poll.fetch(session, "https://www.patreon.com/api/posts")

    assert body == '{"data": []}'
    assert session.get.call_args.kwargs["proxy"] == proxy_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, None), ("", None), ("http://u:p@h:1", "http://u:p@h:1")],
)
def test_config_parses_patreon_proxy_url(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, expected: str | None
) -> None:
    import config

    if raw is None:
        monkeypatch.delenv("PATREON_PROXY_URL", raising=False)
    else:
        monkeypatch.setenv("PATREON_PROXY_URL", raw)
    assert config.load_from_env().patreon_proxy_url == expected
    sensitive = config.BotConfig.__private_attributes__["_sensitive_fields"].default
    assert "patreon_proxy_url" in sensitive

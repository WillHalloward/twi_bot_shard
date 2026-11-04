"""/wiki must not send the Patreon session to fandom.com.

cogs/twi.py used to reuse cogs.patreon_poll.fetch, which defaults to the
Patreon cookies/headers (config.COOKIES / config.HEADERS) and the Patreon-only
egress proxy. Every wiki search therefore leaked the Patreon session cookie to
thewanderinginn.fandom.com.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

# conftest purges modules between tests; keep the repo root importable.
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


class _Response:
    async def text(self) -> str:
        return '{"query": {}}'

    async def __aenter__(self) -> "_Response":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


@pytest.mark.asyncio
async def test_fetch_wiki_sends_no_cookies_headers_or_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cogs.twi as twi

    # Even with Patreon credentials configured, none may reach the wiki.
    monkeypatch.setattr(twi.config, "cookies", {"session_id": "SECRET"})
    monkeypatch.setattr(twi.config, "headers", {"User-Agent": "x"})
    session = MagicMock()
    session.get = MagicMock(return_value=_Response())

    url = "https://thewanderinginn.fandom.com/api.php?action=query"
    assert await twi.fetch_wiki(session, url) == '{"query": {}}'

    session.get.assert_called_once_with(url)


def test_twi_no_longer_imports_patreon_fetch() -> None:
    import cogs.twi as twi

    assert not hasattr(twi, "fetch"), "cogs.twi must not use patreon_poll.fetch"

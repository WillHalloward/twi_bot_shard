"""Patreon API requests go through the NAS relay when it is configured.

Patreon's Cloudflare challenges requests from Railway; docker/patreon-relay on
the owner's NAS fetches Patreon API URLs from a home connection with its own
session cookie. Unset relay config keeps the direct request with
COOKIES/HEADERS (local dev, tests).
"""

import os
import sys
from unittest.mock import MagicMock

import aiohttp
import pytest

# conftest purges modules between tests; keep the repo root importable.
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

FP = "24:F8:86:C8:22:CE:B9:8A:10:74:1E:7C:D9:BC:20:77:E1:AD:DC:4C:F1:61:99:D6:DF:A6:B3:6E:C2:BB:A5:02"
API_URL = (
    "https://www.patreon.com/api/posts?include=Cpoll.choices%2Cpoll"
    "&filter[campaign_id]=568211"
)


class _Response:
    def __init__(self, status: int = 200, body: str = '{"data": []}') -> None:
        self.status = status
        self._body = body

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> "_Response":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _session(resp: _Response | None = None) -> MagicMock:
    session = MagicMock()
    session.get = MagicMock(return_value=resp or _Response())
    return session


def _configure(monkeypatch: pytest.MonkeyPatch, mod, **values) -> None:
    defaults = {
        "patreon_relay_url": None,
        "patreon_relay_token": None,
        "patreon_relay_cert_sha256": None,
        "cookies": {"session_id": "SECRET"},
        "headers": {"User-Agent": "UA"},
    }
    defaults.update(values)
    for k, v in defaults.items():
        monkeypatch.setattr(mod.config, k, v)


@pytest.mark.asyncio
async def test_direct_when_relay_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    import cogs.patreon_poll as pp

    _configure(monkeypatch, pp)
    session = _session()

    assert await pp.fetch(session, API_URL) == '{"data": []}'
    args, kwargs = session.get.call_args
    assert args == (API_URL,)
    assert kwargs["cookies"] == {"session_id": "SECRET"}


@pytest.mark.asyncio
async def test_relay_used_and_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    import cogs.patreon_poll as pp

    _configure(
        monkeypatch,
        pp,
        patreon_relay_url="https://203.0.113.7:48888",
        patreon_relay_token="t" * 64,
        patreon_relay_cert_sha256=FP,
    )
    session = _session()

    assert await pp.fetch(session, API_URL) == '{"data": []}'
    args, kwargs = session.get.call_args
    assert args == ("https://203.0.113.7:48888/fetch",)
    assert kwargs["params"] == {"url": API_URL}
    assert kwargs["headers"] == {"Authorization": "Bearer " + "t" * 64}
    assert isinstance(kwargs["ssl"], aiohttp.Fingerprint)
    # The Patreon session never leaves the bot when the relay is used.
    assert "cookies" not in kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token", "fp"), [(None, FP), ("t" * 64, None), ("t" * 64, "abcd")]
)
async def test_relay_misconfigured_raises(
    monkeypatch: pytest.MonkeyPatch, token: str | None, fp: str | None
) -> None:
    import cogs.patreon_poll as pp

    _configure(
        monkeypatch,
        pp,
        patreon_relay_url="https://203.0.113.7:48888",
        patreon_relay_token=token,
        patreon_relay_cert_sha256=fp,
    )
    with pytest.raises(pp.ExternalServiceError):
        await pp.fetch(_session(), API_URL)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 429, 502])
async def test_relay_rejection_raises(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    import cogs.patreon_poll as pp

    _configure(
        monkeypatch,
        pp,
        patreon_relay_url="https://203.0.113.7:48888",
        patreon_relay_token="t" * 64,
        patreon_relay_cert_sha256=FP,
    )
    with pytest.raises(pp.ExternalServiceError):
        await pp.fetch(_session(_Response(status, "nope")), API_URL)


def test_config_parses_relay_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Import BEFORE setting the env vars: conftest purges `config` between
    # tests, and a fresh import would bake the relay settings into the
    # module-level config that other (already-imported) modules then keep.
    import config

    monkeypatch.setenv("PATREON_RELAY_URL", "https://203.0.113.7:48888/")
    monkeypatch.setenv("PATREON_RELAY_TOKEN", "tok")
    monkeypatch.setenv("PATREON_RELAY_CERT_SHA256", FP)
    cfg = config.load_from_env()
    assert cfg.patreon_relay_url == "https://203.0.113.7:48888"
    assert cfg.patreon_relay_token == "tok"
    assert cfg.patreon_relay_cert_sha256 == FP
    sensitive = config.BotConfig.__private_attributes__["_sensitive_fields"].default
    assert "patreon_relay_token" in sensitive


def test_config_relay_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    import config

    for k in ("PATREON_RELAY_URL", "PATREON_RELAY_TOKEN", "PATREON_RELAY_CERT_SHA256"):
        monkeypatch.delenv(k, raising=False)
    assert config.load_from_env().patreon_relay_url is None

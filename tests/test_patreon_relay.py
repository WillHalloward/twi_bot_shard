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
    def __init__(
        self,
        status: int = 200,
        body: str = '{"data": []}',
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}

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
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    monkeypatch.setattr(pp.asyncio, "sleep", fake_sleep)
    session = _session(
        _Response(status, "nope", {"Retry-After": "3", "X-Relay-Error": "nope"})
    )
    with pytest.raises(pp.ExternalServiceError):
        await pp.fetch(session, API_URL)
    if status == 429:
        # Retried RELAY_429_RETRIES times, waiting Retry-After each time.
        assert session.get.call_count == pp.RELAY_429_RETRIES + 1
        assert sleeps == [3.0] * pp.RELAY_429_RETRIES
    else:
        assert session.get.call_count == 1
        assert sleeps == []


@pytest.mark.asyncio
async def test_relay_429_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import cogs.patreon_poll as pp

    _configure(
        monkeypatch,
        pp,
        patreon_relay_url="https://203.0.113.7:48888",
        patreon_relay_token="t" * 64,
        patreon_relay_cert_sha256=FP,
    )
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    monkeypatch.setattr(pp.asyncio, "sleep", fake_sleep)
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[
            _Response(
                429,
                "rate limited",
                {"Retry-After": "12", "X-Relay-Error": "rate limited"},
            ),
            _Response(200, '{"data": [1]}'),
        ]
    )

    assert await pp.fetch(session, API_URL) == '{"data": [1]}'
    assert sleeps == [12.0]
    assert session.get.call_count == 2


@pytest.mark.parametrize(
    ("header", "expected"),
    [("12", 12.0), (None, 10.0), ("garbage", 10.0), ("0", 1.0), ("3600", 65.0)],
)
def test_retry_after_parsing(header: str | None, expected: float) -> None:
    import cogs.patreon_poll as pp

    assert pp._retry_after_seconds(header) == expected


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


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429])
async def test_upstream_status_passed_through(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """A Patreon status relayed unchanged (no X-Relay-Error) is not a relay
    failure: return the body like a direct request would, never retry."""
    import cogs.patreon_poll as pp

    _configure(
        monkeypatch,
        pp,
        patreon_relay_url="https://203.0.113.7:48888",
        patreon_relay_token="t" * 64,
        patreon_relay_cert_sha256=FP,
    )
    body = '{"errors": [{"title": "Unauthorized"}]}'
    session = _session(_Response(status, body))

    assert await pp.fetch(session, API_URL) == body
    assert session.get.call_count == 1

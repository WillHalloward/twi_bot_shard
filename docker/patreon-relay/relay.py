"""Patreon API relay for the Twi Discord bot (runs on the owner's NAS).

Patreon's Cloudflare challenges requests from the bot's Railway containers, but
plain requests from this home connection go through. The bot asks this relay
to fetch a Patreon *API* URL; the relay makes the request from here with an
ordinary curl client and the team account's session cookie, and returns the
response. The session cookie lives only on this machine.

Locked down:
  * HTTPS with a self-signed cert; the bot pins its SHA-256 fingerprint.
  * Source-IP allowlist (Railway static outbound IPs, Docker gateway, LAN).
  * Bearer token (constant-time compare).
  * Only GET https://www.patreon.com/api/... URLs; nothing else is fetched.
  * Simple global rate limit.

Endpoints:
  GET /healthz                  -> 200 "ok"         (no auth; for checks)
  GET /fetch?url=<patreon api>  -> upstream status + body (auth required)

Config (environment):
  RELAY_TOKEN      required, shared secret (Authorization: Bearer ...)
  ALLOW_IPS        comma-separated client IPs/CIDRs
  PATREON_COOKIES  JSON object of cookies (e.g. {"session_id": "..."})
  PATREON_UA       optional User-Agent for upstream requests
  TLS_CERT/TLS_KEY paths (default /certs/relay.crt, /certs/relay.key)
  RATE_PER_MIN     max upstream fetches per minute (default 30)

Standard library only (plus the curl binary).
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import os
import ssl
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ALLOWED_PREFIX = "https://www.patreon.com/api/"
LISTEN_PORT = int(os.environ.get("PORT", "8443"))
TOKEN = os.environ["RELAY_TOKEN"].strip()
ALLOW_NETS = [
    ipaddress.ip_network(x.strip(), strict=False)
    for x in os.environ.get("ALLOW_IPS", "").split(",")
    if x.strip()
]
COOKIES: dict[str, str] = json.loads(os.environ.get("PATREON_COOKIES", "{}"))
UA = os.environ.get("PATREON_UA", "").strip()
RATE_PER_MIN = int(os.environ.get("RATE_PER_MIN", "30"))
MAX_BODY = 20 * 1024 * 1024  # 20 MiB cap on upstream responses

if len(TOKEN) < 32:
    sys.exit("RELAY_TOKEN must be at least 32 characters")
if not ALLOW_NETS:
    sys.exit("ALLOW_IPS must list at least one client IP/CIDR")

_rate_lock = threading.Lock()
_recent: deque[float] = deque()


def log(msg: str) -> None:
    """Write one log line to stdout (picked up by docker logs)."""
    print(time.strftime("%Y-%m-%dT%H:%M:%S"), msg, flush=True)


def allowed_client(ip: str) -> bool:
    """Return True if ``ip`` is inside one of the allowlisted networks."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in ALLOW_NETS)


def take_rate_slot() -> int:
    """Consume one slot of the per-minute budget.

    Returns:
        0 if a slot was taken, otherwise the whole seconds until the oldest
        slot frees up (sent to the client as Retry-After).
    """
    now = time.monotonic()
    with _rate_lock:
        while _recent and now - _recent[0] > 60:
            _recent.popleft()
        if len(_recent) >= RATE_PER_MIN:
            return max(1, int(60 - (now - _recent[0])) + 1)
        _recent.append(now)
        return 0


def valid_target(url: str) -> bool:
    """Only plain https://www.patreon.com/api/... URLs, no tricks."""
    if not url.startswith(ALLOWED_PREFIX):
        return False
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and parts.hostname == "www.patreon.com"
        and parts.port is None
        and not parts.username
        and not parts.password
        # URL is embedded in a quoted curl config line: refuse anything that
        # could break out of the quoting.
        and not any(c in url for c in '\r\n"\\')
    )


def fetch_upstream(url: str) -> tuple[int, bytes, str]:
    """GET ``url`` with curl and the session cookie.

    The cookie and URL are passed through curl's stdin config (-K -), so they
    never appear in the process list.

    Returns:
        (status, body, content_type)
    """
    # globoff: Patreon API URLs contain literal [] (filter[campaign_id]=...),
    # which curl would otherwise treat as a glob range and refuse.
    cfg = ["globoff", f'url = "{url}"']
    if COOKIES:
        cookie = "; ".join(f"{k}={v}" for k, v in COOKIES.items())
        cfg.append(f'cookie = "{cookie}"')
    if UA:
        cfg.append(f'user-agent = "{UA}"')
    proc = subprocess.run(
        [
            "curl",
            "-sS",
            "--compressed",
            "--max-time",
            "30",
            "--max-filesize",
            str(MAX_BODY),
            "-H",
            "Accept: application/json",
            "-w",
            "\n%{http_code} %{content_type}",
            "-K",
            "-",
        ],
        input="\n".join(cfg).encode(),
        capture_output=True,
        timeout=40,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"curl exit {proc.returncode}: {proc.stderr[:200]!r}")
    body, _, trailer = proc.stdout.rpartition(b"\n")
    status_s, _, ctype = trailer.decode(errors="replace").partition(" ")
    return int(status_s), body, ctype or "application/octet-stream"


class Handler(BaseHTTPRequestHandler):
    """Request handler for /healthz and /fetch."""

    server_version = "twi-patreon-relay/1"
    sys_version = ""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Silence the default per-request stderr logging (we log ourselves)."""

    def _reject(
        self, status: int, reason: str, extra_headers: dict[str, str] | None = None
    ) -> None:
        """Send a relay-originated error, labelled with X-Relay-Error.

        Lets clients tell it apart from an upstream Patreon status that /fetch
        passes through unchanged.
        """
        self._send(
            status,
            reason.encode(),
            extra_headers={"X-Relay-Error": reason, **(extra_headers or {})},
        )

    def _send(
        self,
        status: int,
        body: bytes,
        ctype: str = "text/plain",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        """Serve /healthz and /fetch."""
        client = self.client_address[0]
        if not allowed_client(client):
            log(f"deny ip={client} path={self.path.split('?')[0]}")
            self._reject(403, "forbidden")
            return

        path, _, query = self.path.partition("?")
        if path == "/healthz":
            self._send(200, b"ok")
            return
        if path != "/fetch":
            self._reject(404, "not found")
            return

        auth = self.headers.get("Authorization", "")
        if not hmac.compare_digest(auth.encode(), f"Bearer {TOKEN}".encode()):
            log(f"bad-token ip={client}")
            self._reject(401, "unauthorized")
            return

        url = (parse_qs(query).get("url") or [""])[0]
        if not valid_target(url):
            log(f"bad-url ip={client}")
            self._reject(400, "only https://www.patreon.com/api/ URLs are allowed")
            return
        retry_after = take_rate_slot()
        if retry_after:
            log(f"rate-limited ip={client} retry_after={retry_after}s")
            self._reject(
                429, "rate limited", extra_headers={"Retry-After": str(retry_after)}
            )
            return

        started = time.monotonic()
        try:
            status, body, ctype = fetch_upstream(url)
        except Exception as e:  # noqa: BLE001
            log(f"upstream-error ip={client} err={type(e).__name__}")
            self._reject(502, "upstream fetch failed")
            return
        log(
            f"fetch ip={client} status={status} bytes={len(body)} "
            f"ms={int((time.monotonic() - started) * 1000)} "
            f"path={urlsplit(url).path}"
        )
        self._send(status, body, ctype)


def main() -> None:
    """Start the HTTPS relay."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(
        os.environ.get("TLS_CERT", "/certs/relay.crt"),
        os.environ.get("TLS_KEY", "/certs/relay.key"),
    )
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    log(
        f"listening on :{LISTEN_PORT} allow={','.join(map(str, ALLOW_NETS))} "
        f"cookies={len(COOKIES)} rate={RATE_PER_MIN}/min"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()

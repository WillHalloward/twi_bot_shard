# Patreon API relay (runs on the owner's NAS)

Patreon's Cloudflare puts requests from the bot's Railway containers behind a
"Just a moment…" bot challenge (`cf-mitigated: challenge`), decided by the
client's TLS fingerprint — a plain forward proxy through a home IP did not
help. Ordinary `curl` from the home connection is not challenged. Patreon's
official API cannot read polls, so the bot keeps using the web API, but now
through this relay: the bot asks it to fetch a Patreon **API** URL, and the
relay makes the request from home with plain curl and the session cookie of a
(non-creator) team account.

```
Railway Cognita ──HTTPS (pinned cert, bearer token)──▶ NAS relay :48888 ──curl──▶ www.patreon.com/api/…
```

## Security

- **TLS with a pinned self-signed cert.** The bot verifies the cert's SHA-256
  fingerprint (`PATREON_RELAY_CERT_SHA256`), so the link is encrypted and the
  relay can't be impersonated. No CA / hostname needed (home IP may change).
- **Source-IP allowlist** (`ALLOW_IPS`): Railway Cognita static outbound IPs
  (production `208.77.244.240`, staging `208.77.244.241`, shared
  `152.55.184.240/.241`), the Docker bridge gateway `172.29.16.1` (requests
  from the NAS itself) and the home LAN. Docker preserves the real client IP
  (verified). The router can't do this itself: one rule per external port, and
  Railway spreads traffic over 3 IPs.
- **Bearer token** (`RELAY_TOKEN`, constant-time compare).
- **Only `https://www.patreon.com/api/…` URLs** are fetched; anything else,
  lookalike hosts and quote/CRLF tricks → `400`. Cookie and URL are passed to
  curl on stdin, never on the command line.
- **Rate limit** (`RATE_PER_MIN`, default 30) → `429`.
- The **Patreon session cookie lives only on the NAS** (`relay.env`, chmod 600);
  it is no longer needed in Railway.
- Container: read-only filesystem, `no-new-privileges`, runs as the NAS user so
  the private key can stay `chmod 600`. Standard-library Python + curl only.

## Where it runs

- QNAP NAS (`ssh nas`), Container Station, `/share/Container/patreon-relay`.
- Router forwards external **TCP 48888 → 192.168.0.46:48888**.
- Railway Cognita (staging and production) env:
  - `PATREON_RELAY_URL=https://<home public IP>:48888`
  - `PATREON_RELAY_TOKEN=<RELAY_TOKEN from relay.env>`
  - `PATREON_RELAY_CERT_SHA256=<fingerprint of certs/relay.crt>`

## Setup / rebuild

```bash
ssh nas
cd /share/Container/patreon-relay
mkdir -p certs && chmod 700 certs
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 3650 \
  -subj /CN=twi-patreon-relay -keyout certs/relay.key -out certs/relay.crt
chmod 600 certs/relay.key
cp relay.env.example relay.env && chmod 600 relay.env   # then fill it in:
sed -i "s/^RELAY_TOKEN=.*/RELAY_TOKEN=$(openssl rand -hex 32)/" relay.env
export PATH=/share/CACHEDEV1_DATA/.qpkg/container-station/bin:$PATH
export DOCKER_CONFIG=$PWD/.docker   # default ~/.docker isn't writable on QNAP
docker compose up -d --build
openssl x509 -in certs/relay.crt -noout -fingerprint -sha256   # -> PATREON_RELAY_CERT_SHA256
```

## Refreshing the Patreon session

When polls stop updating (relay log shows `/api/current_user` 401, or the bot
gets no polls): log into Patreon with the team account in a browser, copy the
`session_id` (and `patreon_device_id`) cookie, update `PATREON_COOKIES` in
`relay.env`, then `docker compose up -d` (env is read at start). Nothing to
change on Railway.

## Checks (on the NAS)

```bash
TOK=$(sed -n 's/^RELAY_TOKEN=//p' relay.env)
curl -sk https://127.0.0.1:48888/healthz                                    # ok
curl -sk --globoff -H "Authorization: Bearer $TOK" \
  'https://127.0.0.1:48888/fetch?url=https://www.patreon.com/api/current_user' | head -c 200
docker logs --tail 20 patreon-relay       # one line per request: ip, status, ms, path
```

## If something changes

- **Home IP changes** → update `PATREON_RELAY_URL` (cert pin is unaffected).
- **Railway static IPs change** (re-enabled, region move) → update `ALLOW_IPS`.
- **Cert expires (10 years) / regenerated** → update `PATREON_RELAY_CERT_SHA256`.

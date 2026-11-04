# Patreon egress proxy (runs on the owner's NAS)

Patreon blocks requests coming from Railway's IP ranges (the poll fetches in
`cogs/patreon_poll.py` got an HTML block page instead of JSON), while the exact
same requests work from a home connection. This is a minimal
[tinyproxy](https://tinyproxy.github.io/) forward proxy that the bot routes its
Patreon calls through, so Patreon sees a residential IP.

## How it is locked down

- **Source allowlist** (`Allow`): only the Railway Cognita static outbound IPs
  (production `208.77.244.240`, staging `208.77.244.241`, shared
  `152.55.184.240/.241`), the Docker bridge gateway (`172.29.16.1`, i.e. requests
  from the NAS itself) and the home LAN may connect at all. Checked before auth.
  The router can't do this: it allows one rule per external port, and Railway
  spreads each service's traffic over 3 IPs. If Static IPs are re-enabled or
  the service changes region, the IPs change — update `tinyproxy.conf`.
- **Password** (`BasicAuth`): no or wrong credentials → `407` / `401`.
- **Allowlist** (`FilterDefaultDeny Yes` + `filter`): only `*.patreon.com`;
  any other destination → `403`, even with valid credentials. It cannot be
  abused as an open proxy.
- **HTTPS only for tunnels** (`ConnectPort 443`). The bot talks HTTPS to
  Patreon through a CONNECT tunnel, so the Patreon cookies are never visible to
  the proxy or the network. (The proxy password itself travels in clear to the
  proxy; the allowlist limits what a leaked password could do.)
- Image is built locally from Alpine's own `tinyproxy` package (no third-party
  proxy image).

## Where it runs

- QNAP NAS (`ssh nas`), Container Station, project dir
  `/share/Container/patreon-proxy` (192.168.0.46).
- Router forwards external **TCP 48888 → 192.168.0.46:48888**.
- Railway `production` Cognita has
  `PATREON_PROXY_URL=http://twibot:<password>@<home public IP>:48888`.
  Unset = direct connection (staging/dev don't need it).

## Rebuild / rotate the password

```bash
ssh nas
cd /share/Container/patreon-proxy
cp tinyproxy.conf.example tinyproxy.conf   # only if starting from scratch
sed -i "s/^BasicAuth twibot .*/BasicAuth twibot $(openssl rand -hex 20)/" tinyproxy.conf
chmod 600 tinyproxy.conf
export PATH=/share/CACHEDEV1_DATA/.qpkg/container-station/bin:$PATH
export DOCKER_CONFIG=$PWD/.docker   # the default ~/.docker isn't writable on QNAP
docker compose up -d --build
```

Then update `PATREON_PROXY_URL` on Railway with the new password.

## If the home IP changes

`PATREON_PROXY_URL` contains the public IP. If the ISP changes it, either update
the variable or point it at a dynamic-DNS name for the home connection.

## Quick check from the NAS

```bash
PASS=$(awk '/^BasicAuth twibot /{print $3}' tinyproxy.conf)
curl -s -o /dev/null -w '%{http_code}\n' -x "http://twibot:$PASS@127.0.0.1:48888" \
  'https://www.patreon.com/api/posts?filter%5Bcampaign_id%5D=568211&page%5Bcount%5D=1'   # 200
curl -s -o /dev/null -w '%{http_connect}\n' -x "http://twibot:$PASS@127.0.0.1:48888" https://example.com   # 403
```

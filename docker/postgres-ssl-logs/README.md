# Postgres (official Railway image) with Railway-friendly logs — "Path B"

Runs the database on Railway's **official** Postgres image
(`ghcr.io/railwayapp-templates/postgres-ssl:18`) instead of the third-party
`pgvector/pgvector` image, while keeping the per-line log severity colouring.

## Why this over the plain custom image (Path A)

`postgres-ssl:18` is Railway-maintained and already bundles:

- **pgvector** (`postgresql-18-pgvector`) — required by the `/ask_db` command
- **jq** — used by the log shipper
- **Automatic SSL** — certs generated on first boot
- **pgBackRest backups / PITR** — dormant until you set `WAL_ARCHIVE_*` env vars

## Why there is still a Dockerfile (and not just an image + start command)

The official image does **not** colour logs on its own; Railway's own managed
Postgres adds that via a start command. We could do the same — point the
service straight at the image and set a one-line start command — but that
requires inlining the whole `jq` filter into a shell string (nested-quoting
hell) and isn't version-controlled. A two-line Dockerfile that copies the
shipper script in is far more robust and lives in the repo.

## How it works

`pg-log-entrypoint.sh` boots Postgres **through the image's own `wrapper.sh`**
(so SSL/backup setup still runs) with `log_destination=jsonlog` +
`logging_collector=off`, so JSON log lines go to stderr. That stderr is piped
through `ship-logs.sh` (a `jq` filter) which adds a normalised `level` field and
writes the result to the container's stdout. Postgres stays the main process
(`exec`), so SIGTERM still gives a graceful shutdown. No log files are written.

## Deploy

Builds onto the **existing** `pgvector` service — volume and data are preserved;
only the deploy source and start command change. Run from *inside* this
directory with no PATH argument (passing a path trips a CLI `prefix not found`
bug).

```bash
cd docker/postgres-ssl-logs

# Staging
railway link --project <project-id> --environment staging --service pgvector
railway up -d

# Production (after verifying staging)
railway link --project <project-id> --environment production --service pgvector
railway up -d
```

## Enabling backups later (optional)

Set these env vars on the service to turn on pgBackRest WAL archiving to S3:
`WAL_ARCHIVE_BUCKET`, `WAL_ARCHIVE_KEY`, `WAL_ARCHIVE_SECRET`,
`WAL_ARCHIVE_REGION`, `WAL_ARCHIVE_ENDPOINT`.

## Revert

Point the service's source back to the `pgvector/pgvector:pg18` image and
restore the original start command in the Railway dashboard:
`/bin/sh -c "unset PGPORT; docker-entrypoint.sh postgres --port=5432"`. Also
revert the volume mount path to its original value if needed (postgres-ssl
required dropping the trailing slash — see the deploy notes / project memory).

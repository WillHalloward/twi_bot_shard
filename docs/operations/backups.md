# Database Backups & Restore

How the Cognita database (`pgvector` service on Railway) is backed up, how to
verify backups are healthy, and how to restore — including point-in-time
recovery (PITR).

## How it works

The `pgvector` service runs the repo's custom image
(`docker/postgres-ssl-logs/`, built on Railway's official
`ghcr.io/railwayapp-templates/postgres-ssl:18`), which bundles
**pgBackRest**. Backups activate when the `WAL_ARCHIVE_*` env vars are set on
the service:

- **Continuous WAL archiving** (async, `archive-push-queue-max=5GiB`) — every
  WAL segment is shipped to object storage, giving point-in-time granularity.
- **Full base backups** every `WAL_BACKUP_FULL_INTERVAL_HOURS` (default 168 h
  = weekly).
- **Differential backups** every `WAL_BACKUP_DIFF_INTERVAL_HOURS` (default
  24 h).
- A background watcher (`pgbackrest-backup-watcher.sh` in the upstream image)
  takes the **initial backup automatically** and re-runs backups to close
  gaps if archiving falls behind.

Backups land in a **Railway Bucket** in the same environment, under
`/pgbackrest/cluster-<database-system-id>/`.

## Current configuration

| Environment | Bucket | Status |
|---|---|---|
| staging | `db-backups` (created 2026-06-12, region sjc) | **Active** |
| production | — | **NOT yet enabled** — see [Enabling on production](#enabling-on-production) |

Variables on the `pgvector` service (staging values shown as references):

| Variable | Value | Note |
|---|---|---|
| `WAL_ARCHIVE_BUCKET` | `${{ db-backups.BUCKET }}` | S3 bucket name (with Railway's hash suffix) |
| `WAL_ARCHIVE_KEY` | `${{ db-backups.ACCESS_KEY_ID }}` | |
| `WAL_ARCHIVE_SECRET` | `${{ db-backups.SECRET_ACCESS_KEY }}` | |
| `WAL_ARCHIVE_REGION` | `${{ db-backups.REGION }}` | `sjc` |
| `WAL_ARCHIVE_ENDPOINT` | `storage.railway.app` | **Literal, no `https://`** — pgBackRest wants a bare host; the bucket's `ENDPOINT` reference includes the scheme, so it can't be referenced directly |
| `WAL_ARCHIVE_S3_URI_STYLE` | `host` | **Required** — Railway Buckets use virtual-hosted-style URLs; the image's default is `path`, which fails against them |

## Verifying backups are healthy

1. **Archiver status** (cheapest check, from any psql/MCP session):
   ```sql
   SELECT archived_count, last_archived_wal, last_archived_time,
          failed_count, last_failed_wal
   FROM pg_stat_archiver;
   ```
   `archived_count` should grow over time and `last_archived_time` should be
   recent (within `archive_timeout`, 60 s, of the last write activity).
   A growing `failed_count` means archiving is broken — check service logs.
2. **Service logs** — the deploy/runtime logs show `pgbackrest` lines:
   stanza creation, `archive-push` results, and scheduled backup runs.
3. **Misconfiguration sentinel** — if the image rejected the bucket config it
   logs `invalid-bucket sentinel (reason=…)` and archiving is silently OFF.
   Grep the deploy logs for `pgbackrest` after every config change.

## Restore

> ⚠ Restores are exercised on **staging first**. Production restore follows
> the same steps with the production bucket/service.

### A. Point-in-time recovery (same service, same volume)

Use when bad data was written and you want to rewind the cluster.

1. Note the target time (UTC, ISO 8601), e.g. just before the bad deploy.
2. On the `pgvector` service, set:
   ```
   POSTGRES_RECOVERY_TARGET_TIME=2026-06-12T14:30:00+00:00
   ```
3. Redeploy the service. The image writes recovery config to
   `$PGDATA/conf.d/pgbackrest-recovery.conf`; Postgres enters archive
   recovery, replays WAL to the target, then promotes.
4. **Remove `POSTGRES_RECOVERY_TARGET_TIME`** after successful recovery so a
   later restart doesn't re-enter recovery.
5. Note: after a promote, a **new timeline** starts; the watcher takes a
   fresh full backup.

### B. Full restore to a NEW service (disaster recovery / drill)

Use when the volume is lost or you want a side-by-side copy (this is also the
restore-drill procedure).

1. Create a new Railway service from the same image
   (`docker/postgres-ssl-logs/`, or `ghcr.io/railwayapp-templates/postgres-ssl:18`)
   with a **fresh volume** mounted at `/var/lib/postgresql/data` and
   `PGDATA=/var/lib/postgresql/data/pgdata`.
2. Point it at the **source** cluster's backups with the recover-from family:
   ```
   WAL_RECOVER_FROM_BUCKET   = <source bucket name>        # e.g. db-backups-5ddktvrgp3vwo3
   WAL_RECOVER_FROM_KEY      = <source ACCESS_KEY_ID>
   WAL_RECOVER_FROM_SECRET   = <source SECRET_ACCESS_KEY>
   WAL_RECOVER_FROM_REGION   = <source region>             # sjc
   WAL_RECOVER_FROM_ENDPOINT = storage.railway.app
   WAL_RECOVER_FROM_S3_URI_STYLE = host
   WAL_RECOVER_FROM_PATH     = /pgbackrest/cluster-<sysid> # see bucket layout
   ```
   Optionally add `POSTGRES_RECOVERY_TARGET_TIME` for PITR into the copy.
3. Deploy; the image restores the latest base backup and replays WAL.
4. Verify: row counts on key tables (`messages`, `users`, `servers`),
   `SELECT max(created_at) FROM messages;` close to the incident time.
5. To **promote** the copy to be the real DB: update the bot's
   `DATABASE_URL`/`DB_*` to the new service (and enable `WAL_ARCHIVE_*` on it
   with a **new or emptied bucket path** — never have two clusters archiving
   to the same path).

### C. Revert the image itself (if postgres-ssl misbehaves)

Point the service source back to `pgvector/pgvector:pg18`, restore start
command `/bin/sh -c "unset PGPORT; docker-entrypoint.sh postgres --port=5432"`
(see `docker/postgres-ssl-logs/README.md`). Data on the volume is untouched;
this only swaps the runtime image. Backups stop while reverted.

## Enabling on production

Production is **not yet enabled** (requires a production-DB restart — do in a
quiet window):

1. Create a bucket in the **production** environment (e.g. `db-backups`).
2. Set the same six `WAL_ARCHIVE_*` variables on production `pgvector`
   (references to the production bucket; same literal endpoint + uri-style).
3. Deploy the `docker/postgres-ssl-logs/` image to production `pgvector`
   (`cd docker/postgres-ssl-logs && railway link … --environment production
   --service pgvector && railway up -d`).
4. Verify per [Verifying backups](#verifying-backups-are-healthy); confirm the
   initial full backup completes (watcher logs).
5. Schedule a restore drill (procedure B) within the first week.

## RPO / RTO

- **RPO**: ≤ ~60 s of writes (continuous WAL archiving with
  `archive_timeout=60`), assuming archiving is healthy — hence the
  `pg_stat_archiver` check above.
- **RTO**: a procedure-B restore is bounded by base-backup size + WAL replay;
  measure it during the first drill and record the number here.

## History

- **2026-06-12** — staging backups activated (bucket `db-backups`, image
  switched from `pgvector/pgvector:pg18` to the repo's postgres-ssl-logs
  image). Audit item 0.1 (G7 — previously the weakest finding: the only
  "backup" was a 0-byte dump).

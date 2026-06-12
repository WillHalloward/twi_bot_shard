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
| production | `db-backups-prod` (created 2026-06-12, region sjc) | **Active** — restore drill **PASSED** 2026-06-12 (see [History](#history)) |

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
restore-drill procedure). **Drilled successfully 2026-06-12 against the
production bucket** — the gotchas below are from that drill, learn from them.

1. Create a new Railway service from the same image
   (`docker/postgres-ssl-logs/`, or `ghcr.io/railwayapp-templates/postgres-ssl:18`)
   with a **fresh volume** mounted at `/var/lib/postgresql/data` and
   `PGDATA=/var/lib/postgresql/data/pgdata`.
2. Point it at the **source** cluster's backups with the recover-from family,
   **setting ALL variables before the first deploy onto the empty volume**
   (set them with deploys skipped / in one batch — see gotcha ⚠2):
   ```
   WAL_RECOVER_FROM_BUCKET   = <source bucket name>        # e.g. db-backups-prod-uxoh9zqh3
   WAL_RECOVER_FROM_KEY      = <source ACCESS_KEY_ID>
   WAL_RECOVER_FROM_SECRET   = <source SECRET_ACCESS_KEY>
   WAL_RECOVER_FROM_REGION   = <source region>             # sjc
   WAL_RECOVER_FROM_ENDPOINT = storage.railway.app
   WAL_RECOVER_FROM_S3_URI_STYLE = host
   WAL_RECOVER_FROM_PATH     = /pgbackrest/cluster-<sysid> # from "pgbackrest: using repo1-path=" in source logs
   POSTGRES_RECOVERY_TARGET_TIME = <ISO 8601, e.g. 2026-06-12 20:50:00+00:00>
   POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD = <match source>
   ```
   - ⚠1 **`POSTGRES_RECOVERY_TARGET_TIME` is REQUIRED, not optional** — the
     image's restore gate (`wrapper.sh` `restore_from_pgbackrest_if_empty_volume`)
     returns early without it and **silently falls through to a fresh initdb**.
     For "latest possible", pick a timestamp safely in the future of the last
     WAL flush — replay stops at end-of-archive.
   - ⚠2 **The volume must still be EMPTY when the fully-configured deploy
     boots.** Any boot with partial config initdb's a fresh cluster onto the
     volume, which permanently disarms the restore gate (`PG_VERSION` present
     → skip). If that happens: delete + recreate the volume and redeploy.
3. Deploy; the wrapper logs `restoring from source bucket (target=…)`,
   restores the base backup (`--delta --type=time --target-action=promote`),
   replays WAL to the target, and promotes. Confirm via the
   `pgbackrest: restore-gate …` log line — it prints exactly why the restore
   did or didn't run.
4. Verify (drilled method): give the copy a temporary TCP proxy
   (dashboard → service → Settings → TCP proxy, or the `tcpProxyCreate` API —
   note `railway ssh` mangles SQL quoting and won't forward stdin), then:
   - `SELECT pg_is_in_recovery();` → must be `false` (promoted)
   - **Exact-match check**: `SELECT count(*) FROM messages WHERE created_at <
     timestamp '<recovery target>';` must equal the same query on the live
     source — this is insert-only data, so the counts match exactly.
   - `SELECT max(created_at) FROM messages;` → just under the target time.
5. To **promote** the copy to be the real DB: update the bot's
   `DATABASE_URL`/`DB_*` to the new service (and enable `WAL_ARCHIVE_*` on it
   with a **new or emptied bucket path** — never have two clusters archiving
   to the same path). For a drill: tear down the service, its volume(s), and
   the TCP proxy.

### C. Revert the image itself (if postgres-ssl misbehaves)

Point the service source back to `pgvector/pgvector:pg18`, restore start
command `/bin/sh -c "unset PGPORT; docker-entrypoint.sh postgres --port=5432"`
(see `docker/postgres-ssl-logs/README.md`). Data on the volume is untouched;
this only swaps the runtime image. Backups stop while reverted.

## Production enablement notes (done 2026-06-12)

Production is **active**. Operational lessons from the enablement, for the
next environment or re-enablement:

- **Set the start command explicitly** (`/usr/local/bin/pg-log-entrypoint.sh`)
  on the service — the first prod deploy kept the old dashboard start command
  (`docker-entrypoint.sh postgres`), which **bypasses `wrapper.sh` entirely**:
  Postgres ran fine but SSL/pgBackRest init silently never happened. The
  tell-tale: no `pgbackrest:` lines and raw (unshipped) log format.
- **Collation check after image swaps**: a transient deployment ran a
  glibc-2.36 runtime against the 2.41-initialized cluster (warnings:
  "collation version mismatch"). Remediated 2026-06-12: `REINDEX INDEX
  CONCURRENTLY` on all 22 collation-dependent indexes (49 s) +
  `ALTER DATABASE railway REFRESH COLLATION VERSION` + `ALTER COLLATION
  "en_US"/"en_US.utf8" REFRESH VERSION`. Verify with:
  `SELECT count(*) FROM pg_collation WHERE collprovider='c' AND collversion
  IS DISTINCT FROM pg_collation_actual_version(oid);` → must be 0.
  (The image's own `collation-refresh` hook currently fails with a /tmp
  permission error — upstream bug, do it manually.)

## RPO / RTO (measured)

- **RPO**: ≤ ~60 s of writes (continuous WAL archiving with
  `archive_timeout=60`), assuming archiving is healthy — hence the
  `pg_stat_archiver` check above.
- **RTO** (measured in the 2026-06-12 drill, 13 GB database): **~9.5 min**
  machine time — 8 m 06 s base-backup restore from the bucket + ~1.5 min WAL
  replay & promote — plus operator time to create the service/volume/vars.
  First full backup of the 13 GB prod DB took 4 m 54 s.

## History

- **2026-06-12** — staging backups activated (bucket `db-backups`, image
  switched from `pgvector/pgvector:pg18` to the repo's postgres-ssl-logs
  image). Audit item 0.1 (G7 — previously the weakest finding: the only
  "backup" was a 0-byte dump).
- **2026-06-12 (evening)** — production backups activated (bucket
  `db-backups-prod`); start-command and collation remediations applied (see
  enablement notes). First full backup 13 GB / 294 s.
- **2026-06-12 (evening)** — **restore drill PASSED**: PITR restore of the
  production backup to a throwaway service (`target=20:50:00Z`,
  `--target-action=promote`). Verification: time-filtered message count
  matched live production **exactly** (19,005,224 = 19,005,224), users exact
  (23,061), `max(created_at)` = 20:49:36 (< target), promoted cleanly.
  Drill service/volumes/proxy torn down after. (One detached 0 MB drill
  volume resisted API deletion — harmless; remove via dashboard if it
  lingers.)

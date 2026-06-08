# Observability & Monitoring (Sentry)

Runtime error reporting and liveness monitoring run through
[Sentry](https://sentry.io). The integration lives in `utils/sentry_setup.py`
and is **a no-op unless `SENTRY_DSN` is set**, so local development and the test
suite are unaffected.

## Initialisation

`init_sentry()` is called early in `main.py` (right after logging is configured).
It is gated on `SENTRY_DSN` and tags every event with the deployment
`environment` and the git SHA as the `release`. Defaults are
privacy-conservative:

- `send_default_pii=False`
- performance tracing off (`traces_sample_rate=0.0`, tunable via
  `SENTRY_TRACES_SAMPLE_RATE`)

See the [Sentry environment variables](../developer/environment-variables.md#observability-sentry)
for configuration.

## Error Reporting

`capture_exception()` is fired from:

- the `log_error()` choke point in `utils/error_handling.py` (so it rides on the
  same filter that excludes expected errors like cooldowns, check-failures, and
  `CognitaError`), and
- the other escalation paths wired in `setup_global_exception_handler()`: the
  `sys.excepthook`, the `on_error` event-dispatch handler (listeners), and the
  asyncio `loop.set_exception_handler` (fire-and-forget tasks), and
- the background `@tasks.loop` `.error` handlers, which call it directly.

See [Error Handling → Global Error Handlers](../developer/error-handling.md#global-error-handlers)
for the full picture of the five escalation paths.

A `before_send` hook runs the event's exception value and log message through
`redact_sensitive_info()`, so secrets are scrubbed before leaving the process.

> **Note:** `before_send` does **not** scrub stack-frame local variables — rely
> on Sentry's server-side data-scrubbing for those, or set
> `include_local_variables=False` if needed.

Sentry's default integrations are left enabled deliberately: the
`LoggingIntegration` is a secondary net that turns any ERROR-level log into an
event. **Do not** pass `integrations=[...]` or `default_integrations=False`
without first adding explicit `capture_exception()` calls for any path that
relies on it (see the note in `utils/sentry_setup.py`).

## Liveness Heartbeat

`cogs/heartbeat.py` is a dead-man's-switch for the "unreachable but not throwing
errors" failure mode (hang, OOM-kill, silent gateway disconnect). While
connected, the bot sends a Sentry cron check-in every 5 minutes
(`send_heartbeat()`, monitor slug `twi-bot-heartbeat`, created automatically on
first check-in).

Sentry — externally — raises a missed check-in issue after ~15 min (interval 5 +
margin 10) when the check-ins stop. Because the alert is driven by Sentry
reacting to the *absence* of a signal, it fires even when the bot itself is dead.

The cog loads in staging/production (not in test mode, where the loop is
skipped).

## Configuration & Alerting

`SENTRY_DSN` is set as a Railway env var on both the `staging` and `production`
environments (same DSN; the `environment` tag differentiates them). Issues route
to Discord via Sentry **issue-alert rules** ("a new issue is created", filtered
per environment) configured in the Sentry UI — the MCP/API does not create alert
rules.

## Gotcha

Running code locally with `SENTRY_DSN` set will report uncaught exceptions to the
shared project via Sentry's default excepthook integration. Normal local dev tags
them `development` (ignored by the staging/production alert rules), but manual
test scripts that force `environment='staging'`/`'production'` will trip the real
Discord alerts. Tag throwaway test events with a distinct environment (e.g.
`local-test`).

## Database observability

The database is the easiest layer to be blind to, because the app-side timer in
`utils/db.py` measures **connection-acquire wait + query execution together**.
A "slow query" on a trivial statement is therefore usually *pool contention*
(waiting for a free connection), not a slow query. Visibility comes from three
layers — app, pool, and the Postgres server.

### What the bot already records (code, always on)

- **Slow-query log** (`utils/db.py`, threshold 0.5s): every query method warns
  when total time exceeds the threshold. The warning carries a
  `[pool: X in use, Y idle, Z open, M max]` suffix so you can tell *why* it was
  slow (the timer wraps acquire + execution together):
  - `in use == max` → **saturation**, the query waited for a connection;
  - `open == 0` → **cold connect**, the pool had drained to empty and had to
    open a fresh (TLS) connection — the usual cause of a one-off multi-second
    "slow" trivial query (see the note on `max_inactive_connection_lifetime`
    below);
  - otherwise → the **query/server itself** was genuinely slow.
- **Pool utilisation** (`utils/resource_monitor.py`): the resource monitor is
  handed the asyncpg pool and records `db_pool_size` / `db_pool_idle` /
  `db_pool_in_use` / `db_pool_max` each cycle, and emits a
  `DB connection pool saturated` warning only when **in-use reaches max** (not
  merely when idle is 0 — a quiescent pool also reports 0 idle).

> **Why the pool often shows 0 open/idle:** the pool is created with
> `max_inactive_connection_lifetime=180.0` (`main.py`), so after ~3 min without
> DB activity asyncpg closes its idle connections and the pool shrinks toward 0.
> The next query then pays a cold-connection (TLS handshake) cost, which the
> app-side timer attributes to that query. If cold-connect latency becomes a
> problem, raise/disable that lifetime or add a periodic keepalive query so a
> warm connection is always available. Pool is min 5 / max 20.

### Layer 1 — Sentry query tracing (lowest effort, highest value)

The asyncpg integration already emits `op:db origin:auto.db.asyncpg` spans
(visible in the `trace` block of any captured event) — they are just dropped
because sampling is off. To turn on the **Queries** insights dashboard
(slowest/most-frequent queries, per-command timing, N+1 detection):

1. On Railway, set `SENTRY_TRACES_SAMPLE_RATE` to a small value (e.g. `0.1`) on
   the `staging` / `production` service. No deploy needed — restart the service.
2. Open Sentry → **Insights → Queries** for the project. Start low (0.05–0.1):
   tracing consumes quota and adds slight overhead. Query *parameters* are not
   captured (`send_default_pii=False` + parameterised SQL).

### Layer 2 — `pg_stat_statements` (authoritative server-side truth)

The canonical Postgres tool: aggregates every normalised query with call count,
total/mean/max time, rows, and cache-hit ratio. One-time setup on the Railway
Postgres service:

1. Add `pg_stat_statements` to `shared_preload_libraries` (Railway Postgres
   service config) and restart the DB.
2. Once: `CREATE EXTENSION IF NOT EXISTS pg_stat_statements;`
3. Read the top offenders any time:
   ```sql
   SELECT calls, total_exec_time, mean_exec_time, max_exec_time, rows, query
   FROM pg_stat_statements
   ORDER BY total_exec_time DESC
   LIMIT 20;
   ```
   (`total_exec_time` = biggest cumulative cost; `mean_exec_time` = slowest per
   call.) Reset the counters with `SELECT pg_stat_statements_reset();`.

### Layer 3 — server-side slow log + plans (why a query is slow)

On the Railway Postgres service, set:

- `log_min_duration_statement = 500` — logs any statement over 500ms
  (authoritative execution time, no pool-wait noise).
- `auto_explain` (add to `shared_preload_libraries`) with
  `auto_explain.log_min_duration = '500ms'` and `auto_explain.log_analyze = on`
  — captures the actual `EXPLAIN ANALYZE` plan for slow statements, surfacing
  missing indexes / sequential scans.

For ad-hoc investigation of a specific query, run
`EXPLAIN (ANALYZE, BUFFERS) <query>;` against the DB.

### Live "what's happening right now"

```sql
-- currently-running queries and what they're waiting on
SELECT pid, now() - query_start AS duration, wait_event_type, wait_event, query
FROM pg_stat_activity
WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%'
ORDER BY duration DESC;

-- blocked / blocking locks
SELECT * FROM pg_locks WHERE NOT granted;
```

### Triage flow for a slow-query warning

1. Read the `[pool: …]` suffix. `in use == max` → contention (raise pool
   `max_size` in `main.py` or reduce concurrent DB work). `open == 0` → cold
   connect after the pool drained (see the `max_inactive_connection_lifetime`
   note above) — not a query problem. Otherwise the query/server was genuinely
   slow; continue below.
2. Find the query in **Sentry → Queries** or `pg_stat_statements` to see how
   often it runs and its true execution time.
3. If genuinely slow, `EXPLAIN (ANALYZE, BUFFERS)` it (or read the `auto_explain`
   plan) to find the missing index / scan.

## Related Documentation

- [Error Handling](../developer/error-handling.md) — exception hierarchy and escalation paths
- [Environment Variables](../developer/environment-variables.md#observability-sentry) — `SENTRY_*` configuration
- [Deployment](deployment.md) — Railway environment setup

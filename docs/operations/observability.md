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

## Related Documentation

- [Error Handling](../developer/error-handling.md) — exception hierarchy and escalation paths
- [Environment Variables](../developer/environment-variables.md#observability-sentry) — `SENTRY_*` configuration
- [Deployment](deployment.md) — Railway environment setup

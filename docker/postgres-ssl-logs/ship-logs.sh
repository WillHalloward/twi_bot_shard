#!/usr/bin/env bash
#
# Read Postgres' JSON log lines on stdin and re-emit them on stdout with a
# `level` field Railway recognises. Postgres' jsonlog carries `error_severity`
# (LOG / WARNING / ERROR / FATAL / DEBUGx / ...) which Railway ignores; mapping
# it to debug|info|warn|error makes the log explorer colour each line by its
# real severity instead of treating every stderr line as an error.
#
# Non-JSON lines (e.g. wrapper.sh's SSL/backup setup output, or a few very early
# startup messages before jsonlog is active) are wrapped as info so nothing is
# lost.
#
# Wrapped in a restart loop so a transient jq failure can never propagate a
# broken pipe back to Postgres (which writes its logs to our stdin); the small
# sleep prevents a tight loop if jq exits immediately at shutdown.
set -uo pipefail

while true; do
    jq -cR --unbuffered '
        (fromjson? // {message: ., error_severity: "LOG"})
        | (.error_severity // "LOG" | ascii_downcase) as $sev
        | .level = (
            if   ($sev | startswith("debug")) then "debug"
            elif  $sev == "warning"           then "warn"
            elif ($sev == "error" or $sev == "fatal" or $sev == "panic") then "error"
            else "info" end)
    ' || true
    sleep 0.5
done

#!/usr/bin/env bash
#
# Boot Postgres through the postgres-ssl image's own wrapper.sh so its SSL and
# pgBackRest setup still run, but with JSON logging on stderr routed through the
# log shipper — giving Railway per-line severity instead of all-red.
#
# wrapper.sh ends with `exec docker-entrypoint.sh "$@"`, so the args below are
# forwarded to Postgres. We replicate the image's default CMD
# (`postgres -p 5432 -c listen_addresses=*`) and add the jsonlog flags.
#
# Postgres remains the main (PID 1) process via the exec chain, so Railway's
# SIGTERM reaches it for a graceful shutdown. The shipper runs as a process
# substitution wired to fd 2; its stdout is inherited from this script (the
# container's stdout), which is where the normalised log lines land.
set -uo pipefail

# Railway injects PGPORT (libpq); the image already targets 5432, but unset it
# defensively so the server can't bind to the wrong port.
unset PGPORT

exec /usr/local/bin/wrapper.sh postgres \
    -p 5432 \
    -c listen_addresses='*' \
    -c log_destination=jsonlog \
    -c logging_collector=off \
    2> >(exec /usr/local/bin/ship-logs.sh)

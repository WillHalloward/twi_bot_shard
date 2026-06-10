# Railway's official Postgres image (postgres-ssl) with Railway-friendly logs.
#
# postgres-ssl already bundles everything we need: pgvector, jq, automatic SSL,
# and pgBackRest-based backups (the latter stays dormant until WAL_ARCHIVE_*
# env vars are set). What it does NOT do is colour logs — its wrapper.sh leaves
# Postgres logging at the default (all-stderr, which Railway paints red).
#
# So we layer a thin entrypoint on top that boots Postgres *through* the image's
# own wrapper.sh — preserving its SSL/backup setup — but with jsonlog on stderr
# piped through jq, which adds a Railway-recognised `level` field per line.
#
# Pin to pg18 to match the current data cluster's major version.
FROM ghcr.io/railwayapp-templates/postgres-ssl:18

COPY pg-log-entrypoint.sh /usr/local/bin/pg-log-entrypoint.sh
COPY ship-logs.sh /usr/local/bin/ship-logs.sh
RUN chmod +x /usr/local/bin/pg-log-entrypoint.sh /usr/local/bin/ship-logs.sh

# jq ships in the base image, so no extra package install is needed.
# ENTRYPOINT here is only a fallback; Railway runs the start command from
# railway.toml, which points at the same script.
ENTRYPOINT ["/usr/local/bin/pg-log-entrypoint.sh"]

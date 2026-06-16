"""Real-Postgres integration tests.

These tests run against an actual PostgreSQL server (the production engine),
not the SQLite/mock stand-ins the rest of the suite uses. They exist because
the audit (findings/12 E7) found the unit suite could not reproduce any of the
four production DB bug classes — non-idempotent inserts, naive-local
timestamps, asyncpg-dialect SQL, and non-atomic multi-writes — because every
SQL string terminated in a mock or an incompatible SQLite engine.

They are gated on the ``TEST_DATABASE_URL`` environment variable: unset (local
dev, the default unit run) → skipped; set (CI's Postgres service container) →
run against the real schema applied from ``database/init.sql`` +
``database/optimizations/base.sql``.
"""

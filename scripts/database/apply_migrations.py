#!/usr/bin/env python3
"""Apply pending SQL schema migrations, tracked in a schema_migrations table.

Designed to run as a Railway pre-deploy step so code and database schema stay
in sync. Migrations live in ``database/schema/migrations/*.sql`` and are applied
in filename order (use a sortable ``YYYYMMDD_description.sql`` prefix).

Behaviour
---------
* Ensures a ``schema_migrations`` tracking table exists.
* Migrations listed in ``MANUAL_MIGRATIONS`` are **recorded as applied without
  being executed**. Use this for heavy / table-locking migrations that must be
  run by hand in a maintenance window (e.g. type changes, sequence rewrites,
  materialized-view rebuilds). The runner must never lock production tables
  unexpectedly during a deploy.
* Every other migration not yet recorded is executed inside a transaction and
  then recorded.

Requirements for migrations
---------------------------
* Idempotent (``IF NOT EXISTS`` / guarded ``DO`` blocks) so an interrupted or
  retried deploy is safe, and so a migration that was already applied by hand
  is harmless to re-run.
* Single-transaction safe — statements that cannot run inside a transaction
  (e.g. ``CREATE INDEX CONCURRENTLY``) must be added to ``MANUAL_MIGRATIONS``
  and run by hand.

Usage
-----
    python scripts/database/apply_migrations.py            # apply pending
    python scripts/database/apply_migrations.py --dry-run  # show plan only

Requires ``DATABASE_URL`` in the environment.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2] / "database" / "schema" / "migrations"
)

# Migrations applied by hand in a maintenance window, never by the auto-runner.
# The runner records them as applied (so they don't show as pending) but does
# not execute them. Add heavy / table-locking / non-transactional migrations
# here.
MANUAL_MIGRATIONS: frozenset[str] = frozenset(
    {
        "20260405_database_design_cleanup.sql",
    }
)

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def _normalize_dsn(dsn: str) -> str:
    """Normalize a SQLAlchemy-style URL to a plain asyncpg DSN."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )


def _discover_migrations() -> list[Path]:
    """Return migration files sorted by filename (chronological prefix order)."""
    if not MIGRATIONS_DIR.is_dir():
        return []
    return sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())


async def apply_migrations(dry_run: bool = False) -> int:
    """Apply pending migrations. Returns the number executed (-1 on config error)."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return -1

    migrations = _discover_migrations()
    if not migrations:
        print(f"No migration files found in {MIGRATIONS_DIR}")
        return 0

    conn = await asyncpg.connect(_normalize_dsn(dsn))
    try:
        await conn.execute(CREATE_TRACKING_TABLE)
        recorded = {
            row["filename"]
            for row in await conn.fetch("SELECT filename FROM schema_migrations")
        }

        applied = 0
        for migration in migrations:
            name = migration.name
            if name in recorded:
                continue

            if name in MANUAL_MIGRATIONS:
                print(f"Recording manual migration (not executed): {name}")
                if not dry_run:
                    await conn.execute(
                        "INSERT INTO schema_migrations(filename) VALUES ($1) "
                        "ON CONFLICT DO NOTHING",
                        name,
                    )
                continue

            print(f"Applying migration: {name}")
            if dry_run:
                continue
            async with conn.transaction():
                await conn.execute(migration.read_text())
                await conn.execute(
                    "INSERT INTO schema_migrations(filename) VALUES ($1)", name
                )
            applied += 1
            print(f"  ✓ applied {name}")

        if applied == 0:
            print("Schema is up to date; no migrations executed.")
        else:
            print(f"Done. Executed {applied} migration(s).")
        return applied
    finally:
        await conn.close()


def main() -> int:
    """CLI entry point."""
    dry_run = "--dry-run" in sys.argv
    result = asyncio.run(apply_migrations(dry_run=dry_run))
    return 1 if result < 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

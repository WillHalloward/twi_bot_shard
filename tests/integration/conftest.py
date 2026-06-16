"""Fixtures for real-Postgres integration tests.

Gated on ``TEST_DATABASE_URL`` (an asyncpg-style DSN, e.g.
``postgresql://postgres:postgres@localhost:5432/twibot_test``). When it is
unset every test in this package is skipped, so local unit runs and developers
without a Postgres are unaffected; CI sets it to its service container.

The schema is bootstrapped once per session from the real SQL the bot ships —
``database/init.sql`` (tables) then ``database/optimizations/base.sql``
(constraints, indexes, materialized views, the refresh function) — plus the
``mentions`` partial unique indexes from migration ``20260613_01`` (created
non-concurrently here; CONCURRENTLY is only needed against a live, populated
table). This mirrors the production schema closely enough that the dialect,
constraint, and timestamp behaviours under test are the real ones.
"""

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import asyncpg
import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from utils.db import Database

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INIT_SQL = _REPO_ROOT / "database" / "init.sql"
_BASE_SQL = _REPO_ROOT / "database" / "optimizations" / "base.sql"

# Mentions partial unique indexes (migration 20260613_01), CONCURRENTLY dropped
# — a fresh test table builds them instantly and inside the bootstrap path.
_MENTIONS_UNIQUE_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS mentions_message_user_uindex
    ON mentions (message_id, user_mention) WHERE user_mention IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS mentions_message_role_uindex
    ON mentions (message_id, role_mention) WHERE role_mention IS NOT NULL;
"""

# Tables the integration tests read/write — truncated between tests for
# isolation. RESTART IDENTITY resets the serial sequences; CASCADE clears
# FK-dependent rows in one statement.
_TABLES_TO_CLEAN = (
    "attachments",
    "mentions",
    "reactions",
    "messages",
    "users",
    "servers",
    "channels",
    "roles",
    "poll_option",
    "invisible_text_twi",
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


async def _apply_schema(conn: asyncpg.Connection) -> None:
    """Apply the production schema to a fresh database (idempotent)."""
    conn_exec = conn.execute
    await conn_exec(_INIT_SQL.read_text())
    await conn_exec(_BASE_SQL.read_text())
    await conn_exec(_MENTIONS_UNIQUE_SQL)


# The schema is DB state, applied exactly once across the session. The pool is
# function-scoped so it lives on each test's own event loop (asyncpg pools are
# loop-bound, and pytest-asyncio's default loop scope is function — a
# session-scoped async fixture would raise ScopeMismatch). Bootstrapping is
# idempotent (CREATE ... IF NOT EXISTS), so the guard is an optimisation, not a
# correctness requirement.
_schema_applied = False


@pytest_asyncio.fixture
async def pg_pool() -> AsyncIterator[asyncpg.Pool]:
    """Function-scoped asyncpg pool; schema bootstrapped once per session."""
    global _schema_applied
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")  # safety net beyond module skipif
    pool = await asyncpg.create_pool(TEST_DATABASE_URL, min_size=1, max_size=4)
    if not _schema_applied:
        async with pool.acquire() as conn:
            await _apply_schema(conn)
        _schema_applied = True
    try:
        yield pool
    finally:
        await pool.close()


@pytest_asyncio.fixture
async def clean_db(pg_pool: asyncpg.Pool) -> AsyncIterator[asyncpg.Pool]:
    """Truncate the worked tables before each test for isolation."""
    async with pg_pool.acquire() as conn:
        await conn.execute(
            f"TRUNCATE {', '.join(_TABLES_TO_CLEAN)} RESTART IDENTITY CASCADE"
        )
    yield pg_pool


@pytest_asyncio.fixture
async def real_db(clean_db: asyncpg.Pool) -> "Database":
    """The bot's real ``utils.db.Database`` over the test pool (clean tables).

    Imported lazily inside the fixture: the root conftest's ``clean_imports``
    autouse fixture purges ``utils.db`` from ``sys.modules`` between tests, so a
    module-level import could bind a stale incarnation.
    """
    from utils.db import Database

    return Database(clean_db)

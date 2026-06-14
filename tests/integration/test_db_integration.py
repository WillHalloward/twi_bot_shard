"""Real-Postgres integration tests for the four production DB bug classes.

The audit (findings/12 E7) showed the unit suite is structurally blind to these
because every SQL string terminates in a mock or SQLite. Each test here runs the
real bot code / real SQL against a real PostgreSQL engine:

1. Idempotency — ``save_message`` re-delivery must not duplicate attachment /
   mention rows (the ON CONFLICT fix, audit 1.2 / C8-1 / G1).
2. Timestamps — code-generated timestamps must be UTC even on a non-UTC host
   (audit 1.3 / G9). Verified by running under TZ=America/Los_Angeles.
3. asyncpg-dialect SQL — ``= ANY($1::bigint[])``, ``plainto_tsquery``,
   ``SIMILAR TO``, and materialized-view refresh must parse and run (SQLite
   cannot represent any of these).
4. Atomicity — ``save_message``'s multi-write sequence should leave no partial
   rows on mid-sequence failure (audit 2.6, not yet shipped → xfail).
"""

import datetime
import os
import time
import types
from collections.abc import AsyncIterator

import asyncpg
import pytest

# Gate at collection: marker for filtering + skip the whole module when no real
# Postgres is configured (local unit runs, developers without a DB). CI sets
# TEST_DATABASE_URL to its service container. (A conftest pytestmark does not
# apply skips to test items, so the skipif must live on the test module.)
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL not set; real-Postgres integration tests skipped",
    ),
]

UTC = datetime.UTC


# --------------------------------------------------------------------------- #
# Lightweight discord.Message stand-ins (only the attributes save_message reads)
# --------------------------------------------------------------------------- #
class _Attachment:
    def __init__(self, aid: int) -> None:
        self.id = aid
        self.filename = f"file_{aid}.png"
        self.url = f"https://cdn.discordapp.com/attachments/{aid}.png"
        self.size = 1234
        self.height = 10
        self.width = 20
        self._spoiler = False

    def is_spoiler(self) -> bool:
        return self._spoiler


def _make_message(
    *,
    message_id: int = 5001,
    author_id: int = 4001,
    guild_id: int = 3001,
    channel_id: int = 2001,
    attachments: list[int] | None = None,
    user_mentions: list[int] | None = None,
    role_mentions: list[int] | None = None,
) -> types.SimpleNamespace:
    """Build a minimal object exposing exactly what save_message accesses."""
    aware = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    author = types.SimpleNamespace(
        id=author_id, name="tester", bot=False, created_at=aware, display_name="Tester"
    )
    guild = types.SimpleNamespace(id=guild_id, name="Guild", created_at=aware)
    channel = types.SimpleNamespace(id=channel_id, name="general")
    return types.SimpleNamespace(
        id=message_id,
        created_at=aware,
        content="hello world",
        jump_url=f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}",
        reference=None,
        author=author,
        guild=guild,
        channel=channel,
        attachments=[_Attachment(a) for a in (attachments or [])],
        mentions=[types.SimpleNamespace(id=u) for u in (user_mentions or [])],
        role_mentions=[types.SimpleNamespace(id=r) for r in (role_mentions or [])],
    )


def _bot(real_db) -> types.SimpleNamespace:
    return types.SimpleNamespace(db=real_db)


async def _count(db, table: str, where: str = "", *args) -> int:
    clause = f" WHERE {where}" if where else ""
    result = await db.fetchval(
        f"SELECT count(*) FROM {table}{clause}", *args, use_cache=False
    )
    return int(result)


# --------------------------------------------------------------------------- #
# 1. Idempotency
# --------------------------------------------------------------------------- #
class TestIdempotency:
    @pytest.mark.asyncio
    async def test_save_message_twice_does_not_duplicate_children(
        self, real_db
    ) -> None:
        from cogs.stats_listeners import save_message

        msg = _make_message(
            attachments=[9001, 9002],
            user_mentions=[7001, 7002],
            role_mentions=[6001],
        )
        bot = _bot(real_db)

        await save_message(bot, msg)
        await save_message(bot, msg)  # re-delivery / backfill overlap

        assert await _count(real_db, "messages", "message_id=$1", msg.id) == 1
        assert await _count(real_db, "attachments", "message_id=$1", msg.id) == 2
        assert (
            await _count(
                real_db,
                "mentions",
                "message_id=$1 AND user_mention IS NOT NULL",
                msg.id,
            )
            == 2
        )
        assert (
            await _count(
                real_db,
                "mentions",
                "message_id=$1 AND role_mention IS NOT NULL",
                msg.id,
            )
            == 1
        )

    @pytest.mark.asyncio
    async def test_mentions_partial_unique_index_is_real(self, real_db) -> None:
        """A raw duplicate (no ON CONFLICT) must raise — proves the DB constraint
        exists, not just app-level dedup."""
        # Parent rows first (messages has an FK to servers).
        await real_db.execute(
            "INSERT INTO servers(server_id) VALUES($1) ON CONFLICT DO NOTHING", 3001
        )
        await real_db.execute(
            "INSERT INTO messages(message_id, created_at, server_name, server_id, channel_id, jump_url, is_bot) "
            "VALUES($1, now(), 'g', $2, $3, 'u', false)",
            8801,
            3001,
            2001,
        )
        await real_db.execute(
            "INSERT INTO mentions(message_id, user_mention) VALUES($1, $2)", 8801, 7777
        )
        # The bot's Database wraps asyncpg errors in DatabaseError; assert the
        # wrapper and that its cause is the real unique-constraint violation.
        from utils.db import DatabaseError

        with pytest.raises(DatabaseError) as exc_info:
            await real_db.execute(
                "INSERT INTO mentions(message_id, user_mention) VALUES($1, $2)",
                8801,
                7777,
            )
        assert isinstance(exc_info.value.__cause__, asyncpg.UniqueViolationError)


# --------------------------------------------------------------------------- #
# 2. Timestamps stored as UTC even on a non-UTC host
# --------------------------------------------------------------------------- #
class TestTimestampUTC:
    @pytest.mark.asyncio
    async def test_reaction_timestamp_is_utc_under_nonutc_tz(self, real_db) -> None:
        from cogs.stats_listeners import save_reaction

        async def _users() -> AsyncIterator[types.SimpleNamespace]:
            yield types.SimpleNamespace(id=4242)

        reaction = types.SimpleNamespace(
            emoji="👍",
            message=types.SimpleNamespace(id=5151),
            users=_users,
        )

        old_tz = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "America/Los_Angeles"  # UTC-7/8; exposes naive-local bug
            time.tzset()
            before = datetime.datetime.now(UTC).replace(tzinfo=None)
            await save_reaction(_bot(real_db), reaction)
            after = datetime.datetime.now(UTC).replace(tzinfo=None)
        finally:
            if old_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old_tz
            time.tzset()

        stored = await real_db.fetchval(
            "SELECT date FROM reactions WHERE message_id=$1", 5151, use_cache=False
        )
        assert stored is not None
        assert stored.tzinfo is None, "column is timezone-naive UTC by contract"
        # If the code used naive LOCAL time, `stored` would be ~7-8h behind UTC.
        assert before <= stored <= after, (
            f"stored timestamp {stored} not within UTC window [{before}, {after}] "
            "— naive-local-time regression (G9)"
        )


# --------------------------------------------------------------------------- #
# 3. asyncpg-dialect SQL
# --------------------------------------------------------------------------- #
class TestDialectSQL:
    @pytest.mark.asyncio
    async def test_any_bigint_array(self, real_db) -> None:
        for uid in (101, 102, 103):
            await real_db.execute(
                "INSERT INTO users(user_id, username) VALUES($1, $2)", uid, f"u{uid}"
            )
        # Faithful to stats_commands.py:73 — the asyncpg array idiom SQLite can't run.
        rows = await real_db.fetch(
            "SELECT user_id FROM users WHERE user_id = ANY($1::bigint[]) ORDER BY user_id",
            [101, 103, 999],
            use_cache=False,
        )
        assert [r["user_id"] for r in rows] == [101, 103]

    @pytest.mark.asyncio
    async def test_plainto_tsquery(self, real_db) -> None:
        # $3 (not a reused $2) for the tsvector text: a parameter used as both a
        # varchar column value and to_tsvector's text arg trips asyncpg's
        # "inconsistent types deduced" type inference.
        await real_db.execute(
            "INSERT INTO poll_option(option_id, option_text, tokens) "
            "VALUES($1, $2, to_tsvector('english', $3))",
            1,
            "the wandering inn chapter",
            "the wandering inn chapter",
        )
        rows = await real_db.fetch(
            "SELECT option_id FROM poll_option WHERE tokens @@ plainto_tsquery($1)",
            "wandering",
            use_cache=False,
        )
        assert [r["option_id"] for r in rows] == [1]

    @pytest.mark.asyncio
    async def test_similar_to(self, real_db) -> None:
        await real_db.execute(
            "INSERT INTO invisible_text_twi(serial_id, title, content) VALUES($1, $2, $3)",
            1,
            "Chapter 1.05",
            "secret",
        )
        # Faithful to twi.py:778 — SIMILAR TO is core Postgres, absent in SQLite.
        rows = await real_db.fetch(
            "SELECT title FROM invisible_text_twi WHERE lower(title) similar to lower($1)",
            "chapter 1.0%",
            use_cache=False,
        )
        assert [r["title"] for r in rows] == ["Chapter 1.05"]

    @pytest.mark.asyncio
    async def test_refresh_materialized_views(self, real_db) -> None:
        # base.sql defines the matviews + refresh_materialized_views(); cogs/stats.py
        # calls it. Verify it runs against a real engine (SQLite has no matviews).
        await real_db.execute("SELECT refresh_materialized_views()")
        exists = await real_db.fetchval(
            "SELECT count(*) FROM pg_matviews WHERE matviewname = 'daily_message_stats'",
            use_cache=False,
        )
        assert exists == 1


# --------------------------------------------------------------------------- #
# 4. Atomicity (known gap — save_message is not yet transactional, backlog 2.6)
# --------------------------------------------------------------------------- #
class TestAtomicity:
    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="save_message is not wrapped in a transaction yet (backlog 2.6); "
        "a mid-sequence failure leaves the message row orphaned. Flip to a plain "
        "assertion when 2.6 lands.",
        strict=False,
    )
    async def test_mid_sequence_failure_leaves_no_partial_rows(self, real_db) -> None:
        from cogs.stats_listeners import save_message

        msg = _make_message(message_id=5252, user_mentions=[7001])
        bot = _bot(real_db)

        original_execute_many = real_db.execute_many

        async def failing_execute_many(query: str, *args, **kwargs) -> None:
            if "INSERT INTO mentions" in query:
                raise asyncpg.PostgresError("injected mid-sequence failure")
            await original_execute_many(query, *args, **kwargs)

        real_db.execute_many = failing_execute_many
        try:
            with pytest.raises(asyncpg.PostgresError):
                await save_message(bot, msg)
        finally:
            real_db.execute_many = original_execute_many

        # Desired (transactional) behaviour: the whole save rolled back.
        assert await _count(real_db, "messages", "message_id=$1", msg.id) == 0

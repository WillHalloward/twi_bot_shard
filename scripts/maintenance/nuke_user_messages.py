#!/usr/bin/env python
# ruff: noqa: D205,D212,D301,D103,E501
r"""DANGER — Permanent deletion script for user 131894958759215106. See below.

╔══════════════════════════════════════════════════════════════════════════════╗
║         DANGER — PERMANENT DELETION SCRIPT — DO NOT RUN CARELESSLY          ║
║                                                                              ║
║  Target user  : 131894958759215106                                           ║
║  Operation    : Delete all messages from Discord + database                  ║
║  Reversibility: NONE — this is permanent and cannot be undone                ║
╚══════════════════════════════════════════════════════════════════════════════╝

One-off script to honour a banned user's request to have their messages removed.
This is NOT a bot command and cannot be triggered accidentally through Discord.

TWO-PHASE PROCESS
─────────────────
Phase 1  Delete each message from Discord via the HTTP API.
         Each successfully deleted message is marked deleted=True in the DB.
         The script is resumable — re-run to continue after interruption.

Phase 2  Hard-delete message rows (and related attachments / reactions) from
         the PostgreSQL database for the target user.
         Only run AFTER phase 1 has completed (or if you do not need Discord
         deletion).

REQUIRED SAFETY GATES (ALL must be satisfied to execute)
──────────────────────────────────────────────────────────
  1. --phase 1  or  --phase 2  must be specified
  2. --execute  flag must be present   (default is a safe dry-run preview)
  3. --confirm "I CONFIRM DELETE 131894958759215106"  must match exactly
  4. Interactive y/N prompt shown after stats — must type "yes" to proceed

USAGE EXAMPLES
──────────────
  # See what phase 1 would do (safe, no changes):
  python scripts/maintenance/nuke_user_messages.py --phase 1

  # Run phase 1 for real:
  python scripts/maintenance/nuke_user_messages.py --phase 1 --execute \\
      --confirm "I CONFIRM DELETE 131894958759215106"

  # Resume phase 1 after an interruption (skips already-deleted messages):
  python scripts/maintenance/nuke_user_messages.py --phase 1 --execute \\
      --confirm "I CONFIRM DELETE 131894958759215106"

  # Run phase 2 after phase 1 is complete:
  python scripts/maintenance/nuke_user_messages.py --phase 2 --execute \\
      --confirm "I CONFIRM DELETE 131894958759215106"

TEST MODES  (--phase 1 only, no passphrase required)
─────────────────────────────────────────────────────
Test modes let you verify that the bot has permission to delete messages and
that the DB update path works, before committing to the full run.  Each test
still makes real Discord API calls and updates deleted=true in the DB.

  # Delete one arbitrary message (dry-run preview):
  python scripts/maintenance/nuke_user_messages.py --phase 1 --test one

  # Delete one arbitrary message (for real):
  python scripts/maintenance/nuke_user_messages.py --phase 1 --test one --execute

  # Delete one message per channel (dry-run):
  python scripts/maintenance/nuke_user_messages.py --phase 1 --test per-channel

  # Delete one message per channel (for real):
  python scripts/maintenance/nuke_user_messages.py --phase 1 --test per-channel --execute

  # Delete a specific message by ID (dry-run):
  python scripts/maintenance/nuke_user_messages.py --phase 1 --test message \\
      --message-id 123456789012345678

  # Delete a specific message by ID (for real):
  python scripts/maintenance/nuke_user_messages.py --phase 1 --test message \\
      --message-id 123456789012345678 --execute
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import ssl
import sys
from datetime import datetime
from pathlib import Path

import aiohttp
import asyncpg

# ── project root on path ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import config  # noqa: E402 — must come after sys.path manipulation

# ── constants ─────────────────────────────────────────────────────────────────
TARGET_USER_ID: int = 131894958759215106
REQUIRED_CONFIRM: str = "I CONFIRM DELETE 131894958759215106"
DISCORD_API_BASE: str = "https://discord.com/api/v10"

# How many channels to delete from concurrently.
# Discord's global rate-limit is 50 req/s; at CONCURRENCY channels × ~3 msg/s
# each we stay well under that ceiling.
CONCURRENCY: int = 5

# Seconds to wait between consecutive deletes within a single channel
# (conservative floor — 429 responses will add more via Retry-After).
DELETE_DELAY: float = 0.35

# ── logging ───────────────────────────────────────────────────────────────────
LOG_FILE = Path(f"nuke_user_{TARGET_USER_ID}_{datetime.utcnow():%Y%m%d_%H%M%S}.log")

_formatter = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_formatter)

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(_formatter)

log = logging.getLogger("nuke_user")
log.setLevel(logging.INFO)
log.propagate = False  # don't hand off to root logger (avoids duplicates)
log.addHandler(_stdout_handler)
log.addHandler(_file_handler)


# ══════════════════════════════════════════════════════════════════════════════
# Database helpers
# ══════════════════════════════════════════════════════════════════════════════


def _create_ssl_context() -> ssl.SSLContext | None:
    cert_path = Path("ssl-cert")
    if not cert_path.exists():
        log.warning("ssl-cert/ directory not found — connecting without SSL")
        return None
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.load_verify_locations(cert_path / "server-ca.pem")
        ctx.load_cert_chain(cert_path / "client-cert.pem", cert_path / "client-key.pem")
        return ctx
    except Exception as exc:
        log.warning(
            "Failed to load SSL certificates (%s) — connecting without SSL", exc
        )
        return None


async def create_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(
        database=config.database,
        user=config.DB_user,
        password=config.DB_password,
        host=config.host,
        port=config.port,
        ssl=_create_ssl_context(),
        command_timeout=600,
        min_size=1,
        max_size=3,
    )
    if pool is None:
        raise RuntimeError("Failed to create database connection pool")
    return pool


# ══════════════════════════════════════════════════════════════════════════════
# Statistics / preview
# ══════════════════════════════════════════════════════════════════════════════


async def show_stats(pool: asyncpg.Pool, phase: int) -> dict:
    """Query and print a summary of what this run would affect."""
    if phase == 1:
        rows = await pool.fetch(
            """
            SELECT
                COUNT(*)                                AS total,
                COUNT(*) FILTER (WHERE deleted = false) AS pending,
                COUNT(*) FILTER (WHERE deleted = true)  AS already_done,
                COUNT(DISTINCT channel_id)              AS channels,
                MIN(created_at)                         AS oldest,
                MAX(created_at)                         AS newest
            FROM messages
            WHERE user_id = $1
            """,
            TARGET_USER_ID,
        )
        stats = dict(rows[0])
        log.info("━" * 72)
        log.info("PHASE 1 — DISCORD DELETION PREVIEW")
        log.info("━" * 72)
        log.info("  Total messages in DB  : %s", stats["total"])
        log.info("  Already deleted       : %s", stats["already_done"])
        log.info("  Pending (to delete)   : %s", stats["pending"])
        log.info("  Unique channels       : %s", stats["channels"])
        log.info("  Date range            : %s → %s", stats["oldest"], stats["newest"])
        log.info("━" * 72)
        return stats

    else:  # phase 2
        msg_count = await pool.fetchval(
            "SELECT COUNT(*) FROM messages WHERE user_id = $1",
            TARGET_USER_ID,
        )
        att_count = await pool.fetchval(
            """
            SELECT COUNT(*) FROM attachments
            WHERE message_id IN (
                SELECT message_id FROM messages WHERE user_id = $1
            )
            """,
            TARGET_USER_ID,
        )
        rxn_count = await pool.fetchval(
            """
            SELECT COUNT(*) FROM reactions
            WHERE message_id IN (
                SELECT message_id FROM messages WHERE user_id = $1
            )
            """,
            TARGET_USER_ID,
        )
        # Messages still not marked deleted (warn if phase 1 was skipped/incomplete)
        undone = await pool.fetchval(
            "SELECT COUNT(*) FROM messages WHERE user_id = $1 AND deleted = false",
            TARGET_USER_ID,
        )
        stats = {
            "messages": msg_count,
            "attachments": att_count,
            "reactions": rxn_count,
            "not_discord_deleted": undone,
        }
        log.info("━" * 72)
        log.info("PHASE 2 — DATABASE DELETION PREVIEW")
        log.info("━" * 72)
        log.info("  messages rows to delete     : %s", msg_count)
        log.info("  attachments rows to delete  : %s", att_count)
        log.info("  reactions rows to delete    : %s", rxn_count)
        if undone:
            log.warning(
                "  ⚠  %s messages are NOT marked deleted=true — "
                "phase 1 may not be complete!",
                undone,
            )
        log.info("━" * 72)
        return stats


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — Discord deletion
# ══════════════════════════════════════════════════════════════════════════════


async def _delete_one_discord_message(
    session: aiohttp.ClientSession,
    channel_id: int,
    message_id: int,
    headers: dict,
    dry_run: bool,
) -> bool:
    """Delete a single message from Discord.

    Returns True if the message is gone (deleted or already missing), False on
    a non-recoverable error. Handles rate-limiting (429) with Retry-After.
    """
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages/{message_id}"

    if dry_run:
        return True  # pretend success in dry-run mode

    for attempt in range(6):
        try:
            async with session.delete(url, headers=headers) as resp:
                if resp.status == 204:
                    return True
                if resp.status == 404:
                    # Already deleted on Discord side — treat as success
                    log.debug(
                        "Message %s in channel %s already gone (404)",
                        message_id,
                        channel_id,
                    )
                    return True
                if resp.status == 429:
                    body = await resp.json()
                    retry_after: float = float(body.get("retry_after", 5))
                    log.warning(
                        "Rate limited — sleeping %.2f s (attempt %d/6)",
                        retry_after,
                        attempt + 1,
                    )
                    await asyncio.sleep(retry_after + 0.1)
                    continue
                if resp.status in (401, 403):
                    log.error(
                        "Permission denied deleting message %s in channel %s (HTTP %s)",
                        message_id,
                        channel_id,
                        resp.status,
                    )
                    return False
                log.warning(
                    "Unexpected HTTP %s deleting message %s — retrying (attempt %d/6)",
                    resp.status,
                    message_id,
                    attempt + 1,
                )
                await asyncio.sleep(2**attempt)
        except (aiohttp.ClientError, TimeoutError) as exc:
            log.warning("Network error on attempt %d/6: %s", attempt + 1, exc)
            await asyncio.sleep(2**attempt)

    log.error(
        "Gave up deleting message %s in channel %s after 6 attempts",
        message_id,
        channel_id,
    )
    return False


async def _process_channel(
    channel_id: int,
    message_ids: list[int],
    session: aiohttp.ClientSession,
    pool: asyncpg.Pool,
    headers: dict,
    dry_run: bool,
    counters: dict,
    sem: asyncio.Semaphore,
) -> None:
    """Delete all pending messages in one channel, updating the DB as we go."""
    async with sem:
        log.info(
            "Channel %s — starting deletion of %s messages",
            channel_id,
            len(message_ids),
        )
        for msg_id in message_ids:
            success = await _delete_one_discord_message(
                session, channel_id, msg_id, headers, dry_run
            )
            if success:
                if not dry_run:
                    await pool.execute(
                        "UPDATE messages SET deleted = true WHERE message_id = $1",
                        msg_id,
                    )
                counters["deleted"] += 1
            else:
                counters["failed"] += 1

            total_processed = counters["deleted"] + counters["failed"]
            if total_processed % 250 == 0:
                log.info(
                    "Progress  deleted=%d  failed=%d  total_processed=%d",
                    counters["deleted"],
                    counters["failed"],
                    total_processed,
                )

            await asyncio.sleep(DELETE_DELAY)

        log.info("Channel %s — finished", channel_id)


async def run_phase1(pool: asyncpg.Pool, dry_run: bool) -> None:
    """Phase 1: delete every pending message from Discord."""
    # Fetch only messages not yet deleted, grouped by channel
    rows = await pool.fetch(
        """
        SELECT message_id, channel_id
        FROM messages
        WHERE user_id = $1 AND deleted = false
        ORDER BY channel_id, message_id
        """,
        TARGET_USER_ID,
    )

    if not rows:
        log.info(
            "No pending messages to delete from Discord — phase 1 is already complete."
        )
        return

    # Group by channel
    by_channel: dict[int, list[int]] = {}
    for row in rows:
        by_channel.setdefault(row["channel_id"], []).append(row["message_id"])

    log.info(
        "Phase 1 starting — %d messages across %d channels%s",
        len(rows),
        len(by_channel),
        "  [DRY RUN — no changes will be made]" if dry_run else "",
    )

    headers = {
        "Authorization": f"Bot {config.bot_token}",
        "User-Agent": "DiscordBot (nuke_user_messages, 1.0)",
    }
    counters: dict[str, int] = {"deleted": 0, "failed": 0}
    sem = asyncio.Semaphore(CONCURRENCY)

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [
            asyncio.create_task(
                _process_channel(
                    channel_id, msg_ids, session, pool, headers, dry_run, counters, sem
                )
            )
            for channel_id, msg_ids in by_channel.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    log.info("━" * 72)
    log.info(
        "Phase 1 complete — deleted=%d  failed=%d%s",
        counters["deleted"],
        counters["failed"],
        "  [DRY RUN]" if dry_run else "",
    )
    if counters["failed"]:
        log.warning(
            "%d messages could not be deleted from Discord. "
            "Re-run to retry, or check permissions.",
            counters["failed"],
        )
    log.info("━" * 72)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — Database deletion
# ══════════════════════════════════════════════════════════════════════════════


async def run_phase2(pool: asyncpg.Pool, dry_run: bool) -> None:
    """Phase 2: hard-delete all DB rows for the target user's messages."""
    if dry_run:
        log.info("Phase 2 preview complete — no DB changes made (dry-run).")
        return

    log.info("Deleting from attachments …")
    att_deleted = await pool.fetchval(
        """
        WITH deleted AS (
            DELETE FROM attachments
            WHERE message_id IN (
                SELECT message_id FROM messages WHERE user_id = $1
            )
            RETURNING 1
        )
        SELECT COUNT(*) FROM deleted
        """,
        TARGET_USER_ID,
    )
    log.info("  attachments deleted: %s", att_deleted)

    log.info("Deleting from reactions …")
    rxn_deleted = await pool.fetchval(
        """
        WITH deleted AS (
            DELETE FROM reactions
            WHERE message_id IN (
                SELECT message_id FROM messages WHERE user_id = $1
            )
            RETURNING 1
        )
        SELECT COUNT(*) FROM deleted
        """,
        TARGET_USER_ID,
    )
    log.info("  reactions deleted: %s", rxn_deleted)

    log.info("Deleting from messages …")
    msg_deleted = await pool.fetchval(
        """
        WITH deleted AS (
            DELETE FROM messages WHERE user_id = $1
            RETURNING 1
        )
        SELECT COUNT(*) FROM deleted
        """,
        TARGET_USER_ID,
    )
    log.info("  messages deleted: %s", msg_deleted)

    log.info("━" * 72)
    log.info(
        "Phase 2 complete — messages=%s  attachments=%s  reactions=%s",
        msg_deleted,
        att_deleted,
        rxn_deleted,
    )
    log.info("━" * 72)


# ══════════════════════════════════════════════════════════════════════════════
# Test modes
# ══════════════════════════════════════════════════════════════════════════════


async def _build_test_candidates(
    pool: asyncpg.Pool,
    test_mode: str,
    message_id_arg: int | None,
) -> list[dict] | None:
    """Return the list of (message_id, channel_id) dicts for a test run.

    Returns None when there is nothing to do (no pending messages).
    Exits the process on invalid input (wrong owner, missing ID, etc.).
    """
    if test_mode == "message":
        if message_id_arg is None:
            log.error("--test message requires --message-id")
            sys.exit(1)
        row = await pool.fetchrow(
            "SELECT message_id, channel_id, user_id FROM messages WHERE message_id = $1",
            message_id_arg,
        )
        if row is None:
            log.error("Message ID %s not found in the database.", message_id_arg)
            sys.exit(1)
        if row["user_id"] != TARGET_USER_ID:
            log.error(
                "Message %s belongs to user %s, not the target user %s — aborting.",
                message_id_arg,
                row["user_id"],
                TARGET_USER_ID,
            )
            sys.exit(1)
        return [{"message_id": row["message_id"], "channel_id": row["channel_id"]}]

    if test_mode == "one":
        row = await pool.fetchrow(
            """
            SELECT message_id, channel_id
            FROM messages
            WHERE user_id = $1 AND deleted = false
            ORDER BY created_at ASC
            LIMIT 1
            """,
            TARGET_USER_ID,
        )
        if row is None:
            return None
        return [{"message_id": row["message_id"], "channel_id": row["channel_id"]}]

    # per-channel
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (channel_id) message_id, channel_id
        FROM messages
        WHERE user_id = $1 AND deleted = false
        ORDER BY channel_id, created_at ASC
        """,
        TARGET_USER_ID,
    )
    if not rows:
        return None
    return [
        {"message_id": r["message_id"], "channel_id": r["channel_id"]} for r in rows
    ]


async def _attempt_discord_delete(
    session: aiohttp.ClientSession,
    ch_id: int,
    msg_id: int,
    headers: dict,
) -> tuple[str, int]:
    """Try to DELETE one message, returning (status_label, http_status).

    Retries up to 4 times with back-off; honours 429 Retry-After.
    """
    url = f"{DISCORD_API_BASE}/channels/{ch_id}/messages/{msg_id}"
    status_label = "UNKNOWN"
    http_status = 0

    for attempt in range(4):
        try:
            async with session.delete(url, headers=headers) as resp:
                http_status = resp.status
                if resp.status == 204:
                    return "OK", http_status
                if resp.status == 404:
                    return "ALREADY_GONE", http_status
                if resp.status == 429:
                    body = await resp.json()
                    wait = float(body.get("retry_after", 5))
                    log.warning("Rate limited — sleeping %.2fs", wait)
                    await asyncio.sleep(wait + 0.1)
                    continue
                if resp.status in (400, 401, 403):
                    # 400 = archived/locked thread; 401/403 = no permission.
                    # None of these will succeed on retry.
                    return f"PERMISSION_DENIED(HTTP {resp.status})", http_status
                status_label = f"HTTP_{resp.status}"
                await asyncio.sleep(2**attempt)
        except (aiohttp.ClientError, TimeoutError) as exc:
            status_label = f"NETWORK_ERROR({exc!r})"
            await asyncio.sleep(2**attempt)

    return status_label, http_status


async def run_test(
    pool: asyncpg.Pool,
    test_mode: str,
    message_id_arg: int | None,
    dry_run: bool,
) -> None:
    """Run a limited test deletion to verify permissions and the DB update path.

    test_mode values:
      "one"         — pick the oldest pending message and delete it
      "per-channel" — pick the oldest pending message from each channel
      "message"     — delete the specific message given by message_id_arg

    Each deletion prints a result row: OK / ALREADY_GONE / FAIL / DRY_RUN
    and the measured round-trip latency.  deleted=true is set in the DB for
    every message that Discord confirms as gone.
    """
    candidates = await _build_test_candidates(pool, test_mode, message_id_arg)
    if candidates is None:
        log.info("No pending messages found for test — all may already be deleted.")
        return

    mode_label = {
        "one": "single arbitrary message",
        "per-channel": f"one message from each of {len(candidates)} channel(s)",
        "message": f"specific message {message_id_arg}",
    }[test_mode]

    log.info("━" * 72)
    log.info("TEST MODE — %s%s", mode_label, "  [DRY RUN]" if dry_run else "")
    log.info("━" * 72)
    for c in candidates:
        log.info(
            "  Will target  message_id=%-20s  channel_id=%s",
            c["message_id"],
            c["channel_id"],
        )
    log.info("━" * 72)

    if dry_run:
        log.info("DRY RUN — no changes made.")
        return

    headers = {
        "Authorization": f"Bot {config.bot_token}",
        "User-Agent": "DiscordBot (nuke_user_messages, 1.0)",
    }
    ok_count = 0
    fail_count = 0

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30)
    ) as session:
        for candidate in candidates:
            msg_id = candidate["message_id"]
            ch_id = candidate["channel_id"]
            t_start = asyncio.get_event_loop().time()

            status_label, _ = await _attempt_discord_delete(
                session, ch_id, msg_id, headers
            )
            latency_ms = round((asyncio.get_event_loop().time() - t_start) * 1000)

            db_updated = False
            if status_label in ("OK", "ALREADY_GONE"):
                await pool.execute(
                    "UPDATE messages SET deleted = true WHERE message_id = $1", msg_id
                )
                db_updated = True
                ok_count += 1
            else:
                fail_count += 1

            icon = "✓" if db_updated else "✗"
            log.info(
                "%s  msg=%-20s  ch=%-20s  discord=%-30s  db=%s  latency=%dms",
                icon,
                msg_id,
                ch_id,
                status_label,
                "updated" if db_updated else "unchanged",
                latency_ms,
            )

    log.info("━" * 72)
    log.info("Test complete — ok=%d  failed=%d", ok_count, fail_count)
    if fail_count:
        log.warning(
            "%d deletion(s) failed — check permissions for the bot in those channels.",
            fail_count,
        )
    log.info("━" * 72)


# ══════════════════════════════════════════════════════════════════════════════
# Safety gate helpers
# ══════════════════════════════════════════════════════════════════════════════


def _warn_if_phase1_incomplete(phase: int, stats: dict) -> None:
    """Prompt the user if phase 2 is requested before phase 1 is finished."""
    if phase != 2:
        return
    undone = stats.get("not_discord_deleted", 0)
    if undone <= 0:
        return
    log.warning(
        "%d messages have not been Discord-deleted yet (deleted=false).", undone
    )
    _require_interactive_yes(
        f"\n  ⚠  {undone} messages were NOT deleted from Discord.\n"
        "  Proceed with DB deletion anyway?"
    )


def _banner() -> None:
    print()
    print(
        "╔══════════════════════════════════════════════════════════════════════════════╗"
    )
    print(
        "║         DANGER — PERMANENT DELETION — READ BEFORE PROCEEDING                ║"
    )
    print(
        "╠══════════════════════════════════════════════════════════════════════════════╣"
    )
    print(f"║  Target user ID : {TARGET_USER_ID:<58} ║")
    print(
        "║  This action CANNOT be undone.                                               ║"
    )
    print(
        "╚══════════════════════════════════════════════════════════════════════════════╝"
    )
    print()


def _require_interactive_yes(prompt: str) -> None:
    """Prompt the user and abort unless they type exactly 'yes'."""
    try:
        answer = input(prompt + " [type 'yes' to proceed] ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(0)
    if answer != "yes":
        print("Aborted — you did not type 'yes'.")
        sys.exit(0)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Permanently delete all messages for user 131894958759215106",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2],
        required=True,
        help="1 = delete from Discord API; 2 = delete from database",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually make changes. Without this flag the script is a dry-run preview.",
    )
    parser.add_argument(
        "--confirm",
        type=str,
        default="",
        help=f'Must be exactly: "{REQUIRED_CONFIRM}"',
    )

    test_group = parser.add_argument_group(
        "test modes (--phase 1 only, no passphrase required)"
    )
    test_group.add_argument(
        "--test",
        choices=["one", "per-channel", "message"],
        default=None,
        metavar="MODE",
        help=(
            "Run a limited test before the full deletion. "
            "one=delete 1 message; per-channel=delete 1 per channel; "
            "message=delete a specific message (requires --message-id)."
        ),
    )
    test_group.add_argument(
        "--message-id",
        type=int,
        default=None,
        metavar="ID",
        help="Discord message ID to target when --test message is used.",
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    # ── Validate flag combinations ────────────────────────────────────────────
    if args.test is not None and args.phase != 1:
        log.error("--test modes are only valid with --phase 1")
        sys.exit(1)
    if args.test == "message" and args.message_id is None:
        log.error("--test message requires --message-id <id>")
        sys.exit(1)
    if args.message_id is not None and args.test != "message":
        log.error("--message-id is only used with --test message")
        sys.exit(1)

    _banner()
    log.info("Log file  : %s", LOG_FILE)
    log.info("Phase     : %d", args.phase)
    log.info("Test mode : %s", args.test or "none (full run)")
    log.info("Dry run   : %s", not args.execute)

    # ══════════════════════════════════════════════════════════════════════════
    # TEST MODE — lighter safety, just --execute + interactive yes
    # ══════════════════════════════════════════════════════════════════════════
    if args.test is not None:
        log.info("Connecting to database …")
        pool = await create_pool()
        log.info("Connected.")
        try:
            if args.execute:
                _require_interactive_yes(
                    f"\nAbout to run test '{args.test}' — this makes real Discord API calls "
                    "and updates the DB. Proceed?"
                )
            await run_test(pool, args.test, args.message_id, dry_run=not args.execute)
        finally:
            await pool.close()
            log.info("Database connection closed. Log saved to: %s", LOG_FILE)
        return

    # ══════════════════════════════════════════════════════════════════════════
    # FULL RUN — all safety gates required
    # ══════════════════════════════════════════════════════════════════════════

    # ── Safety gate 1: confirm passphrase (only required when --execute) ──────
    if args.execute:
        if args.confirm != REQUIRED_CONFIRM:
            log.error(
                "ABORTED — --confirm value is wrong or missing.\n"
                '  Required exactly: "%s"\n'
                "  Got            : %r",
                REQUIRED_CONFIRM,
                args.confirm,
            )
            sys.exit(1)
        log.info("Confirm passphrase: OK")

    # ── Connect to DB ─────────────────────────────────────────────────────────
    log.info("Connecting to database …")
    pool = await create_pool()
    log.info("Connected.")

    try:
        # ── Show stats ────────────────────────────────────────────────────────
        stats = await show_stats(pool, args.phase)

        if not args.execute:
            log.info(
                "DRY RUN mode — add --execute (and --confirm) to make real changes."
            )
            return

        # ── Safety gate 2: phase-2 warning when phase-1 may be incomplete ────
        _warn_if_phase1_incomplete(args.phase, stats)

        # ── Safety gate 3: final interactive confirmation ─────────────────────
        action = (
            f"delete {stats.get('pending', stats.get('messages', '?'))} items from "
            + ("Discord" if args.phase == 1 else "the database")
        )
        _require_interactive_yes(f"\nAbout to {action}. Are you sure?")

        # ── Execute ───────────────────────────────────────────────────────────
        if args.phase == 1:
            await run_phase1(pool, dry_run=False)
        else:
            await run_phase2(pool, dry_run=False)

    finally:
        await pool.close()
        log.info("Database connection closed. Log saved to: %s", LOG_FILE)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        log.exception("Unhandled exception — script aborted")

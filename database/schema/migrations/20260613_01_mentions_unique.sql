-- =============================================================
-- Migration: Unique indexes on mentions (idempotent child rows)
-- Generated: 2026-06-13
-- Database: Cognita Discord Bot (PostgreSQL)
-- Status: MANUAL migration — listed in MANUAL_MIGRATIONS in
--         apply_migrations.py and applied by hand via psql.
--         CREATE INDEX CONCURRENTLY cannot run inside the
--         migration runner's per-migration transaction.
-- Source: Audit findings 02 C8-1 / 06 G1 — mentions has only a
--         serial PK, so re-saves (event re-delivery, backfill
--         overlapping live saves) silently duplicate rows. The
--         partial unique indexes below back the targetless
--         ON CONFLICT DO NOTHING added to the mentions INSERTs
--         in cogs/stats_listeners.py.
-- IMPORTANT: Run during a low-traffic period.
-- IMPORTANT: Do NOT run with --single-transaction or inside a
--            BEGIN/COMMIT block. CONCURRENTLY operations require
--            autocommit mode and will fail inside a transaction.
-- =============================================================

\set ON_ERROR_STOP 1

-- =============================================================
-- SECTION 1: Dedupe existing rows
-- =============================================================
-- Keep the lowest serial_id per (message_id, user_mention) and
-- per (message_id, role_mention); delete the rest. Without this,
-- CREATE UNIQUE INDEX fails on pre-existing duplicates.

DELETE FROM mentions m
USING mentions keep
WHERE m.user_mention IS NOT NULL
  AND keep.user_mention IS NOT NULL
  AND m.message_id = keep.message_id
  AND m.user_mention = keep.user_mention
  AND m.serial_id > keep.serial_id;

DELETE FROM mentions m
USING mentions keep
WHERE m.role_mention IS NOT NULL
  AND keep.role_mention IS NOT NULL
  AND m.message_id = keep.message_id
  AND m.role_mention = keep.role_mention
  AND m.serial_id > keep.serial_id;

-- =============================================================
-- SECTION 2: Partial unique indexes
-- =============================================================
-- Partial (WHERE ... IS NOT NULL) because each row populates only
-- one of user_mention/role_mention; the other column stays NULL.

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS mentions_message_user_uindex
    ON mentions (message_id, user_mention)
    WHERE user_mention IS NOT NULL;

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS mentions_message_role_uindex
    ON mentions (message_id, role_mention)
    WHERE role_mention IS NOT NULL;

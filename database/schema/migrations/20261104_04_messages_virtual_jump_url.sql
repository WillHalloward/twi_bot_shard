-- =============================================================
-- Migration: messages.jump_url -> VIRTUAL generated column
-- Generated: 2026-11-04
-- Database: Cognita Discord Bot (PostgreSQL 18+)
-- Status: MANUAL migration — listed in MANUAL_MIGRATIONS in
--         apply_migrations.py and applied by hand via psql.
--         VACUUM FULL cannot run inside the runner's transaction and
--         takes an ACCESS EXCLUSIVE lock on messages.
-- Context: jump_url was 87 of ~229 bytes per messages row (~1.6 GB) and
--          is always 'https://discord.com/channels/<server>/<channel>/<msg>'
--          (0 mismatches across all 19,735,630 production rows,
--          2026-11-04). A VIRTUAL generated column (Postgres 18) keeps it
--          queryable for ad-hoc SQL while storing nothing. No application
--          code reads it.
-- Prereq:  20261104_03 applied and the code that no longer inserts
--          jump_url deployed (inserting into a generated column errors).
--          Run 20261104_02 (index drops) FIRST: VACUUM FULL rebuilds
--          every remaining index, so fewer indexes = shorter lock.
-- IMPORTANT: Section 2 blocks writes to messages while the table is
--            rewritten (minutes on production). Message saves wait or
--            time out during that window. Run in a quiet period.
-- IMPORTANT: Do NOT run with --single-transaction (VACUUM).
-- Run:     psql "$DATABASE_URL" -f database/schema/migrations/20261104_04_messages_virtual_jump_url.sql
-- =============================================================

\set ON_ERROR_STOP 1

-- =============================================================
-- SECTION 1: Swap the column (one transaction, metadata-only)
-- =============================================================
-- Refuses to run if any stored URL differs from the derived one, so
-- no link can be silently changed. Rows inserted after 20261104_03
-- have NULL and are skipped by the check. Skipped entirely once the
-- column is already generated (re-run safe).

BEGIN;

DO $$
DECLARE
    mismatches bigint;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_attribute
        WHERE attrelid = 'messages'::regclass
          AND attname = 'jump_url'
          AND attgenerated <> ''
    ) THEN
        RAISE NOTICE 'messages.jump_url is already generated; skipping swap';
        RETURN;
    END IF;

    SELECT count(*) INTO mismatches
    FROM messages
    WHERE jump_url IS NOT NULL
      AND jump_url <> 'https://discord.com/channels/' || server_id::text
                      || '/' || channel_id::text || '/' || message_id::text;
    IF mismatches > 0 THEN
        RAISE EXCEPTION '% rows have a jump_url that differs from the derived URL; aborting', mismatches;
    END IF;

    ALTER TABLE messages DROP COLUMN jump_url;
    ALTER TABLE messages ADD COLUMN jump_url text
        GENERATED ALWAYS AS (
            'https://discord.com/channels/' || server_id::text || '/'
            || channel_id::text || '/' || message_id::text
        ) VIRTUAL;
END
$$;

COMMIT;

-- =============================================================
-- SECTION 2: Reclaim the space
-- =============================================================
-- DROP COLUMN only hides the old bytes; VACUUM FULL rewrites the
-- table (and its indexes) without them.

VACUUM FULL messages;

-- =============================================================
-- Verification
-- =============================================================
-- Expect: attgenerated = 'v', and a sample URL that looks right.
SELECT attname, attgenerated FROM pg_attribute
WHERE attrelid = 'messages'::regclass AND attname = 'jump_url';
SELECT jump_url FROM messages ORDER BY created_at DESC LIMIT 1;
SELECT pg_size_pretty(pg_total_relation_size('messages')) AS messages_size;

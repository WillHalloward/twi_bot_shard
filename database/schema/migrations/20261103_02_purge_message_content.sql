-- =============================================================
-- Migration: Purge stored Discord message text
-- Generated: 2026-11-03
-- Database: Cognita Discord Bot (PostgreSQL)
-- Status: MANUAL migration — listed in MANUAL_MIGRATIONS in
--         apply_migrations.py and applied by hand via psql.
--         Batched commits and VACUUM FULL cannot run inside the
--         runner's per-migration transaction, and VACUUM FULL takes
--         an ACCESS EXCLUSIVE lock on messages.
-- Context: Discord Message Content intent review. The bot no longer
--          stores message text (it keeps only content_length). This
--          migration deletes the text that was stored before that
--          change, so the intent application can truthfully answer
--          "not storing message content off-platform".
-- Prereq:  20261103_01_add_messages_content_length.sql applied AND
--          the code that writes content_length deployed. Otherwise
--          the old code fails once the column is dropped.
-- IMPORTANT: Run during a low-traffic period. Section 3 locks
--            messages/attachments (writes block) during the rewrite.
-- IMPORTANT: Do NOT run with --single-transaction or inside a
--            BEGIN/COMMIT block. The batched DO block commits
--            per batch, and VACUUM cannot run in a transaction.
-- Run:     psql "$DATABASE_URL" -f database/schema/migrations/20261103_02_purge_message_content.sql
-- =============================================================

\set ON_ERROR_STOP 1

-- =============================================================
-- SECTION 1: Backfill content_length from the existing text
-- =============================================================
-- Batched so it doesn't hold row locks on millions of rows in one
-- transaction. Re-runnable: only touches rows not yet backfilled.
-- Skipped automatically when the content column is already gone.

DO $$
DECLARE
    batch_rows integer;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'content'
    ) THEN
        RAISE NOTICE 'messages.content already dropped; skipping backfill';
        RETURN;
    END IF;

    LOOP
        EXECUTE $q$
            UPDATE messages SET content_length = LENGTH(content)
            WHERE message_id IN (
                SELECT message_id FROM messages
                WHERE content_length IS NULL AND content IS NOT NULL
                LIMIT 50000
            )
        $q$;
        GET DIAGNOSTICS batch_rows = ROW_COUNT;
        EXIT WHEN batch_rows = 0;
        RAISE NOTICE 'backfilled % rows', batch_rows;
        COMMIT;
    END LOOP;
END
$$;

-- =============================================================
-- SECTION 2: Drop the text columns
-- =============================================================

ALTER TABLE messages DROP COLUMN IF EXISTS content;
ALTER TABLE message_edit DROP COLUMN IF EXISTS old_content;
ALTER TABLE message_edit DROP COLUMN IF EXISTS new_content;
-- Discord counts attachments as message content too. Stats only ever
-- read attachments.id (to count messages with attachments), so the
-- filename and CDN URL go; size/dimensions/spoiler are kept.
ALTER TABLE attachments DROP COLUMN IF EXISTS filename;
ALTER TABLE attachments DROP COLUMN IF EXISTS url;

-- =============================================================
-- SECTION 3: Physically remove the data from disk
-- =============================================================
-- DROP COLUMN only hides the column; the bytes stay in the heap
-- and TOAST pages until the table is rewritten. VACUUM FULL
-- rewrites both tables without the dropped data.

VACUUM FULL messages;
VACUUM FULL message_edit;
VACUUM FULL attachments;

-- =============================================================
-- Verification (expect 0 rows)
-- =============================================================
SELECT table_name, column_name FROM information_schema.columns
WHERE (table_name IN ('messages', 'message_edit')
       AND column_name IN ('content', 'old_content', 'new_content'))
   OR (table_name = 'attachments' AND column_name IN ('filename', 'url'));

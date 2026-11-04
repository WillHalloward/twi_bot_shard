-- Migration: allow messages.jump_url to be omitted on insert
-- Date: 2026-11-04
--
-- Context:
--   messages.jump_url is being replaced by a VIRTUAL generated column (saves
--   ~1.6 GB; it is always derivable from server_id/channel_id/message_id,
--   verified for all 19.7M production rows). The new code no longer writes
--   it, so the plain column must stop being NOT NULL before that code starts
--   inserting, otherwise every message save would fail.
--
--   Runs automatically on deploy (metadata-only, instant). The swap to the
--   virtual column + VACUUM FULL is the MANUAL migration
--   20261104_04_messages_virtual_jump_url.sql. Rows inserted in between get
--   NULL here and are computed correctly once the swap runs.
--
--   Guarded: a generated column has no NOT NULL to drop (re-runs, fresh
--   databases built from init.sql).

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_attribute
        WHERE attrelid = 'messages'::regclass
          AND attname = 'jump_url'
          AND attgenerated = ''
          AND attnotnull
    ) THEN
        ALTER TABLE messages ALTER COLUMN jump_url DROP NOT NULL;
    END IF;
END
$$;

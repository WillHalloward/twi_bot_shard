-- Migration: add messages.content_length (message text is no longer stored)
-- Date: 2026-11-03
--
-- Context:
--   To pass Discord's Message Content privileged-intent review, the bot stops
--   persisting message text. The only thing stats ever read from
--   messages.content was AVG(LENGTH(content)), so the save paths in
--   cogs/stats_listeners.py now write len(message.content) into this column
--   instead.
--
--   This migration only adds the column (cheap, metadata-only), so it runs
--   automatically on deploy, before the new code starts writing to it.
--   Backfilling it and deleting the existing text is the separate MANUAL
--   migration 20261103_02_purge_message_content.sql.

ALTER TABLE messages ADD COLUMN IF NOT EXISTS content_length integer;

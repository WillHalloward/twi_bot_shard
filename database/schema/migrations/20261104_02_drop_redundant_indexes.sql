-- =============================================================
-- Migration: Drop redundant / unused indexes on messages + reactions
-- Generated: 2026-11-04
-- Database: Cognita Discord Bot (PostgreSQL)
-- Status: MANUAL migration — listed in MANUAL_MIGRATIONS in
--         apply_migrations.py and applied by hand via psql.
--         DROP INDEX CONCURRENTLY cannot run inside the runner's
--         per-migration transaction. CONCURRENTLY means no table lock:
--         safe to run while the bot is live.
-- Context: messages is 10 GB, of which 6.1 GB is indexes. Several are
--          exact duplicates (a b-tree serves both scan directions, so
--          "(x)" and "(x DESC)" do the same job) or never used.
--          20260405_database_design_cleanup.sql tried to drop some of
--          these but was never actually run on production, and
--          database/optimizations/base.sql re-created others on every
--          startup. base.sql no longer creates any of them.
--          Sizes / scan counts are production, 2026-11-04.
-- Safety:  Every dropped index has a kept twin that covers it (kept
--          indexes are created by base.sql on every startup, so they
--          exist in every environment). No constraint depends on any
--          of them: all FKs to messages use messages_pk.
-- Run:     psql "$DATABASE_URL" -f database/schema/migrations/20261104_02_drop_redundant_indexes.sql
-- =============================================================

\set ON_ERROR_STOP 1

-- ---------------- messages (~2.9 GB) ----------------

-- Duplicate of messages_pk (both unique on message_id).        423 MB
DROP INDEX CONCURRENTLY IF EXISTS messages_id_uindex;

-- (created_at DESC) duplicates idx_messages_created_at.       423 MB
DROP INDEX CONCURRENTLY IF EXISTS messages_created_at_index;

-- (channel_id, created_at DESC) duplicates
-- idx_messages_channel_created (channel_id, created_at).       594 MB
DROP INDEX CONCURRENTLY IF EXISTS idx_messages_channel_created_at;

-- (user_id, created_at DESC) duplicates
-- idx_messages_user_created (user_id, created_at).             594 MB
DROP INDEX CONCURRENTLY IF EXISTS idx_messages_user_created_at;

-- (message_id DESC, channel_id): message_id lookups are served
-- by messages_pk.                                              593 MB
DROP INDEX CONCURRENTLY IF EXISTS messages_message_id_channel_id_index;

-- (channel_id DESC): covered by idx_messages_channel_created
-- (channel_id leads it).                                       131 MB
DROP INDEX CONCURRENTLY IF EXISTS messages_channel_id_index;

-- (is_bot): boolean, 0 scans.                                  130 MB
DROP INDEX CONCURRENTLY IF EXISTS idx_messages_is_bot;

-- ---------------- reactions (~0.2 GB) ----------------

-- message_id lookups are served by the unique
-- reactions_message_id_user_id_{emoji_id,unicode_emoji}_uindex.
-- Both 0 scans.                                                119 MB
DROP INDEX CONCURRENTLY IF EXISTS idx_reactions_message_emoji;
DROP INDEX CONCURRENTLY IF EXISTS idx_reactions_message_unicode;

-- 0 scans.                                                     106 MB
DROP INDEX CONCURRENTLY IF EXISTS idx_reactions_date;
DROP INDEX CONCURRENTLY IF EXISTS idx_reactions_user_id;

-- Verification (expect 0 rows)
SELECT indexname FROM pg_indexes
WHERE indexname IN (
    'messages_id_uindex', 'messages_created_at_index',
    'idx_messages_channel_created_at', 'idx_messages_user_created_at',
    'messages_message_id_channel_id_index', 'messages_channel_id_index',
    'idx_messages_is_bot', 'idx_reactions_message_emoji',
    'idx_reactions_message_unicode', 'idx_reactions_date',
    'idx_reactions_user_id');

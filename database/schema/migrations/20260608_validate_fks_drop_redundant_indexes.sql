-- =============================================================
-- Migration: Validate FK constraints + drop redundant indexes
-- Generated: 2026-06-08
-- Database: Cognita Discord Bot (PostgreSQL)
-- Status: APPLIED to production 2026-06-08 (via psql).
-- Source: pgHero "Invalid Constraints" + "Duplicate Indexes" findings.
-- IMPORTANT: Run during a low-traffic period.
-- IMPORTANT: Do NOT run with --single-transaction or inside a
--            BEGIN/COMMIT block. CONCURRENTLY operations require
--            autocommit mode and will fail inside a transaction.
-- =============================================================

\set ON_ERROR_STOP 1

-- =============================================================
-- SECTION 1: Clean orphaned child rows, then VALIDATE the FKs
-- =============================================================
-- attachments_messages_fk and mentions_messages_fk were added
-- NOT VALID, so existing rows were never checked. Production had
-- 15 attachments and 3 mentions referencing messages that no
-- longer exist (dead, unreachable rows). VALIDATE fails until
-- they're removed. The FKs have no ON DELETE CASCADE, but the bot
-- soft-deletes messages (deleted=true), so validating does not
-- affect normal deletion.

DELETE FROM attachments a
 WHERE a.message_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM messages m WHERE m.message_id = a.message_id);

DELETE FROM mentions x
 WHERE x.message_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM messages m WHERE m.message_id = x.message_id);

ALTER TABLE attachments VALIDATE CONSTRAINT attachments_messages_fk;
ALTER TABLE mentions VALIDATE CONSTRAINT mentions_messages_fk;

-- =============================================================
-- SECTION 2: Drop redundant indexes (each covered by a composite)
-- =============================================================
-- Every index below is fully covered by an existing composite /
-- primary-key / unique index whose leading column matches, so the
-- single-column index only adds write + space overhead. Freed
-- ~550 MB (most of it on messages). The corresponding CREATE INDEX
-- statements were removed from database/optimizations/base.sql,
-- database/init.sql, database/schema/tables.sql, and
-- database/utilities/gallery-migration.sql so they are not
-- recreated. (The 20260405 cleanup migration also listed two of
-- these but was never applied; this migration supersedes it.)

-- covered by creator_links_pk (user_id, title)
DROP INDEX CONCURRENTLY IF EXISTS idx_creator_links_user_id;
DROP INDEX CONCURRENTLY IF EXISTS creator_links_user_id_index;

-- covered by gallery_migration_message_id_key (message_id) unique
DROP INDEX CONCURRENTLY IF EXISTS idx_gallery_migration_message_id;

-- covered by gallery_posts_message_id_key (message_id) unique
DROP INDEX CONCURRENTLY IF EXISTS idx_gallery_posts_message_id;

-- covered by the messages (col, created_at) composites
DROP INDEX CONCURRENTLY IF EXISTS idx_messages_channel_id;     -- idx_messages_channel_created
DROP INDEX CONCURRENTLY IF EXISTS idx_messages_server_id;      -- idx_messages_server_created
DROP INDEX CONCURRENTLY IF EXISTS idx_messages_user_id;        -- idx_messages_user_created
DROP INDEX CONCURRENTLY IF EXISTS messages_user_id_index;      -- idx_messages_user_created

-- covered by idx_reactions_message_emoji (message_id, emoji_id)
DROP INDEX CONCURRENTLY IF EXISTS idx_reactions_message_id;

-- covered by idx_reports_unique_user_message (message_id, user_id)
DROP INDEX CONCURRENTLY IF EXISTS idx_reports_message_id;

-- covered by role_membership_role_id_user_id_index (role_id, user_id)
DROP INDEX CONCURRENTLY IF EXISTS idx_role_membership_role;

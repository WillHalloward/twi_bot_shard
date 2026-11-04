-- =============================================================
-- Migration: Purge remaining stored message content
-- Generated: 2026-11-04
-- Database: Cognita Discord Bot (PostgreSQL)
-- Status: MANUAL migration — listed in MANUAL_MIGRATIONS in
--         apply_migrations.py and applied by hand via psql.
--         Uses psql \gset/\if meta-commands and VACUUM FULL, which
--         cannot run inside the runner's per-migration transaction.
-- Context: Follow-up to 20261103_02. The Discord intent application
--          certifies the bot does not store message content
--          off-platform, but two places still held it:
--            * embeds / embed_fields: legacy embed tracking (titles,
--              descriptions, field values). No code reads or writes
--              them; last row 2026-05-29.
--            * gallery_migration.raw_content / raw_embed_data: original
--              message text and embed JSON saved by
--              /gallery_admin extract_data. The code no longer writes
--              them; the extracted title/creator/tags/images remain.
-- Prereq:  The code that stops writing raw_content/raw_embed_data is
--          deployed (otherwise /gallery_admin extract_data fails once
--          the columns are gone).
-- Notes:   Tables are small (~100 MB total); runs in seconds.
--          gallery_migration only exists in production; the \if
--          guard skips it elsewhere.
-- Run:     psql "$DATABASE_URL" -f database/schema/migrations/20261104_01_purge_embeds_and_gallery_raw_content.sql
-- =============================================================

\set ON_ERROR_STOP 1

-- =============================================================
-- SECTION 1: Legacy embed tracking tables
-- =============================================================
-- DROP TABLE removes the files immediately; no VACUUM needed.

DROP TABLE IF EXISTS embed_fields;
DROP TABLE IF EXISTS embeds;

-- =============================================================
-- SECTION 2: gallery_migration raw message content
-- =============================================================
-- DROP COLUMN only hides the data; VACUUM FULL rewrites the table
-- without it.

SELECT to_regclass('public.gallery_migration') IS NOT NULL AS has_gallery_migration \gset
\if :has_gallery_migration
ALTER TABLE gallery_migration DROP COLUMN IF EXISTS raw_content;
ALTER TABLE gallery_migration DROP COLUMN IF EXISTS raw_embed_data;
VACUUM FULL gallery_migration;
\endif

-- =============================================================
-- Verification (expect 0 rows)
-- =============================================================
SELECT table_name, column_name FROM information_schema.columns
WHERE table_schema = 'public'
  AND (table_name IN ('embeds', 'embed_fields')
       OR (table_name = 'gallery_migration'
           AND column_name IN ('raw_content', 'raw_embed_data')));

-- =============================================================
-- Migration: Database Design Cleanup
-- Generated: 2026-04-05
-- Database: Cognita Discord Bot (PostgreSQL)
-- IMPORTANT: Test on staging before running on production.
-- IMPORTANT: Run during a low-traffic period. Most operations
--            use CONCURRENTLY and are safe online, but some
--            ALTER COLUMN TYPE commands require brief table
--            rewrites (marked WARNING below).
-- IMPORTANT: Several sections (14, 15) require coordinated
--            application code changes. Read the notes before
--            executing those sections.
-- IMPORTANT: Do NOT run with --single-transaction or inside a
--            BEGIN/COMMIT block. CONCURRENTLY operations require
--            autocommit mode and will fail inside a transaction.
-- IMPORTANT: Verify `SHOW timezone;` returns 'UTC' on the DB
--            server before running Section 13. If not, the
--            timestamp→timestamptz conversion will store wrong
--            offsets for future writes.
-- =============================================================

\set ON_ERROR_STOP 1


-- =============================================================
-- SECTION 1: SKIPPED — PostgreSQL 18 named NOT NULL constraints
-- =============================================================
-- The original audit identified "*_not_null" constraints as
-- redundant CHECK constraints. However, this database runs on
-- PostgreSQL 18, which introduced named NOT NULL constraints
-- (pg_constraint.contype = 'n'). These are NOT redundant — they
-- ARE the NOT NULL enforcement mechanism in PG18. Dropping them
-- would actually remove NOT NULL from those columns.
-- No action required; all constraints are correct as-is.
-- =============================================================


-- =============================================================
-- SECTION 2: Drop duplicate indexes
-- =============================================================
-- Strategy:
--   * For _uindex duplicates of PK-backing indexes: drop the
--     _uindex, keep the _pk index (it is the actual PK backing).
--   * For error_telemetry: _index suffix duplicates _idx suffix;
--     drop the older _index ones, keep _idx.
--   * For creator_links: two identical non-unique indexes on
--     user_id; drop the older _index one, keep idx_.
--   * For messages: the old _index set is superseded by the
--     newer idx_ set; drop the _index ones.
--   * For poll_option: "index_name" is a stale placeholder name
--     that duplicates poll_option_pk; drop it.
--   * The servers table has THREE unique indexes on server_id
--     (servers_pk, servers_server_id_uindex, plus serial_id has
--     servers_serial_id_uindex which is its own unique column);
--     drop servers_server_id_uindex, keep servers_pk.
-- All use CONCURRENTLY (no table lock on production).
-- Safe online.
-- =============================================================

-- banned_words: serial_id_uindex duplicates banned_words_pk
DROP INDEX CONCURRENTLY IF EXISTS banned_words_serial_id_uindex;

-- categories: id_uindex duplicates categories_pk
DROP INDEX CONCURRENTLY IF EXISTS categories_id_uindex;

-- channels: id_uindex duplicates channels_pk
DROP INDEX CONCURRENTLY IF EXISTS channels_id_uindex;

-- gallery_mementos: channel_name_uindex duplicates gallery_mementos_pk
DROP INDEX CONCURRENTLY IF EXISTS gallery_mementos_channel_name_uindex;

-- mentions: serial_id_uindex duplicates mentions_pk
DROP INDEX CONCURRENTLY IF EXISTS mentions_serial_id_uindex;

-- message_edit: serial_id_uindex duplicates message_edit_pk
DROP INDEX CONCURRENTLY IF EXISTS message_edit_serial_id_uindex;

-- messages: id_uindex duplicates messages_pk
DROP INDEX CONCURRENTLY IF EXISTS messages_id_uindex;

-- poll: poll_id_uindex duplicates poll_pk (both on id)
DROP INDEX CONCURRENTLY IF EXISTS poll_id_uindex;

-- poll_option: stale placeholder name duplicates poll_option_pk
DROP INDEX CONCURRENTLY IF EXISTS index_name;

-- role_history: serial_id_uindex duplicates role_history_pk
DROP INDEX CONCURRENTLY IF EXISTS role_history_serial_id_uindex;

-- role_membership: serial_id_uindex duplicates role_membership_pk
DROP INDEX CONCURRENTLY IF EXISTS role_membership_serial_id_uindex;

-- role_membership: user_id_role_id_uindex duplicates role_membership_pk_2
DROP INDEX CONCURRENTLY IF EXISTS role_membership_user_id_role_id_uindex;

-- roles: id_uindex duplicates roles_pk
DROP INDEX CONCURRENTLY IF EXISTS roles_id_uindex;

-- server_membership: user_id_server_id_uindex duplicates server_membership_user_id_server_id_key
DROP INDEX CONCURRENTLY IF EXISTS server_membership_user_id_server_id_uindex;

-- servers: server_id_uindex duplicates servers_pk
DROP INDEX CONCURRENTLY IF EXISTS servers_server_id_uindex;

-- thread_membership: serial_id_uindex duplicates thread_membership_pk
DROP INDEX CONCURRENTLY IF EXISTS thread_membership_serial_id_uindex;

-- threads: id_uindex duplicates threads_pk
DROP INDEX CONCURRENTLY IF EXISTS threads_id_uindex;

-- twi_reddit: discord_id_uindex duplicates twi_reddit_pk
DROP INDEX CONCURRENTLY IF EXISTS twi_reddit_discord_id_uindex;

-- updates: serial_id_uindex duplicates updates_pk
DROP INDEX CONCURRENTLY IF EXISTS updates_serial_id_uindex;

-- users: user_id_uindex duplicates users_pk
DROP INDEX CONCURRENTLY IF EXISTS users_user_id_uindex;

-- error_telemetry: _index suffix duplicates _idx suffix (same column, same operator)
DROP INDEX CONCURRENTLY IF EXISTS error_telemetry_command_name_index;
DROP INDEX CONCURRENTLY IF EXISTS error_telemetry_error_type_index;
DROP INDEX CONCURRENTLY IF EXISTS error_telemetry_timestamp_index;
-- NOTE: error_telemetry_user_id_idx has no _index counterpart; keep it.
-- NOTE: error_telemetry_resolved_idx has no duplicate; keep it.

-- creator_links: two identical non-unique indexes on user_id
-- creator_links_user_id_index and idx_creator_links_user_id are identical.
-- Drop the older name, keep the idx_ convention.
DROP INDEX CONCURRENTLY IF EXISTS creator_links_user_id_index;

-- messages: old _index set superseded by the idx_ set.
--   messages_channel_id_index   (channel_id DESC)          vs idx_messages_channel_id (channel_id)
--     and idx_messages_channel_created / idx_messages_channel_created_at
--   messages_created_at_index   (created_at DESC)          vs idx_messages_created_at (created_at)
--   messages_user_id_index      (user_id)                  vs idx_messages_user_id (user_id)
--     and idx_messages_user_created / idx_messages_user_created_at
--   messages_message_id_channel_id_index (message_id DESC, channel_id) -- no exact idx_ equivalent
--     but message_id is already covered by the PK (messages_pk); the composite is for lookups
--     by message+channel. Evaluate in application before dropping - listed here as a candidate.
-- Drop clear superseded single-column duplicates:
DROP INDEX CONCURRENTLY IF EXISTS messages_created_at_index;
DROP INDEX CONCURRENTLY IF EXISTS messages_user_id_index;

-- messages_channel_id_index uses DESC ordering; idx_messages_channel_id is ASC.
-- If the application relies on reverse-scan on channel_id, keep messages_channel_id_index.
-- Drop it only if query plans show idx_messages_channel_id covers all needs:
-- DROP INDEX CONCURRENTLY IF EXISTS messages_channel_id_index;  -- REVIEW BEFORE ENABLING

-- messages_message_id_channel_id_index: composite (message_id DESC, channel_id).
-- No direct idx_ duplicate. The PK covers message_id lookups, but not the channel_id
-- composite. Leave this index unless profiling shows it is unused.
-- DROP INDEX CONCURRENTLY IF EXISTS messages_message_id_channel_id_index;  -- REVIEW BEFORE ENABLING


-- =============================================================
-- SECTION 3: Add missing FK indexes
-- =============================================================
-- Foreign key columns without a supporting index cause full
-- sequential scans during ON DELETE / ON UPDATE and join queries.
-- Verified against existing indexes; the following FK columns
-- have no covering index at all.
-- Safe online (CONCURRENTLY).
-- =============================================================

-- emotes.guild_id -> servers.server_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_emotes_guild_id
    ON emotes (guild_id);

-- infractions.user_id -> users.user_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_infractions_user_id
    ON infractions (user_id);

-- mentions.message_id -> messages.message_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_mentions_message_id
    ON mentions (message_id);

-- poll_option.poll_id -> poll.id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_poll_option_poll_id
    ON poll_option (poll_id);

-- role_history.user_id -> users.user_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_role_history_user_id
    ON role_history (user_id);

-- role_history.role_id -> roles.id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_role_history_role_id
    ON role_history (role_id);

-- role_membership.user_id -> users.user_id
-- (already covered by the composite unique index role_membership_pk_2 (user_id, role_id)
-- which the planner can use for FK checks -- keeping this explicit index is optional,
-- but adding it makes FK enforcement unambiguous)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_role_membership_user_id
    ON role_membership (user_id);

-- roles.guild_id -> servers.server_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_roles_guild_id
    ON roles (guild_id);

-- server_membership.server_id -> servers.server_id
-- (covered by composite unique server_membership_user_id_server_id_key (user_id, server_id)
-- but that composite starts with user_id; planner cannot use it for server_id-only lookups)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_server_membership_server_id
    ON server_membership (server_id);

-- server_membership.user_id -> users.user_id
-- (same composite starts with user_id so this IS covered; skip)
-- No action needed.


-- =============================================================
-- SECTION 4: Fix data types
-- =============================================================
-- 4a: poll_option.num_votes  smallint -> integer
--     smallint caps at 32,767 votes. A popular poll can exceed
--     this. integer (2^31-1) is the safe choice.
--     WARNING: Table rewrite required, locks table briefly.
-- 4b: patreon_twi.post_id    integer -> bigint
--     Patreon post IDs are large external identifiers; integer
--     risks overflow.
--     WARNING: Table rewrite required, locks table briefly.
-- 4c: roles.color            varchar -> integer
--     Discord color values are 24-bit integers (0-16777215).
--     Storing as varchar wastes space and makes comparisons
--     fragile. Cast only if the application always writes
--     numeric strings; otherwise leave as varchar and note.
--     WARNING: Table rewrite required, locks table briefly.
--     REQUIRES APPLICATION CODE CHANGE - see note below.
-- =============================================================

-- 4a: poll_option.num_votes smallint -> integer
-- WARNING: Table rewrite required, locks table briefly.
ALTER TABLE poll_option
    ALTER COLUMN num_votes TYPE integer;

-- 4b: patreon_twi.post_id integer -> bigint
-- WARNING: Table rewrite required, locks table briefly.
ALTER TABLE patreon_twi
    ALTER COLUMN post_id TYPE bigint;

-- 4c: roles.color varchar -> integer
-- NOTE: Only run this if the application writes color as a plain
-- numeric string (e.g. '16711680') and never as hex/name.
-- Verify with: SELECT DISTINCT color FROM roles LIMIT 50;
-- If values are hex strings like '#ff0000' leave this commented
-- out and handle conversion in application code instead.
-- REQUIRES APPLICATION CODE CHANGE before running.
-- WARNING: Table rewrite required, locks table briefly.
--
-- ALTER TABLE roles
--     ALTER COLUMN color TYPE integer USING color::integer;


-- =============================================================
-- SECTION 5: Rename join_leave.join_or_leave to is_join (boolean)
-- =============================================================
-- The column stores only 'join' or 'leave' as varchar.
-- Converting to boolean (true=join, false=leave) saves space,
-- improves index efficiency, and removes the need for string
-- comparison in queries.
-- Application code has already been updated to write TRUE/FALSE
-- and reference the column as is_join.
-- Run steps in order; verify after each before proceeding.
-- =============================================================

-- Step 1: Add a new boolean column alongside the old one.
-- Safe online.
ALTER TABLE join_leave
    ADD COLUMN IF NOT EXISTS is_join boolean;

-- Step 2: Backfill from the existing varchar column.
-- WARNING: Full table scan + write. Run during low traffic.
-- COALESCE handles any unexpected NULL join_or_leave rows (defaults to FALSE/leave).
UPDATE join_leave
    SET is_join = COALESCE(join_or_leave = 'join', FALSE)
    WHERE is_join IS NULL;

-- Step 3: Set NOT NULL once backfill is verified.
-- DO block makes this idempotent (errors if column is already NOT NULL on re-run).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'join_leave'
          AND column_name  = 'is_join'
          AND is_nullable  = 'YES'
    ) THEN
        ALTER TABLE join_leave ALTER COLUMN is_join SET NOT NULL;
    END IF;
END $$;

-- Step 4: Drop the old varchar column.
-- WARNING: Table rewrite required, locks table briefly.
-- Only run after verifying is_join data looks correct.
-- ALTER TABLE join_leave DROP COLUMN join_or_leave;


-- =============================================================
-- SECTION 6: Fix sequences from integer to bigint
-- =============================================================
-- Sequences with integer max (2,147,483,647) attached to high-
-- volume tables risk exhaustion. The messages table alone has
-- 18M+ rows. Sequences whose owning column is still integer
-- must have the column widened first (Section 4 handles the
-- critical ones; below handles the sequence objects).
--
-- Sequences confirmed as integer-capped (max=2147483647):
--   audit_log_id_seq, banned_words_serial_id_seq,
--   bot_metrics_id_seq, button_action_history_serial_seq,
--   command_history_serial_seq, creator_links_serial_id_seq,
--   emotes_serial_id_seq, error_telemetry_id_seq,
--   infractions_id_seq (*seq is bigint but column is int - fix),
--   innktober_quests_serial_seq, innktober_submission_id_seq,
--   join_leave_id_seq, mentions_serial_id_seq,
--   message_edit_serial_id_seq, password_link_serial_id_seq,
--   quotes_serial_id_seq, reactions_id_seq, reports_id_seq,
--   role_history_serial_id_seq, role_membership_serial_id_seq,
--   schema_embeddings_id_seq, server_membership_serial_id_seq,
--   servers_serial_id_seq, twi_reddit_serial_index_seq,
--   updates_serial_id_seq, users_serial_id_seq.
--
-- Priority order: tables with most rows / fastest growth first.
-- For each: widen the column then alter the sequence.
-- WARNING: ALTER COLUMN TYPE causes table rewrite (brief lock).
-- Safe online for the sequence itself; the column change is not.
-- =============================================================

-- High-priority: command_history (tracks every command)
ALTER TABLE command_history ALTER COLUMN serial TYPE bigint;
ALTER SEQUENCE command_history_serial_seq AS bigint MAXVALUE 9223372036854775807;

-- High-priority: mentions (one row per mention in every message)
ALTER TABLE mentions ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE mentions_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

-- High-priority: message_edit (edit events)
ALTER TABLE message_edit ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE message_edit_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

-- High-priority: reactions
ALTER TABLE reactions ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE reactions_id_seq AS bigint MAXVALUE 9223372036854775807;

-- High-priority: role_history and role_membership
ALTER TABLE role_history ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE role_history_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE role_membership ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE role_membership_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

-- High-priority: server_membership
ALTER TABLE server_membership ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE server_membership_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

-- Medium-priority: users and servers (referenced by many FKs)
ALTER TABLE users ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE users_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE servers ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE servers_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

-- Medium-priority: audit_log, bot_metrics, error_telemetry
ALTER TABLE audit_log ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE audit_log_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE bot_metrics ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE bot_metrics_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE error_telemetry ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE error_telemetry_id_seq AS bigint MAXVALUE 9223372036854775807;

-- Medium-priority: infractions (sequence already bigint but column is int)
ALTER TABLE infractions ALTER COLUMN id TYPE bigint;
-- sequence infractions_id_seq already has bigint max; no change needed.

-- Lower-priority: remaining tables
ALTER TABLE banned_words ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE banned_words_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE button_action_history ALTER COLUMN serial TYPE bigint;
ALTER SEQUENCE button_action_history_serial_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE creator_links ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE creator_links_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE emotes ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE emotes_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE innktober_quests ALTER COLUMN serial TYPE bigint;
ALTER SEQUENCE innktober_quests_serial_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE innktober_submission ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE innktober_submission_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE join_leave ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE join_leave_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE links ALTER COLUMN id TYPE bigint;
-- links uses tags_id_seq (already bigint max); no sequence change needed.

ALTER TABLE password_link ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE password_link_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE patreon_twi ALTER COLUMN serial_id TYPE bigint;
-- patreon_twi_serial_id_seq already has bigint max; no change needed.

ALTER TABLE quotes ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE quotes_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE reports ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE reports_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE schema_embeddings ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE schema_embeddings_id_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE twi_reddit ALTER COLUMN serial_index TYPE bigint;
ALTER SEQUENCE twi_reddit_serial_index_seq AS bigint MAXVALUE 9223372036854775807;

ALTER TABLE updates ALTER COLUMN serial_id TYPE bigint;
ALTER SEQUENCE updates_serial_id_seq AS bigint MAXVALUE 9223372036854775807;

-- Six tables whose sequences were previously widened to bigint
-- but whose columns were never updated to match.
-- WARNING: Table rewrite required for each, locks table briefly.
ALTER TABLE foliana_interlude    ALTER COLUMN serial_id TYPE bigint;
ALTER TABLE invisible_text_twi   ALTER COLUMN serial_id TYPE bigint;
ALTER TABLE protected_is_public  ALTER COLUMN serial_id TYPE bigint;
ALTER TABLE webhook_pins_twi     ALTER COLUMN serial_id TYPE bigint;
-- wandering_inn and poll also have integer columns backed by bigint sequences.
ALTER TABLE wandering_inn        ALTER COLUMN serial_id TYPE bigint;
ALTER TABLE poll                 ALTER COLUMN index_serial TYPE bigint;


-- =============================================================
-- SECTION 7: Fix bot_metrics.metric_data json -> jsonb
-- =============================================================
-- jsonb is binary-indexed, supports GIN indexing, operators
-- like @>, ?, and is generally faster to query than json.
-- WARNING: Table rewrite required, locks table briefly.
-- =============================================================

ALTER TABLE bot_metrics
    ALTER COLUMN metric_data TYPE jsonb USING metric_data::jsonb;


-- =============================================================
-- SECTION 8: Fix gallery_mementos primary key
-- =============================================================
-- Current state:
--   PK is on channel_name (varchar) via gallery_mementos_pk.
--   channel_id (bigint, NOT NULL) exists but is not the PK.
--   guild_id (bigint, NULLABLE) is present.
--
-- The natural identifier for a Discord gallery channel is
-- channel_id (a stable snowflake), not channel_name (mutable).
-- Recommended fix:
--   1. Drop the current PK constraint (backed by gallery_mementos_pk).
--   2. Add PRIMARY KEY on channel_id.
--   3. Add a UNIQUE constraint on channel_name if still needed
--      for lookup purposes.
--
-- NOTE: Verify that application code uses channel_id as the
-- lookup key before executing. If any code path upserts by
-- channel_name, update it first.
-- WARNING: Table rewrite required, locks table briefly.
-- =============================================================

-- Step 1: Drop existing PK (backed by gallery_mementos_pk index)
ALTER TABLE gallery_mementos DROP CONSTRAINT IF EXISTS gallery_mementos_pk;

-- Step 2: Add new PK on channel_id.
-- DO block makes this idempotent (ADD PRIMARY KEY errors if PK already exists).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema   = 'public'
          AND table_name     = 'gallery_mementos'
          AND constraint_type = 'PRIMARY KEY'
    ) THEN
        ALTER TABLE gallery_mementos ADD PRIMARY KEY (channel_id);
    END IF;
END $$;

-- Step 3: Retain unique constraint on channel_name to prevent duplicate entries.
-- Without this, two rows with the same channel_name can be silently inserted.
-- DO block makes this idempotent (ADD CONSTRAINT has no IF NOT EXISTS in PostgreSQL).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name   = 'gallery_mementos'
          AND constraint_name = 'gallery_mementos_channel_name_key'
    ) THEN
        ALTER TABLE gallery_mementos ADD CONSTRAINT gallery_mementos_channel_name_key
            UNIQUE (channel_name);
    END IF;
END $$;


-- =============================================================
-- SECTION 9: Fix daily_message_stats materialized view
-- (remove hardcoded server_id)
-- =============================================================
-- Current definition filters WHERE server_id = '346842016480755724'
-- This hardcoded server_id makes the view non-portable and
-- breaks if the bot ever serves a different primary guild, or
-- if the view is queried for other guilds.
--
-- New definition: remove the server_id filter, group by server_id
-- so the view covers all servers. Callers filter by server_id
-- in their queries.
--
-- Also: the view uses 'timestamp without time zone' columns from
-- messages (created_at) directly in date arithmetic. This is
-- consistent with the application's UTC-naive convention and
-- requires no change here.
--
-- Safe online (materialized view refresh does not lock base table
-- in PostgreSQL 9.4+).
-- =============================================================

DROP MATERIALIZED VIEW IF EXISTS daily_message_stats;

CREATE MATERIALIZED VIEW daily_message_stats AS
    SELECT
        count(*)      AS total,
        channel_id,
        channel_name,
        server_id
    FROM messages
    WHERE
        created_at >= (now() - INTERVAL '1 day')
        AND is_bot = false
    GROUP BY channel_id, channel_name, server_id
    ORDER BY count(*) DESC;

-- Re-create the supporting index for CONCURRENTLY refreshes.
-- Index is on (channel_id, channel_name, server_id) to match the GROUP BY exactly,
-- ensuring uniqueness even if a channel was renamed (different channel_name, same channel_id).
CREATE UNIQUE INDEX IF NOT EXISTS daily_message_stats_group_key_idx
    ON daily_message_stats (channel_id, channel_name, server_id);


-- Rebuild daily_member_stats to use the new is_join boolean column.
-- Section 5 (Steps 1-3) added is_join and backfilled it, so the new
-- view can reference is_join immediately. The old join_or_leave column
-- still exists at this point (Step 4 is still commented out), so the
-- old view definition also still works — but we replace it now so the
-- view is correct once Step 4 runs.
DROP MATERIALIZED VIEW IF EXISTS daily_member_stats;
CREATE MATERIALIZED VIEW daily_member_stats AS
    SELECT
        count(*) FILTER (WHERE is_join = true)  AS joins,
        count(*) FILTER (WHERE is_join = false) AS leaves,
        server_id
    FROM join_leave
    WHERE date >= (now() - INTERVAL '1 day')
    GROUP BY server_id;

-- Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY support.
CREATE UNIQUE INDEX IF NOT EXISTS daily_member_stats_server_id_idx
    ON daily_member_stats (server_id);


-- =============================================================
-- SECTION 10: Fix typo currant_patreon -> current_patreon
-- =============================================================
-- twi_reddit.currant_patreon is a misspelling of current_patreon.
-- The _not_null constraint with the old name was dropped in Section 1.
-- Safe online (metadata-only rename, no table rewrite in Postgres 12+).
-- REQUIRES APPLICATION CODE CHANGE: update all queries and ORM
-- models that reference 'currant_patreon' to use 'current_patreon'.
-- =============================================================

-- DO block makes this idempotent (RENAME COLUMN errors if column already renamed).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'twi_reddit'
          AND column_name  = 'currant_patreon'
    ) THEN
        ALTER TABLE twi_reddit RENAME COLUMN currant_patreon TO current_patreon;
    END IF;
END $$;


-- =============================================================
-- SECTION 11: Fix reports.reason length
-- =============================================================
-- reports.reason is VARCHAR(50). Moderation reasons routinely
-- exceed 50 characters and truncation causes silent data loss.
-- Expanding to VARCHAR(500) or TEXT is safe online in PostgreSQL
-- (increasing varchar length never rewrites the table).
-- Safe online.
-- =============================================================

ALTER TABLE reports
    ALTER COLUMN reason TYPE varchar(500);


-- =============================================================
-- SECTION 12: Drop unused schema_embeddings vector index
-- =============================================================
-- idx_schema_embeddings_vector is an IVFFlat index with lists=10.
-- schema_embeddings is a small table (one row per DB table).
-- IVFFlat indexes require a minimum of ~39 * lists rows to be
-- effective (i.e., ~390 rows for lists=10). On a small table
-- the index adds write overhead and is never selected by the
-- planner over a sequential scan.
-- If the table grows large enough for vector ANN search to be
-- beneficial, recreate with appropriate lists value then.
-- Safe online (CONCURRENTLY).
-- =============================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_schema_embeddings_vector;


-- =============================================================
-- SECTION 13: Standardize timestamp types (all to timestamptz)
-- =============================================================
-- The database mixes timestamp (no tz) and timestamptz columns.
-- The application always writes UTC-naive datetimes (per CLAUDE.md
-- convention), but storing as timestamptz makes timezone handling
-- explicit and prevents future bugs if the server timezone changes.
--
-- Affected columns (timestamp without time zone):
--   audit_log.timestamp
--   bot_metrics.timestamp                (+ fix in Section 7)
--   button_action_history.date
--   categories.created_at
--   channels.created_at
--   command_history.start_date
--   command_history.end_date
--   creator_links.last_changed
--   credential_metadata.created_at
--   credential_metadata.last_rotated_at
--   credential_metadata.next_rotation_at
--   emotes.created_at
--   error_telemetry.timestamp
--   infractions.date
--   join_leave.created_at
--   join_leave.date
--   message_edit.edit_timestamp
--   messages.created_at                  (HIGH IMPACT - 18M+ rows)
--   reactions.date
--   reports.created_at
--   role_history.date
--   role_permissions.created_at
--   role_permissions.updated_at
--   roles.created_at
--   schema_embeddings.created_at
--   schema_embeddings.updated_at
--   server_settings.created_at
--   server_settings.updated_at
--   servers.creation_date
--   twi_reddit.time_added
--   updates.date
--   user_permissions.created_at
--   user_permissions.updated_at
--   users.created_at
--
-- WARNING: Every ALTER COLUMN TYPE below causes a table rewrite
-- and a brief ACCESS EXCLUSIVE lock. For the messages table
-- (18M+ rows) this lock could last several minutes.
-- STRONGLY RECOMMENDED: Run the messages table change during a
-- scheduled maintenance window.
--
-- The cast `AT TIME ZONE 'UTC'` interprets the stored value
-- as UTC (which it already is per application convention) and
-- converts to timestamptz correctly.
-- =============================================================

-- Drop all materialized views whose columns we're about to alter.
-- They depend on join_leave.date and messages.created_at.
-- All are recreated at the end of this section.
DROP MATERIALIZED VIEW IF EXISTS daily_member_stats;
DROP MATERIALIZED VIEW IF EXISTS daily_message_stats;
DROP MATERIALIZED VIEW IF EXISTS channel_hourly_stats;
DROP MATERIALIZED VIEW IF EXISTS user_activity_stats;

-- Small/metadata tables first (fast rewrites):
ALTER TABLE audit_log
    ALTER COLUMN timestamp TYPE timestamptz USING timestamp AT TIME ZONE 'UTC';

ALTER TABLE bot_metrics
    ALTER COLUMN timestamp TYPE timestamptz USING timestamp AT TIME ZONE 'UTC';

ALTER TABLE button_action_history
    ALTER COLUMN date TYPE timestamptz USING date AT TIME ZONE 'UTC';

ALTER TABLE categories
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';

ALTER TABLE channels
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';

ALTER TABLE command_history
    ALTER COLUMN start_date TYPE timestamptz USING start_date AT TIME ZONE 'UTC';
ALTER TABLE command_history
    ALTER COLUMN end_date TYPE timestamptz USING end_date AT TIME ZONE 'UTC';

ALTER TABLE creator_links
    ALTER COLUMN last_changed TYPE timestamptz USING last_changed AT TIME ZONE 'UTC';

ALTER TABLE credential_metadata
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
ALTER TABLE credential_metadata
    ALTER COLUMN last_rotated_at TYPE timestamptz USING last_rotated_at AT TIME ZONE 'UTC';
ALTER TABLE credential_metadata
    ALTER COLUMN next_rotation_at TYPE timestamptz USING next_rotation_at AT TIME ZONE 'UTC';

ALTER TABLE emotes
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';

ALTER TABLE error_telemetry
    ALTER COLUMN timestamp TYPE timestamptz USING timestamp AT TIME ZONE 'UTC';

ALTER TABLE infractions
    ALTER COLUMN date TYPE timestamptz USING date AT TIME ZONE 'UTC';

ALTER TABLE join_leave
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
ALTER TABLE join_leave
    ALTER COLUMN date TYPE timestamptz USING date AT TIME ZONE 'UTC';

ALTER TABLE message_edit
    ALTER COLUMN edit_timestamp TYPE timestamptz USING edit_timestamp AT TIME ZONE 'UTC';

ALTER TABLE reactions
    ALTER COLUMN date TYPE timestamptz USING date AT TIME ZONE 'UTC';

ALTER TABLE reports
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';

ALTER TABLE role_history
    ALTER COLUMN date TYPE timestamptz USING date AT TIME ZONE 'UTC';

ALTER TABLE role_permissions
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
ALTER TABLE role_permissions
    ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'UTC';

ALTER TABLE roles
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';

ALTER TABLE schema_embeddings
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
ALTER TABLE schema_embeddings
    ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'UTC';

ALTER TABLE server_settings
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
ALTER TABLE server_settings
    ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'UTC';

ALTER TABLE servers
    ALTER COLUMN creation_date TYPE timestamptz USING creation_date AT TIME ZONE 'UTC';

ALTER TABLE twi_reddit
    ALTER COLUMN time_added TYPE timestamptz USING time_added AT TIME ZONE 'UTC';

ALTER TABLE updates
    ALTER COLUMN date TYPE timestamptz USING date AT TIME ZONE 'UTC';

ALTER TABLE user_permissions
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
ALTER TABLE user_permissions
    ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'UTC';

ALTER TABLE users
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';

-- WARNING: messages.created_at - 18M+ rows. SCHEDULE A MAINTENANCE WINDOW.
-- Indexes idx_messages_created_at, idx_messages_channel_created,
-- idx_messages_channel_created_at, idx_messages_user_created,
-- idx_messages_user_created_at, idx_messages_server_created, and
-- idx_messages_active will be automatically rebuilt during the rewrite.
-- Estimated lock time: several minutes on 18M rows.
ALTER TABLE messages
    ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';

-- Recreate materialized views that were dropped above.
-- All now operate on timestamptz columns (no conversion needed after the ALTER COLUMNs above).

CREATE MATERIALIZED VIEW daily_member_stats AS
    SELECT
        count(*) FILTER (WHERE is_join = true)  AS joins,
        count(*) FILTER (WHERE is_join = false) AS leaves,
        server_id
    FROM join_leave
    WHERE date >= (now() - INTERVAL '1 day')
    GROUP BY server_id;

CREATE UNIQUE INDEX IF NOT EXISTS daily_member_stats_server_id_idx
    ON daily_member_stats (server_id);

CREATE MATERIALIZED VIEW daily_message_stats AS
    SELECT
        count(*)      AS total,
        channel_id,
        channel_name,
        server_id
    FROM messages
    WHERE
        created_at >= (now() - INTERVAL '1 day')
        AND is_bot = false
    GROUP BY channel_id, channel_name, server_id
    ORDER BY count(*) DESC;

CREATE UNIQUE INDEX IF NOT EXISTS daily_message_stats_group_key_idx
    ON daily_message_stats (channel_id, channel_name, server_id);

CREATE MATERIALIZED VIEW channel_hourly_stats AS
    SELECT
        channel_id,
        EXTRACT(hour FROM created_at) AS hour,
        count(*) AS message_count
    FROM messages
    WHERE created_at >= (now() - INTERVAL '30 days')
    GROUP BY channel_id, EXTRACT(hour FROM created_at);

CREATE MATERIALIZED VIEW user_activity_stats AS
    SELECT
        user_id,
        count(*) AS message_count,
        min(created_at) AS first_message,
        max(created_at) AS last_message,
        count(DISTINCT channel_id) AS active_channels
    FROM messages
    WHERE created_at >= (now() - INTERVAL '30 days')
      AND is_bot = false
    GROUP BY user_id;


-- =============================================================
-- SECTION 14: Rename guild_id / server_id for consistency
-- =============================================================
-- The schema uses both guild_id and server_id for the same
-- concept (a Discord guild/server snowflake), creating confusion.
--
-- Current usage:
--   Uses guild_id:  button_action_history, categories, channels,
--                   command_history, emotes (FK to servers.server_id),
--                   error_telemetry, gallery_mementos, links,
--                   reports, role_permissions, roles (FK to servers),
--                   server_settings, threads, user_permissions
--   Uses server_id: infractions, join_leave, messages (FK to servers),
--                   server_membership (FK to servers), servers (PK column)
--
-- RECOMMENDATION: Standardise on guild_id everywhere except the
-- servers table itself (where server_id is the PK and is
-- referenced by many FKs - renaming it requires updating all
-- FK constraints too).
--
-- REQUIRES APPLICATION CODE CHANGE for every renamed column.
-- Coordinate with a code deployment. Do NOT run this section
-- without updating the application first.
--
-- The renames below are provided as a reference; uncomment and
-- execute after the application is updated.
-- =============================================================

-- infractions: server_id -> guild_id
-- (no FK on this column, so rename is simple)
-- ALTER TABLE infractions RENAME COLUMN server_id TO guild_id;

-- join_leave: server_id -> guild_id
-- (no FK on this column)
-- ALTER TABLE join_leave RENAME COLUMN server_id TO guild_id;

-- messages: server_id -> guild_id
-- (has FK constraint messages_servers_server_id_fk)
-- Steps required:
--   1. ALTER TABLE messages RENAME COLUMN server_id TO guild_id;
--   2. The FK constraint references column server_id in messages;
--      PostgreSQL follows the column rename automatically - the
--      constraint name stays but points to the new column name.
--   3. Update application code to use guild_id everywhere.
-- ALTER TABLE messages RENAME COLUMN server_id TO guild_id;

-- server_membership: server_id -> guild_id
-- (has FK server_membership_servers_server_id_fk)
-- ALTER TABLE server_membership RENAME COLUMN server_id TO guild_id;

-- NOTE: Do NOT rename servers.server_id at this time. It is the
-- primary key and is referenced by FK constraints from:
--   messages, command_history, emotes, roles, server_membership.
-- Renaming it requires dropping and recreating all those FKs.
-- If you want to do it, the order is:
--   1. Drop all FK constraints referencing servers.server_id.
--   2. Rename the column.
--   3. Recreate FK constraints with the new column name.
-- This is a large coordinated change; track as a separate migration.


-- =============================================================
-- SECTION 15: Remove redundant links.user_who_added column
-- =============================================================
-- links.user_who_added is a varchar storing the username string.
-- links.id_user_who_added is a bigint storing the Discord user ID.
-- The user ID is the authoritative, stable identifier.
-- The username string is redundant (can be resolved from the
-- users table via id_user_who_added) and will become stale
-- as users change their usernames.
--
-- REQUIRES APPLICATION CODE CHANGE: remove all writes to and
-- reads from links.user_who_added before dropping the column.
-- Verify no queries or ORM models reference user_who_added.
-- Safe online after application is updated (no table rewrite
-- needed for DROP COLUMN in PostgreSQL 12+).
-- =============================================================

-- Verify no data will be lost (check if any rows have user_who_added
-- but no id_user_who_added before dropping):
-- SELECT count(*) FROM links WHERE user_who_added IS NOT NULL AND id_user_who_added IS NULL;

-- Only run after verifying the above returns 0 and application is updated:
-- ALTER TABLE links DROP COLUMN IF EXISTS user_who_added;

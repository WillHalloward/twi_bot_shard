-- =============================================================
-- Migration: add is_join boolean to join_leave (production hotfix)
-- Date: 2026-05-29
-- =============================================================
-- Production was missing the is_join column that the deployed code
-- (cogs/stats.py, cogs/stats_listeners.py) requires. This extracts
-- the safe, additive steps from 20260405_database_design_cleanup.sql
-- (SECTION 5) so production can be reconciled without running the
-- heavier, table-locking sections of that migration.
--
-- Idempotent and safe to run online. Does NOT drop join_or_leave;
-- both columns coexist (matching staging) until the full cleanup
-- migration is applied in a maintenance window.
-- =============================================================

-- Step 1: Add the boolean column alongside the old varchar one.
ALTER TABLE join_leave
    ADD COLUMN IF NOT EXISTS is_join boolean;

-- Step 2: Backfill from the existing varchar column.
-- COALESCE handles any unexpected NULL join_or_leave rows (-> FALSE/leave).
UPDATE join_leave
    SET is_join = COALESCE(join_or_leave = 'join', FALSE)
    WHERE is_join IS NULL;

-- Step 3: Enforce NOT NULL once the backfill is complete.
-- DO block keeps this idempotent on re-run.
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

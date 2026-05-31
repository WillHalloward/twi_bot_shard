-- Migration: add missing `permissions` column to `roles`
-- Date: 2026-05-31
--
-- Context:
--   cogs/stats_listeners.py persists Discord role permission bitfields
--   (`role.permissions.value`) on role create (guild_role_create) and role
--   update (enhanced_guild_role_update), but the column was never present in
--   the schema/model. Every role create/update therefore raised:
--     column "permissions" of relation "roles" does not exist
--   (Sentry: PYTHON-AIOHTTP-3 / -5 / -6).
--
-- Discord permission values are a 64-bit bitfield, so `bigint` is sufficient
-- and consistent with the other id/bitfield columns on this table. Nullable
-- so existing rows are unaffected.

ALTER TABLE roles
    ADD COLUMN IF NOT EXISTS permissions bigint;

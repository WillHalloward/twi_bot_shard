-- Additional Database Optimizations
-- This file contains additional optimizations beyond those in db_optimizations.sql

-- 1. Additional Indexes for Frequently Queried Tables

-- Index for message queries by date range (used in stats.py save command)
CREATE INDEX IF NOT EXISTS idx_messages_created_at_range ON messages(created_at)
WHERE created_at > NOW() - INTERVAL '30 DAYS';

-- Index for thread queries (used in stats.py thread operations)
CREATE INDEX IF NOT EXISTS idx_threads_parent_archived ON threads(parent_id, archived);

-- Index for role membership queries by server (used in member_remove event)
CREATE INDEX IF NOT EXISTS idx_role_membership_by_server ON role_membership(user_id)
INCLUDE (role_id);

-- Index for updates table (frequently written to)
CREATE INDEX IF NOT EXISTS idx_updates_date ON updates(date DESC);
CREATE INDEX IF NOT EXISTS idx_updates_table_action ON updates(updated_table, action);

-- Index for join_leave table by server and date (used in stats reporting)
CREATE INDEX IF NOT EXISTS idx_join_leave_server_date ON join_leave(server_id, date DESC);

-- 2. Optimize Complex JOIN Queries

-- Create a function to get the last message date for a channel
CREATE OR REPLACE FUNCTION get_last_message_date(channel_id_param BIGINT)
RETURNS TIMESTAMP AS $$
DECLARE
    last_date TIMESTAMP;
BEGIN
    SELECT MAX(created_at) INTO last_date
    FROM messages
    WHERE channel_id = channel_id_param;
    
    RETURN last_date;
END;
$$ LANGUAGE plpgsql;

-- 3. Additional Materialized Views for Complex Queries

-- User activity by channel materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS user_channel_activity AS
SELECT
    user_id,
    channel_id,
    COUNT(*) AS message_count,
    MAX(created_at) AS last_message
FROM messages
WHERE created_at >= NOW() - INTERVAL '30 DAYS'
AND is_bot = FALSE
GROUP BY user_id, channel_id;

-- Create index on the materialized view
CREATE INDEX IF NOT EXISTS idx_user_channel_activity_user ON user_channel_activity(user_id);
CREATE INDEX IF NOT EXISTS idx_user_channel_activity_channel ON user_channel_activity(channel_id);

-- Weekly message statistics materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS weekly_message_stats AS
SELECT
    COUNT(*) AS total,
    channel_id,
    channel_name,
    server_id,
    DATE_TRUNC('week', created_at) AS week
FROM messages
WHERE created_at >= NOW() - INTERVAL '90 DAYS'
AND is_bot = FALSE
GROUP BY channel_id, channel_name, server_id, DATE_TRUNC('week', created_at);

-- Create index on the materialized view
CREATE INDEX IF NOT EXISTS idx_weekly_message_stats_channel ON weekly_message_stats(channel_id);
CREATE INDEX IF NOT EXISTS idx_weekly_message_stats_server ON weekly_message_stats(server_id);
CREATE INDEX IF NOT EXISTS idx_weekly_message_stats_week ON weekly_message_stats(week);

-- 4. Update the refresh_materialized_views function to include new views
CREATE OR REPLACE FUNCTION refresh_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW daily_message_stats;
    REFRESH MATERIALIZED VIEW daily_member_stats;
    REFRESH MATERIALIZED VIEW user_channel_activity;
    REFRESH MATERIALIZED VIEW weekly_message_stats;
    REFRESH MATERIALIZED VIEW user_activity_stats;
    REFRESH MATERIALIZED VIEW channel_hourly_stats;
END;
$$ LANGUAGE plpgsql;

-- 5. Add partial indexes for specific query patterns

-- Partial index for recent reactions (frequently queried)
CREATE INDEX IF NOT EXISTS idx_reactions_recent ON reactions(message_id, user_id)
WHERE date > NOW() - INTERVAL '7 DAYS';

-- Partial index for active threads (not archived)
CREATE INDEX IF NOT EXISTS idx_active_threads ON threads(guild_id, parent_id)
WHERE archived = FALSE AND deleted = FALSE;

-- Partial index for non-deleted messages in active channels
CREATE INDEX IF NOT EXISTS idx_active_messages ON messages(channel_id, created_at)
WHERE deleted = FALSE AND created_at > NOW() - INTERVAL '30 DAYS';
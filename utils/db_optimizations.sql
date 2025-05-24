-- Database Optimization Script for Cognita Bot
-- This script adds indexes and materialized views to improve query performance

-- Indexes for frequently queried columns in messages table
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_server_id ON messages(server_id);
CREATE INDEX IF NOT EXISTS idx_messages_channel_id ON messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_is_bot ON messages(is_bot);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_messages_server_created ON messages(server_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_channel_created ON messages(channel_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_user_created ON messages(user_id, created_at);

-- Indexes for join_leave table
CREATE INDEX IF NOT EXISTS idx_join_leave_date ON join_leave(date);
CREATE INDEX IF NOT EXISTS idx_join_leave_server_id ON join_leave(server_id);
CREATE INDEX IF NOT EXISTS idx_join_leave_join_or_leave ON join_leave(join_or_leave);

-- Indexes for reactions table
CREATE INDEX IF NOT EXISTS idx_reactions_message_id ON reactions(message_id);
CREATE INDEX IF NOT EXISTS idx_reactions_user_id ON reactions(user_id);
CREATE INDEX IF NOT EXISTS idx_reactions_date ON reactions(date);

-- Materialized view for daily message statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_message_stats AS
SELECT 
    COUNT(*) AS total, 
    channel_id,
    channel_name,
    server_id
FROM messages 
WHERE created_at >= NOW() - INTERVAL '1 DAY'
AND server_id = 346842016480755724 
AND is_bot = FALSE
GROUP BY channel_id, channel_name, server_id
ORDER BY total DESC;

-- Materialized view for user join/leave statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_member_stats AS
SELECT
    COUNT(*) FILTER (WHERE join_or_leave = 'JOIN') AS joins,
    COUNT(*) FILTER (WHERE join_or_leave = 'LEAVE') AS leaves,
    server_id
FROM join_leave 
WHERE date >= NOW() - INTERVAL '1 DAY'
GROUP BY server_id;

-- Function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW daily_message_stats;
    REFRESH MATERIALIZED VIEW daily_member_stats;
END;
$$ LANGUAGE plpgsql;

-- Comment: To refresh views manually, run:
-- SELECT refresh_materialized_views();
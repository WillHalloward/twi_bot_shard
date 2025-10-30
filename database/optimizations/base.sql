-- Database Performance Optimization Script
-- Based on recommendations from the database review

-- 1. Add Missing Primary Keys
DO $$
BEGIN
    -- Check if attachments_pk constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'attachments_pk'
    ) THEN
        ALTER TABLE attachments ADD CONSTRAINT attachments_pk PRIMARY KEY (id);
    END IF;

    -- Check if foliana_interlude_pk constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'foliana_interlude_pk'
    ) THEN
        ALTER TABLE foliana_interlude ADD CONSTRAINT foliana_interlude_pk PRIMARY KEY (serial_id);
    END IF;

    -- Check if invisible_text_twi_pk constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'invisible_text_twi_pk'
    ) THEN
        ALTER TABLE invisible_text_twi ADD CONSTRAINT invisible_text_twi_pk PRIMARY KEY (serial_id);
    END IF;

    -- Check if password_link_pk constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'password_link_pk'
    ) THEN
        ALTER TABLE password_link ADD CONSTRAINT password_link_pk PRIMARY KEY (serial_id);
    END IF;

    -- Check if quotes_pk constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quotes_pk'
    ) THEN
        ALTER TABLE quotes ADD CONSTRAINT quotes_pk PRIMARY KEY (serial_id);
    END IF;

    -- Check if banned_words_pk constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'banned_words_pk'
    ) THEN
        ALTER TABLE banned_words ADD CONSTRAINT banned_words_pk PRIMARY KEY (serial_id);
    END IF;
END $$;

-- 2. Add Foreign Key Constraints
DO $$
BEGIN
    -- Check if attachments_messages_fk constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'attachments_messages_fk'
    ) THEN
        -- Use NOT VALID to skip validation of existing data
        ALTER TABLE attachments ADD CONSTRAINT attachments_messages_fk
        FOREIGN KEY (message_id) REFERENCES messages(message_id) NOT VALID;
    END IF;

    -- Check if mentions_messages_fk constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'mentions_messages_fk'
    ) THEN
        -- Use NOT VALID to skip validation of existing data
        ALTER TABLE mentions ADD CONSTRAINT mentions_messages_fk
        FOREIGN KEY (message_id) REFERENCES messages(message_id) NOT VALID;
    END IF;
END $$;

-- 3. Add Composite Indexes for Common Query Patterns
-- For message queries filtered by channel and date
CREATE INDEX IF NOT EXISTS idx_messages_channel_created_at ON messages(channel_id, created_at DESC);

-- For user activity queries
CREATE INDEX IF NOT EXISTS idx_messages_user_created_at ON messages(user_id, created_at DESC);

-- For reaction queries
CREATE INDEX IF NOT EXISTS idx_reactions_message_emoji ON reactions(message_id, emoji_id);
CREATE INDEX IF NOT EXISTS idx_reactions_message_unicode ON reactions(message_id, unicode_emoji);

-- For role membership queries
CREATE INDEX IF NOT EXISTS idx_role_membership_role ON role_membership(role_id);

-- 4. Add Indexes for Foreign Keys
-- Add index for message_id in attachments
CREATE INDEX IF NOT EXISTS idx_attachments_message_id ON attachments(message_id);

-- Add index for user_id in creator_links
CREATE INDEX IF NOT EXISTS idx_creator_links_user_id ON creator_links(user_id);

-- 5. Add Partial Indexes for Specific Queries
-- Index for non-deleted messages only
CREATE INDEX IF NOT EXISTS idx_messages_active ON messages(channel_id, created_at)
WHERE deleted = FALSE;

-- Index for active threads
CREATE INDEX IF NOT EXISTS idx_threads_active ON threads(guild_id, parent_id)
WHERE deleted = FALSE;

-- 6. Add Full-Text Search Indexes
-- For quotes search
CREATE INDEX IF NOT EXISTS idx_quotes_text_search ON quotes USING gin(tokens);

-- For poll options search
CREATE INDEX IF NOT EXISTS idx_poll_option_text_search ON poll_option USING gin(tokens);

-- 7. Create Materialized Views for Complex Statistics
-- User activity materialized view
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_matviews WHERE matviewname = 'user_activity_stats'
    ) THEN
        CREATE MATERIALIZED VIEW user_activity_stats AS
        SELECT
            user_id,
            COUNT(*) AS message_count,
            MIN(created_at) AS first_message,
            MAX(created_at) AS last_message,
            COUNT(DISTINCT channel_id) AS active_channels
        FROM messages
        WHERE created_at >= NOW() - INTERVAL '30 DAYS'
        AND is_bot = FALSE
        GROUP BY user_id;
    END IF;

    -- Channel activity by hour
    IF NOT EXISTS (
        SELECT 1 FROM pg_matviews WHERE matviewname = 'channel_hourly_stats'
    ) THEN
        CREATE MATERIALIZED VIEW channel_hourly_stats AS
        SELECT
            channel_id,
            EXTRACT(HOUR FROM created_at) AS hour,
            COUNT(*) AS message_count
        FROM messages
        WHERE created_at >= NOW() - INTERVAL '30 DAYS'
        GROUP BY channel_id, EXTRACT(HOUR FROM created_at);
    END IF;
END $$;

-- 8. Autovacuum Settings for Large Tables
ALTER TABLE reactions SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_vacuum_cost_delay = 2
);

ALTER TABLE role_membership SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_vacuum_cost_delay = 2
);

-- 9. Create Index Maintenance Function
CREATE OR REPLACE FUNCTION maintain_indexes()
RETURNS void AS $$
BEGIN
    -- Rebuild indexes with high fragmentation
    REINDEX TABLE messages;
    REINDEX TABLE reactions;
    -- Add more tables as needed
END;
$$ LANGUAGE plpgsql;

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
    COUNT(*) FILTER (WHERE join_or_leave = 'join') AS joins,
    COUNT(*) FILTER (WHERE join_or_leave = 'leave') AS leaves,
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

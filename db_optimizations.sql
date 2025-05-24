-- Database Performance Optimization Script
-- Based on recommendations from the database review

-- 1. Add Missing Primary Keys
ALTER TABLE attachments ADD CONSTRAINT attachments_pk PRIMARY KEY (id);
ALTER TABLE foliana_interlude ADD CONSTRAINT foliana_interlude_pk PRIMARY KEY (serial_id);
ALTER TABLE invisible_text_twi ADD CONSTRAINT invisible_text_twi_pk PRIMARY KEY (serial_id);
ALTER TABLE password_link ADD CONSTRAINT password_link_pk PRIMARY KEY (serial_id);
ALTER TABLE quotes ADD CONSTRAINT quotes_pk PRIMARY KEY (serial_id);
ALTER TABLE banned_words ADD CONSTRAINT banned_words_pk PRIMARY KEY (serial_id);

-- 2. Add Foreign Key Constraints
ALTER TABLE attachments ADD CONSTRAINT attachments_messages_fk 
FOREIGN KEY (message_id) REFERENCES messages(message_id);

ALTER TABLE mentions ADD CONSTRAINT mentions_messages_fk 
FOREIGN KEY (message_id) REFERENCES messages(message_id);

-- 3. Add Composite Indexes for Common Query Patterns
-- For message queries filtered by channel and date
CREATE INDEX idx_messages_channel_created_at ON messages(channel_id, created_at DESC);

-- For user activity queries
CREATE INDEX idx_messages_user_created_at ON messages(user_id, created_at DESC);

-- For reaction queries
CREATE INDEX idx_reactions_message_emoji ON reactions(message_id, emoji_id);
CREATE INDEX idx_reactions_message_unicode ON reactions(message_id, unicode_emoji);

-- For role membership queries
CREATE INDEX idx_role_membership_role ON role_membership(role_id);

-- 4. Add Indexes for Foreign Keys
-- Add index for message_id in attachments
CREATE INDEX idx_attachments_message_id ON attachments(message_id);

-- Add index for user_id in creator_links
CREATE INDEX idx_creator_links_user_id ON creator_links(user_id);

-- 5. Add Partial Indexes for Specific Queries
-- Index for non-deleted messages only
CREATE INDEX idx_messages_active ON messages(channel_id, created_at) 
WHERE deleted = FALSE;

-- Index for active threads
CREATE INDEX idx_threads_active ON threads(guild_id, parent_id) 
WHERE deleted = FALSE;

-- 6. Add Full-Text Search Indexes
-- For quotes search
CREATE INDEX idx_quotes_text_search ON quotes USING gin(tokens);

-- For poll options search
CREATE INDEX idx_poll_option_text_search ON poll_option USING gin(tokens);

-- 7. Create Materialized Views for Complex Statistics
-- User activity materialized view
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

-- Channel activity by hour
CREATE MATERIALIZED VIEW channel_hourly_stats AS
SELECT 
    channel_id,
    EXTRACT(HOUR FROM created_at) AS hour,
    COUNT(*) AS message_count
FROM messages
WHERE created_at >= NOW() - INTERVAL '30 DAYS'
GROUP BY channel_id, EXTRACT(HOUR FROM created_at);

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
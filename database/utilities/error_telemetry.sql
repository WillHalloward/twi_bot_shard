-- Error telemetry table for tracking errors in the bot
CREATE TABLE IF NOT EXISTS error_telemetry (
    id SERIAL PRIMARY KEY,
    error_type VARCHAR(255) NOT NULL,
    command_name VARCHAR(255) NOT NULL,
    user_id BIGINT NOT NULL,
    error_message TEXT NOT NULL,
    guild_id BIGINT,
    channel_id BIGINT,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolution_notes TEXT
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS error_telemetry_timestamp_idx ON error_telemetry(timestamp);
CREATE INDEX IF NOT EXISTS error_telemetry_error_type_idx ON error_telemetry(error_type);
CREATE INDEX IF NOT EXISTS error_telemetry_command_name_idx ON error_telemetry(command_name);
CREATE INDEX IF NOT EXISTS error_telemetry_user_id_idx ON error_telemetry(user_id);
CREATE INDEX IF NOT EXISTS error_telemetry_resolved_idx ON error_telemetry(resolved);

-- Function to get error statistics
CREATE OR REPLACE FUNCTION get_error_statistics(
    start_date TIMESTAMP DEFAULT (NOW() - INTERVAL '30 days'),
    end_date TIMESTAMP DEFAULT NOW()
)
RETURNS TABLE (
    error_type VARCHAR(255),
    command_name VARCHAR(255),
    error_count BIGINT,
    affected_users BIGINT,
    first_occurrence TIMESTAMP,
    last_occurrence TIMESTAMP
)
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.error_type,
        e.command_name,
        COUNT(*) AS error_count,
        COUNT(DISTINCT e.user_id) AS affected_users,
        MIN(e.timestamp) AS first_occurrence,
        MAX(e.timestamp) AS last_occurrence
    FROM 
        error_telemetry e
    WHERE 
        e.timestamp BETWEEN start_date AND end_date
    GROUP BY 
        e.error_type, e.command_name
    ORDER BY 
        error_count DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get most common errors
CREATE OR REPLACE FUNCTION get_most_common_errors(
    limit_count INTEGER DEFAULT 10,
    start_date TIMESTAMP DEFAULT (NOW() - INTERVAL '30 days'),
    end_date TIMESTAMP DEFAULT NOW()
)
RETURNS TABLE (
    error_type VARCHAR(255),
    error_message TEXT,
    error_count BIGINT,
    affected_users BIGINT,
    first_occurrence TIMESTAMP,
    last_occurrence TIMESTAMP
)
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.error_type,
        e.error_message,
        COUNT(*) AS error_count,
        COUNT(DISTINCT e.user_id) AS affected_users,
        MIN(e.timestamp) AS first_occurrence,
        MAX(e.timestamp) AS last_occurrence
    FROM 
        error_telemetry e
    WHERE 
        e.timestamp BETWEEN start_date AND end_date
    GROUP BY 
        e.error_type, e.error_message
    ORDER BY 
        error_count DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;
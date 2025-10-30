-- Gallery Migration Table
-- This table stores extracted gallery posts for migration to forum format
-- Contains the 5 key fields: title, images, creator, tags, jump_url

CREATE TABLE gallery_migration (
    id SERIAL PRIMARY KEY,
    
    -- Original message information
    message_id BIGINT UNIQUE NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(100) NOT NULL,
    guild_id BIGINT NOT NULL,
    
    -- The 5 key fields for migration
    title TEXT,
    images JSON,  -- Array of image URLs
    creator VARCHAR(200),  -- Creator info (user_id or name)
    tags JSON,  -- Array of tags
    jump_url TEXT,  -- Discord jump URL
    
    -- Additional metadata
    author_id BIGINT NOT NULL,  -- Message author
    author_name VARCHAR(100) NOT NULL,
    is_bot BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,  -- Original message timestamp
    
    -- Migration tracking
    extracted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    migrated BOOLEAN NOT NULL DEFAULT FALSE,
    migrated_at TIMESTAMP,
    target_forum VARCHAR(10),  -- 'sfw' or 'nsfw'
    
    -- Content analysis
    content_type VARCHAR(50),  -- fanart, official, meme, etc.
    has_attachments BOOLEAN NOT NULL DEFAULT FALSE,
    attachment_count INTEGER NOT NULL DEFAULT 0,
    
    -- Manual review tracking
    needs_manual_review BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by BIGINT,
    reviewed_at TIMESTAMP,
    
    -- Raw data for reference
    raw_embed_data JSON,  -- Full embed data
    raw_content TEXT  -- Original message content
);

-- Indexes for performance
CREATE INDEX idx_gallery_migration_message_id ON gallery_migration (message_id);
CREATE INDEX idx_gallery_migration_channel_id ON gallery_migration (channel_id);
CREATE INDEX idx_gallery_migration_migrated ON gallery_migration (migrated);
CREATE INDEX idx_gallery_migration_needs_review ON gallery_migration (needs_manual_review, reviewed);
CREATE INDEX idx_gallery_migration_target_forum ON gallery_migration (target_forum);
CREATE INDEX idx_gallery_migration_content_type ON gallery_migration (content_type);
CREATE INDEX idx_gallery_migration_created_at ON gallery_migration (created_at);
CREATE INDEX idx_gallery_migration_extracted_at ON gallery_migration (extracted_at);

-- Comments for documentation
COMMENT ON TABLE gallery_migration IS 'Stores extracted gallery posts for migration to forum format';
COMMENT ON COLUMN gallery_migration.title IS 'Post title extracted from embed or content';
COMMENT ON COLUMN gallery_migration.images IS 'JSON array of image URLs from embeds and attachments';
COMMENT ON COLUMN gallery_migration.creator IS 'Creator information parsed from "Created by: @user" format';
COMMENT ON COLUMN gallery_migration.tags IS 'JSON array of tags for categorization';
COMMENT ON COLUMN gallery_migration.jump_url IS 'Discord jump URL to original message';
COMMENT ON COLUMN gallery_migration.target_forum IS 'Target forum classification: sfw or nsfw';
COMMENT ON COLUMN gallery_migration.needs_manual_review IS 'Whether entry requires manual review';
COMMENT ON COLUMN gallery_migration.raw_embed_data IS 'Full embed data for reference';
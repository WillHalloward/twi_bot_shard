-- Migration: Add pgvector extension and schema_embeddings table
-- This replaces FAISS for vector similarity search on schema descriptions

-- Enable the pgvector extension (Railway PostgreSQL supports this)
CREATE EXTENSION IF NOT EXISTS vector;

-- Table to store schema descriptions with their embeddings
CREATE TABLE IF NOT EXISTS schema_embeddings (
    id SERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    description TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI text-embedding-3-small outputs 1536 dimensions
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(table_name)
);

-- Create index for fast similarity search using cosine distance
-- IVFFlat is good for datasets up to ~1M vectors
CREATE INDEX IF NOT EXISTS idx_schema_embeddings_vector
ON schema_embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 10);  -- Small number of lists for small dataset

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_schema_embeddings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update timestamp
DROP TRIGGER IF EXISTS schema_embeddings_updated_at ON schema_embeddings;
CREATE TRIGGER schema_embeddings_updated_at
    BEFORE UPDATE ON schema_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_schema_embeddings_timestamp();

-- Comment on table
COMMENT ON TABLE schema_embeddings IS 'Stores schema descriptions with vector embeddings for semantic search in /ask_db command';

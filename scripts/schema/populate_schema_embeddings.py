"""Populate schema embeddings in PostgreSQL using pgvector.

This script replaces the FAISS index builder. It reads schema descriptions
and stores them with their embeddings directly in PostgreSQL.

Usage:
    python scripts/schema/populate_schema_embeddings.py [--from-file|--from-db]

Options:
    --from-file  Load descriptions from schema_descriptions.txt (default)
    --from-db    Auto-generate descriptions from database schema
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncpg
from openai import OpenAI

import config

SCHEMA_FILE = project_root / ".cache/faiss/schema_descriptions.txt"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536


def get_openai_client() -> OpenAI:
    """Get OpenAI client."""
    if not config.openai_api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=config.openai_api_key)


def get_embedding(client: OpenAI, text: str) -> list[float]:
    """Get embedding for a single text."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
    return response.data[0].embedding


def get_embeddings_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Get embeddings for multiple texts in a single API call."""
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [r.embedding for r in response.data]


def load_schema_from_file() -> dict[str, str]:
    """Load schema descriptions from the text file.

    Returns:
        Dict mapping table names to their descriptions.
    """
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")

    with open(SCHEMA_FILE, encoding="utf-8") as f:
        raw = f.read()

    chunks = [chunk.strip() for chunk in raw.split("\n\n") if chunk.strip()]

    # Parse chunks to extract table names
    schema_map = {}
    for chunk in chunks:
        # Try to extract table name from the chunk
        lines = chunk.split("\n")
        if lines:
            # Assume first line contains table name (e.g., "Table: messages" or "messages:")
            first_line = lines[0].lower()
            if "table:" in first_line:
                table_name = first_line.split("table:")[1].strip().split()[0]
            elif ":" in first_line:
                table_name = first_line.split(":")[0].strip()
            else:
                # Use first word as table name
                table_name = first_line.split()[0].strip(":-")

            schema_map[table_name] = chunk

    return schema_map


async def load_schema_from_db(pool: asyncpg.Pool) -> dict[str, str]:
    """Auto-generate schema descriptions from database metadata.

    Returns:
        Dict mapping table names to their auto-generated descriptions.
    """
    # Get all tables and their columns
    query = """
    SELECT
        t.table_name,
        array_agg(
            c.column_name || ' ' || c.data_type ||
            CASE WHEN c.is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END
            ORDER BY c.ordinal_position
        ) as columns,
        obj_description((t.table_schema || '.' || t.table_name)::regclass) as table_comment
    FROM information_schema.tables t
    JOIN information_schema.columns c
        ON t.table_name = c.table_name AND t.table_schema = c.table_schema
    WHERE t.table_schema = 'public'
        AND t.table_type = 'BASE TABLE'
        AND t.table_name NOT IN ('schema_embeddings')  -- Exclude our own table
    GROUP BY t.table_schema, t.table_name
    ORDER BY t.table_name
    """

    rows = await pool.fetch(query)

    schema_map = {}
    for row in rows:
        table_name = row["table_name"]
        columns = row["columns"]
        comment = row["table_comment"] or ""

        # Build description
        description = f"Table: {table_name}\n"
        if comment:
            description += f"Description: {comment}\n"
        description += "Columns:\n"
        for col in columns:
            description += f"  - {col}\n"

        schema_map[table_name] = description.strip()

    return schema_map


async def get_db_pool() -> asyncpg.Pool:
    """Create database connection pool."""
    # Check for DATABASE_URL first (Railway)
    import os
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    else:
        return await asyncpg.create_pool(
            host=config.host,
            port=config.port,
            user=config.DB_user,
            password=config.DB_password,
            database=config.database,
            min_size=1,
            max_size=5,
        )


async def ensure_pgvector_setup(pool: asyncpg.Pool) -> None:
    """Ensure pgvector extension and table exist."""
    async with pool.acquire() as conn:
        # Check if extension exists
        ext_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )

        if not ext_exists:
            print("Creating pgvector extension...")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Check if table exists
        table_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_embeddings')"
        )

        if not table_exists:
            print("Creating schema_embeddings table...")
            await conn.execute("""
                CREATE TABLE schema_embeddings (
                    id SERIAL PRIMARY KEY,
                    table_name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    embedding vector(1536),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Create index
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_schema_embeddings_vector
                ON schema_embeddings USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 10)
            """)


async def upsert_embeddings(
    pool: asyncpg.Pool,
    schema_map: dict[str, str],
    embeddings: dict[str, list[float]]
) -> None:
    """Upsert schema embeddings into the database."""
    async with pool.acquire() as conn:
        for table_name, description in schema_map.items():
            embedding = embeddings.get(table_name)
            if embedding is None:
                print(f"  Warning: No embedding for {table_name}, skipping")
                continue

            # Convert embedding to PostgreSQL vector format
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

            await conn.execute(
                """
                INSERT INTO schema_embeddings (table_name, description, embedding)
                VALUES ($1, $2, $3::vector)
                ON CONFLICT (table_name) DO UPDATE SET
                    description = EXCLUDED.description,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
                """,
                table_name,
                description,
                embedding_str,
            )


async def main(source: str = "file") -> None:
    """Main function to populate schema embeddings."""
    print(f"Populating schema embeddings from {source}...")

    # Get database pool
    print("Connecting to database...")
    pool = await get_db_pool()

    try:
        # Ensure pgvector is set up
        await ensure_pgvector_setup(pool)

        # Load schema descriptions
        print(f"Loading schema from {source}...")
        if source == "file":
            schema_map = load_schema_from_file()
        else:
            schema_map = await load_schema_from_db(pool)

        print(f"Found {len(schema_map)} tables")

        if not schema_map:
            print("No schema descriptions found!")
            return

        # Get OpenAI client
        print("Initializing OpenAI client...")
        client = get_openai_client()

        # Generate embeddings
        print("Generating embeddings...")
        table_names = list(schema_map.keys())
        descriptions = [schema_map[t] for t in table_names]

        # Batch embeddings (OpenAI allows up to 2048 texts per request)
        batch_size = 100
        all_embeddings = []

        for i in range(0, len(descriptions), batch_size):
            batch = descriptions[i:i + batch_size]
            print(f"  Processing batch {i // batch_size + 1}...")
            batch_embeddings = get_embeddings_batch(client, batch)
            all_embeddings.extend(batch_embeddings)

        # Create embedding map
        embeddings_map = dict(zip(table_names, all_embeddings))

        # Upsert to database
        print("Upserting embeddings to database...")
        await upsert_embeddings(pool, schema_map, embeddings_map)

        print(f"Successfully populated {len(schema_map)} schema embeddings!")

    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate schema embeddings")
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Auto-generate descriptions from database schema",
    )
    args = parser.parse_args()

    source = "db" if args.from_db else "file"
    asyncio.run(main(source))

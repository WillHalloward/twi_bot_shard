"""Schema search utilities using pgvector.

This module provides semantic search over database schema descriptions
using PostgreSQL's pgvector extension, replacing the previous FAISS implementation.
"""

import logging
from typing import TYPE_CHECKING

from openai import OpenAI

import config

if TYPE_CHECKING:
    from utils.db import Database

EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TOP_K = 5

logger = logging.getLogger(__name__)


class SchemaSearchError(Exception):
    """Error during schema search operations."""

    pass


def get_openai_client() -> OpenAI:
    """Get OpenAI client for embeddings."""
    if not config.openai_api_key:
        raise SchemaSearchError("OpenAI API key not configured")
    return OpenAI(api_key=config.openai_api_key)


def get_embedding(client: OpenAI, text: str) -> list[float]:
    """Get embedding vector for a text string."""
    try:
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to get embedding: {e}")
        raise SchemaSearchError(f"Failed to generate embedding: {e}") from e


async def search_schema(
    db: "Database",
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[str]:
    """Search for relevant schema descriptions using semantic similarity.

    Args:
        db: Database instance for queries
        query: The user's question to find relevant schema for
        top_k: Number of results to return

    Returns:
        List of schema description strings, ordered by relevance

    Raises:
        SchemaSearchError: If search fails
    """
    try:
        # Get embedding for the query
        client = get_openai_client()
        query_embedding = get_embedding(client, query)

        # Convert to PostgreSQL vector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Search using cosine distance (pgvector uses <=> operator)
        results = await db.fetch(
            """
            SELECT description
            FROM schema_embeddings
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            embedding_str,
            top_k,
        )

        return [row["description"] for row in results]

    except SchemaSearchError:
        raise
    except Exception as e:
        logger.error(f"Schema search failed: {e}")
        raise SchemaSearchError(f"Schema search failed: {e}") from e


async def check_schema_embeddings_exist(db: "Database") -> bool:
    """Check if schema embeddings table exists and has data.

    Args:
        db: Database instance

    Returns:
        True if embeddings are available, False otherwise
    """
    try:
        # Check if table exists
        table_exists = await db.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'schema_embeddings'
            )
            """
        )

        if not table_exists:
            return False

        # Check if there's data
        count = await db.fetchval("SELECT COUNT(*) FROM schema_embeddings")
        return count > 0

    except Exception as e:
        logger.warning(f"Failed to check schema embeddings: {e}")
        return False


def build_sql_prompt(
    question: str,
    schema_chunks: list[str],
    server_id: int | None = None,
    channel_id: int | None = None,
    user_id: int | None = None,
) -> str:
    """Build a prompt for SQL generation.

    Args:
        question: The user's question
        schema_chunks: Relevant schema descriptions
        server_id: Current Discord server ID
        channel_id: Current Discord channel ID
        user_id: User ID of the person asking

    Returns:
        Formatted prompt string for the LLM
    """
    context_info = ""
    if server_id or channel_id or user_id:
        context_info = "\nCurrent Context:\n"
        if server_id:
            context_info += f"- Server ID: {server_id}\n"
        if channel_id:
            context_info += f"- Channel ID: {channel_id}\n"
        if user_id:
            context_info += f"- User ID: {user_id} (the user asking this question)\n"
        context_info += "- When users ask about 'my' or 'me', they are referring to the User ID above\n"
        context_info += "- When users ask about 'this server' or 'here', they are referring to the Server ID above\n"
        context_info += "- When users ask about 'this channel', they are referring to the Channel ID above\n"

    return f"""
You are a PostgreSQL SQL query generator for Cognita, a Discord bot that helps users interact with their Discord server data.

Context:
- This is for a Discord bot called "Cognita" that manages Discord server data
- The database contains information about Discord servers, users, messages, reactions, commands, and other Discord-related data
- Users are asking questions about their Discord server statistics, activity, and data
- The generated query will be executed as-is with no modifications or parameter substitution
{context_info}
Instructions:
- Only return a single valid SELECT SQL query that can be executed directly
- Do NOT include any explanation, comments, or additional text
- Do NOT wrap the query in backticks or markdown formatting
- Do NOT add anything before or after the query
- The query must be standalone and directly executable against a PostgreSQL database
- If you cannot generate a proper SQL query for the question, respond with exactly: "COGNITA_NO_QUERY_POSSIBLE"
- Focus on Discord-related data like servers, users, messages, reactions, commands, etc.
- Consider that this data comes from Discord bot interactions and server monitoring
- Use the context information above to resolve references like 'my', 'me', 'this server', 'here', 'this channel'

Available Schema Information:
{chr(10).join(schema_chunks)}

User Question (from Discord):
\"\"\"{question}\"\"\"
"""


async def generate_sql(
    question: str,
    schema_chunks: list[str],
    server_id: int | None = None,
    channel_id: int | None = None,
    user_id: int | None = None,
    model: str = "gpt-4",
) -> str:
    """Generate SQL from a natural language question.

    Args:
        question: The user's question
        schema_chunks: Relevant schema descriptions
        server_id: Current Discord server ID
        channel_id: Current Discord channel ID
        user_id: User ID of the person asking
        model: OpenAI model to use

    Returns:
        Generated SQL query string

    Raises:
        SchemaSearchError: If SQL generation fails
    """
    try:
        client = get_openai_client()
        prompt = build_sql_prompt(question, schema_chunks, server_id, channel_id, user_id)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a specialized SQL assistant for Cognita, a Discord bot. You help generate PostgreSQL queries to analyze Discord server data including messages, users, reactions, commands, and server statistics. Focus on Discord-related data patterns and common Discord bot use cases.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"SQL generation failed: {e}")
        raise SchemaSearchError(f"Failed to generate SQL: {e}") from e


def extract_sql_from_response(text: str) -> str:
    """Extract SQL query from LLM response.

    Args:
        text: Raw LLM response

    Returns:
        Extracted SQL query or error marker
    """
    import re

    # Check for soft error response first
    if "COGNITA_NO_QUERY_POSSIBLE" in text.strip():
        return "COGNITA_NO_QUERY_POSSIBLE"

    # Prefer code block first
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: find first SELECT up to ;
    match = re.search(r"(SELECT[\s\S]+?;)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Return soft error instead of raising exception
    return "COGNITA_NO_QUERY_POSSIBLE"

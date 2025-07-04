# generate_sql_from_question.py

import faiss
import numpy as np
import json
from openai import OpenAI
import config
# Config
INDEX_FILE = "schema_index.faiss"
LOOKUP_FILE = "schema_lookup.json"
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4"  # or "gpt-3.5-turbo"
TOP_K = 5  # Number of relevant tables to include

client = OpenAI(api_key=config.openai_api_key)

def get_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[text]
    )
    return response.data[0].embedding

def query_faiss(question: str, index_file: str, lookup_file: str, k: int = TOP_K) -> list[str]:
    index = faiss.read_index(index_file)
    with open(lookup_file, "r", encoding="utf-8") as f:
        lookup = json.load(f)
    query_vec = np.array([get_embedding(question)], dtype="float32")
    _, indices = index.search(query_vec, k)
    return [lookup[str(i)] for i in indices[0]]

def build_prompt(question: str, schema_chunks: list[str]) -> str:
    return f"""
You are a PostgreSQL SQL query generator for Cognita, a Discord bot that helps users interact with their Discord server data.

Context:
- This is for a Discord bot called "Cognita" that manages Discord server data
- The database contains information about Discord servers, users, messages, reactions, commands, and other Discord-related data
- Users are asking questions about their Discord server statistics, activity, and data
- The generated query will be executed as-is with no modifications or parameter substitution

Instructions:
- Only return a single valid SELECT SQL query that can be executed directly
- Do NOT include any explanation, comments, or additional text
- Do NOT wrap the query in backticks or markdown formatting
- Do NOT add anything before or after the query
- The query must be standalone and directly executable against a PostgreSQL database
- If you cannot generate a proper SQL query for the question, respond with exactly: "COGNITA_NO_QUERY_POSSIBLE"
- Focus on Discord-related data like servers, users, messages, reactions, commands, etc.
- Consider that this data comes from Discord bot interactions and server monitoring

Available Schema Information:
{chr(10).join(schema_chunks)}

User Question (from Discord):
\"\"\"{question}\"\"\"
"""

def generate_sql(prompt: str) -> str:
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "You are a specialized SQL assistant for Cognita, a Discord bot. You help generate PostgreSQL queries to analyze Discord server data including messages, users, reactions, commands, and server statistics. Focus on Discord-related data patterns and common Discord bot use cases."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()

import re

def extract_sql_from_response(text: str) -> str:
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

def main():
    question = input("🔍 Ask your database: ").strip()

    print("🔗 Searching schema...")
    relevant_schema = query_faiss(question, INDEX_FILE, LOOKUP_FILE)

    print("🧠 Generating prompt...")
    prompt = build_prompt(question, relevant_schema)

    print("🤖 Generating SQL...")
    sql = generate_sql(prompt)

    print("\n✅ Generated SQL:\n")
    print(sql)

    print(extract_sql_from_response(sql))


if __name__ == "__main__":
    main()

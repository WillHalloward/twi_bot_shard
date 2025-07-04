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
You are a PostgreSQL SQL query generator.

Instructions:
- Only return a single valid SELECT SQL query.
- Do NOT include any explanation or comments.
- Do NOT wrap the query in backticks or markdown.
- Do NOT add anything before or after the query.
- The query must be standalone and directly executable.

Schema:
{chr(10).join(schema_chunks)}

Question:
\"\"\"{question}\"\"\"
"""

def generate_sql(prompt: str) -> str:
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "You are a SQL assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()

import re

def extract_sql_from_response(text: str) -> str:
    # Prefer code block first
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: find first SELECT up to ;
    match = re.search(r"(SELECT[\s\S]+?;)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    raise ValueError("No SQL query found in response.")

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

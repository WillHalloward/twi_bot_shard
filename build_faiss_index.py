import openai
import faiss
import numpy as np
import json
from openai import OpenAI
import config

SCHEMA_FILE = "schema_descriptions.txt"
INDEX_FILE = "schema_index.faiss"
LOOKUP_FILE = "schema_lookup.json"
EMBEDDING_MODEL = "text-embedding-3-small"


def load_schema_chunks() -> list[str]:
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        raw = f.read()
    return [chunk.strip() for chunk in raw.split("\n\n") if chunk.strip()]


client = OpenAI(api_key=config.openai_api_key)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [r.embedding for r in response.data]


def build_faiss_index(vectors: list[list[float]]) -> faiss.IndexFlatL2:
    dim = len(vectors[0])
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(vectors).astype("float32"))
    return index


def save_index(index: faiss.IndexFlatL2, filename: str):
    faiss.write_index(index, filename)


def save_lookup(mapping: dict[int, str], filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)


def main():
    print("🔄 Loading schema...")
    schema_chunks = load_schema_chunks()

    print("🔍 Generating embeddings...")
    embeddings = get_embeddings(schema_chunks)

    print("📦 Building FAISS index...")
    index = build_faiss_index(embeddings)

    print(f"💾 Saving FAISS index to {INDEX_FILE}")
    save_index(index, INDEX_FILE)

    print(f"💾 Saving schema lookup to {LOOKUP_FILE}")
    lookup = {i: chunk for i, chunk in enumerate(schema_chunks)}
    save_lookup(lookup, LOOKUP_FILE)

    print("✅ Done! You can now query the schema with FAISS.")


if __name__ == "__main__":
    main()

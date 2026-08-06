"""
Wraps ChromaDB: handles embedding chunks and storing/querying them.
"""
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from chromadb.utils import embedding_functions
from app.config import settings

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")
COLLECTION_NAME = "fda_drug_labels"


def get_client():
    return chromadb.PersistentClient(path=CHROMA_DIR)

def get_embedding_function():
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.embedding_model
    )


def get_or_create_collection():
    client = get_client()
    embed_fn = get_embedding_function()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def add_documents(documents: list[dict]):
    """
    documents: list of dicts with keys: text, drug, section, source, chunk_index
    """
    collection = get_or_create_collection()

    ids = []
    texts = []
    metadatas = []

    for i, doc in enumerate(documents):
        doc_id = f"{doc['drug']}_{doc['section']}_{doc['chunk_index']}_{i}"
        ids.append(doc_id)
        texts.append(doc["text"])
        metadatas.append({
            "drug": doc["drug"],
            "section": doc["section"],
            "source": doc["source"],
            "chunk_index": doc["chunk_index"],
        })

    BATCH_SIZE = 150  # stay safely under ChromaDB's per-call limit
    for start in range(0, len(ids), BATCH_SIZE):
        end = start + BATCH_SIZE
        collection.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )
    return len(ids)


def query_collection(query_text: str, n_results: int = 5, drug_filter: str | None = None):
    collection = get_or_create_collection()

    where_clause = {"drug": drug_filter} if drug_filter else None

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where_clause,
    )
    return results
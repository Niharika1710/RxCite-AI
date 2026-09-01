"""
Wraps ChromaDB: handles embedding chunks and storing/querying them.

Uses Google's hosted Gemini embedding API instead of the local
SentenceTransformer model, which keeps memory usage low for
deployment on Render's free instance.
"""

import os

# Disable Chroma telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings


CHROMA_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "chroma_db",
)

COLLECTION_NAME = "fda_drug_labels"


def get_client():
    """Create and return the persistent ChromaDB client."""
    return chromadb.PersistentClient(path=CHROMA_DIR)


def get_embedding_function():
    """
    Create Google's Gemini embedding function.

    Embeddings are generated through Google's API rather than
    loading Sentence Transformers/PyTorch locally.

    The GOOGLE_API_KEY environment variable must be configured
    in Render.
    """

    return embedding_functions.GoogleGeminiEmbeddingFunction(
        api_key_env_var="GOOGLE_API_KEY",
        model_name="gemini-embedding-001",
        task_type="RETRIEVAL_DOCUMENT",
        dimension=768,
    )


def get_or_create_collection():
    """Get the FDA drug label collection or create it if necessary."""

    client = get_client()
    embed_fn = get_embedding_function()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={
            "hnsw:space": "cosine",
        },
    )

    return collection


def add_documents(documents: list[dict]):
    """
    Add FDA evidence documents to ChromaDB.

    Each document should contain:
        text
        drug
        section
        source
        chunk_index

    Documents are inserted in batches to avoid oversized requests.
    """

    collection = get_or_create_collection()

    ids = []
    texts = []
    metadatas = []

    for i, doc in enumerate(documents):

        doc_id = (
            f"{doc['drug']}_"
            f"{doc['section']}_"
            f"{doc['chunk_index']}_"
            f"{i}"
        )

        ids.append(doc_id)
        texts.append(doc["text"])

        metadatas.append(
            {
                "drug": doc["drug"],
                "section": doc["section"],
                "source": doc["source"],
                "chunk_index": doc["chunk_index"],
            }
        )

    # Keep batches reasonably small
    BATCH_SIZE = 150

    for start in range(0, len(ids), BATCH_SIZE):

        end = start + BATCH_SIZE

        collection.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )

    return len(ids)


def query_collection(
    query_text: str,
    n_results: int = 5,
    drug_filter: str | None = None,
):
    """
    Search the FDA drug-label collection.

    Args:
        query_text: User's question/search text.
        n_results: Number of relevant chunks to return.
        drug_filter: Optional drug name to restrict the search.
    """

    collection = get_or_create_collection()

    where_clause = None

    if drug_filter:
        where_clause = {
            "drug": drug_filter,
        }

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where_clause,
    )

    return results

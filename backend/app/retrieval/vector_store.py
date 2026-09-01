"""
Wraps ChromaDB: handles embedding chunks and storing/querying them.
"""

import os
from typing import List

# Disable Chroma telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

from google import genai

from app.config import settings


CHROMA_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "chroma_db",
)

COLLECTION_NAME = "fda_drug_labels"


# ---------------------------------------------------------
# Gemini Embedding Function
# ---------------------------------------------------------

class GeminiEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Custom ChromaDB embedding function using Google's
    Gemini embedding API.

    This avoids Sentence Transformers and PyTorch,
    which significantly reduces Render memory usage.
    """

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY environment variable is not set."
            )

        self.client = genai.Client(api_key=api_key)

        self.model_name = "gemini-embedding-001"

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []

        for text in input:
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=text,
                config={
                    "task_type": "RETRIEVAL_DOCUMENT",
                    "output_dimensionality": 768,
                },
            )

            embeddings.append(
                response.embeddings[0].values
            )

        return embeddings


# ---------------------------------------------------------
# Chroma Client
# ---------------------------------------------------------

def get_client():
    """Create and return the persistent ChromaDB client."""

    return chromadb.PersistentClient(
        path=CHROMA_DIR
    )


# ---------------------------------------------------------
# Embedding Function
# ---------------------------------------------------------

def get_embedding_function():
    """Return the Gemini embedding function."""

    return GeminiEmbeddingFunction()


# ---------------------------------------------------------
# Collection
# ---------------------------------------------------------

def get_or_create_collection():
    """
    Get the existing ChromaDB collection or create it.
    """

    client = get_client()

    embed_fn = get_embedding_function()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={
            "hnsw:space": "cosine"
        },
    )

    return collection


# ---------------------------------------------------------
# Add Documents
# ---------------------------------------------------------

def add_documents(documents: list[dict]):
    """
    Add documents to ChromaDB.

    Expected format:

    {
        "text": "...",
        "drug": "...",
        "section": "...",
        "source": "...",
        "chunk_index": 0
    }
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

        texts.append(
            doc["text"]
        )

        metadatas.append(
            {
                "drug": doc["drug"],
                "section": doc["section"],
                "source": doc["source"],
                "chunk_index": doc["chunk_index"],
            }
        )

    # Keep batches small to reduce memory usage
    BATCH_SIZE = 50

    for start in range(
        0,
        len(ids),
        BATCH_SIZE
    ):

        end = start + BATCH_SIZE

        collection.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )

    return len(ids)


# ---------------------------------------------------------
# Query
# ---------------------------------------------------------

def query_collection(
    query_text: str,
    n_results: int = 5,
    drug_filter: str | None = None,
):
    """
    Search ChromaDB using semantic similarity.
    """

    collection = get_or_create_collection()

    where_clause = (
        {"drug": drug_filter}
        if drug_filter
        else None
    )

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where_clause,
    )

    return results

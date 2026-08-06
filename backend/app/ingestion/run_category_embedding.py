"""Embed one category into ChromaDB."""
import sys
from app.ingestion.category_ingest import category_to_documents
from app.retrieval.vector_store import add_documents

if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "nsaids"
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    docs = category_to_documents(key, max_pages=pages)
    print(f"\nEmbedding {len(docs)} chunks...")
    count = add_documents(docs)
    print(f"Stored {count} documents.")
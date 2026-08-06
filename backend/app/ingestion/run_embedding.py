"""
One-time script: loads chunked FDA documents and embeds them into ChromaDB.
"""
from app.ingestion.fda_ingest import process_all_to_documents
from app.retrieval.vector_store import add_documents

if __name__ == "__main__":
    print("Loading and chunking FDA documents...")
    docs = process_all_to_documents()
    print(f"Total documents to embed: {len(docs)}")

    print("Embedding and storing in ChromaDB (this calls the OpenAI API)...")
    count = add_documents(docs)
    print(f"Successfully stored {count} documents in ChromaDB.")
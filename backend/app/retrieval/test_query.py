"""
Quick sanity check: query the vector store and inspect results.
"""
from app.retrieval.vector_store import query_collection

def print_results(query: str, drug_filter: str | None = None):
    print(f"\n{'='*60}")
    print(f"QUERY: {query}" + (f"  (filtered to: {drug_filter})" if drug_filter else ""))
    print('='*60)

    results = query_collection(query, n_results=3, drug_filter=drug_filter)

    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for i, (doc, meta, dist) in enumerate(zip(docs, metadatas, distances)):
        print(f"\n--- Result {i+1} (distance: {dist:.4f}) ---")
        print(f"Drug: {meta['drug']} | Section: {meta['section']} | Source: {meta['source']}")
        print(f"Text: {doc[:200]}...")


if __name__ == "__main__":
    print_results("Is warfarin safe during pregnancy?", drug_filter="warfarin")
    print_results("What are the side effects of metformin?", drug_filter="metformin")
    print_results("Can I take ibuprofen with other pain medication?", drug_filter="ibuprofen")
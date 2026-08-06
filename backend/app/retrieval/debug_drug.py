"""Debug what's actually in the vector store for a given drug."""
import sys
from app.retrieval.vector_store import get_or_create_collection, query_collection


def list_drugs():
    collection = get_or_create_collection()
    result = collection.get(include=["metadatas"])
    drugs = {}
    for m in result["metadatas"]:
        d = m.get("drug", "?")
        drugs[d] = drugs.get(d, 0) + 1
    print(f"\nDrugs in vector store ({len(drugs)} distinct):")
    for d, n in sorted(drugs.items()):
        print(f"  {d}: {n} chunks")


def test_query(drug: str, question: str):
    print(f"\n{'='*60}")
    print(f"QUERY: {question}  (filter: {drug})")
    print('='*60)
    results = query_collection(question, n_results=5, drug_filter=drug)
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    if not docs:
        print("NO RESULTS RETURNED")
        return
    for i, (doc, m, dist) in enumerate(zip(docs, metas, dists)):
        print(f"\n[{i+1}] dist={dist:.4f} | {m['drug']} / {m['section']}")
        print(f"    {doc[:160]}...")


if __name__ == "__main__":
    list_drugs()
    drug = sys.argv[1] if len(sys.argv) > 1 else "acetaminophen"
    question = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else f"What is {drug} used for?"
    test_query(drug, question)
"""
Retrieval Agent: searches the vector store for evidence relevant to
the query, scoped to the drug identified by the Router Agent.
"""
from app.retrieval.vector_store import query_collection
from app.models.schemas import RetrievalOutput, EvidenceChunk

DEFAULT_N_RESULTS = 5


def retrieve_evidence(query: str, drug: str | None = None, n_results: int = DEFAULT_N_RESULTS) -> RetrievalOutput:
    """
    Query ChromaDB for the most relevant chunks, optionally filtered to one drug.
    """
    results = query_collection(query, n_results=n_results, drug_filter=drug)

    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    MAX_DISTANCE = 0.75  # drop weak semantic matches before validation

    chunks = [
        EvidenceChunk(
            text=doc,
            drug=meta["drug"],
            section=meta["section"],
            source=meta["source"],
            relevance_score=dist,
        )
        for doc, meta, dist in zip(docs, metadatas, distances)
        if dist <= MAX_DISTANCE
    ]

    return RetrievalOutput(
        query=query,
        drug=drug,
        chunks=chunks,
        chunk_count=len(chunks),
    )


if __name__ == "__main__":
    from app.agents.router_agent import route_query

    test_queries = [
        "Is warfarin safe during pregnancy?",
        "Can I take ibuprofen with alcohol?",
        "Tell me about metformin side effects",
    ]

    for q in test_queries:
        router_result = route_query(q)
        print(f"\n{'='*60}")
        print(f"Query: {q}")
        print(f"Router identified drug: {router_result.identified_drug}")

        if not router_result.is_in_scope:
            print("Out of scope — skipping retrieval.")
            continue

        retrieval_result = retrieve_evidence(q, drug=router_result.identified_drug)
        print(f"Retrieved {retrieval_result.chunk_count} chunks:")
        for i, chunk in enumerate(retrieval_result.chunks):
            print(f"  [{i+1}] {chunk.section} (score: {chunk.relevance_score:.4f}): {chunk.text[:100]}...")
"""
Retrieval Agent: searches the vector store for evidence relevant to
the query, scoped to the drug identified by the Router Agent.

Large FDA labels (e.g. metformin) have hundreds of chunks, and a plain
top-5 nearest-neighbour search gets dominated by whichever section is
bulkiest (usually clinical-trial / adverse-reaction text). That starved
short but critical sections like indications_and_usage, so questions like
"is X indicated for Y?" never saw the indication statement.

Fix: pull a larger candidate pool, then assemble the final set so that
(a) the globally closest chunks are kept, but (b) each distinct section is
represented at least once when it clears the distance threshold. This keeps
side-effect answers strong while making indication/contraindication/dosing
questions actually find their section.
"""
from app.retrieval.vector_store import query_collection
from app.models.schemas import RetrievalOutput, EvidenceChunk

DEFAULT_N_RESULTS = 8       # final chunks handed downstream
CANDIDATE_POOL = 30         # how many to pull before section-diverse selection
MAX_DISTANCE = 0.75         # drop weak semantic matches before validation


def retrieve_evidence(query: str, drug: str | None = None, n_results: int = DEFAULT_N_RESULTS) -> RetrievalOutput:
    """
    Query ChromaDB for relevant chunks (optionally scoped to one drug),
    then select a section-diverse top set so short critical sections
    aren't crowded out by bulky ones.
    """
    # 1) Pull a wide candidate pool so small sections are in the running.
    results = query_collection(query, n_results=CANDIDATE_POOL, drug_filter=drug)

    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    # 2) Build candidate chunks, dropping weak matches up front.
    candidates = [
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

    # Already sorted by distance (closest first) from Chroma, but be safe.
    candidates.sort(key=lambda c: c.relevance_score)

    # 3) Section-diverse selection:
    #    Pass 1 — take the single best chunk from each distinct section.
    #    Pass 2 — fill remaining slots with the next-closest chunks overall.
    chosen: list[EvidenceChunk] = []
    seen_sections: set[str] = set()

    for c in candidates:
        if c.section not in seen_sections:
            chosen.append(c)
            seen_sections.add(c.section)
        if len(chosen) >= n_results:
            break

    if len(chosen) < n_results:
        already = {id(c) for c in chosen}
        for c in candidates:
            if id(c) not in already:
                chosen.append(c)
            if len(chosen) >= n_results:
                break

    # Final ordering by relevance so the closest evidence leads.
    chosen.sort(key=lambda c: c.relevance_score)

    return RetrievalOutput(
        query=query,
        drug=drug,
        chunks=chosen,
        chunk_count=len(chosen),
    )


if __name__ == "__main__":
    from app.agents.router_agent import route_query

    test_queries = [
        "Is warfarin safe during pregnancy?",
        "Can I take ibuprofen with alcohol?",
        "Tell me about metformin side effects",
        "is metformin indicated for type 2 diabetes",
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
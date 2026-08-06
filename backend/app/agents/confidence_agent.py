"""
Confidence Agent: combines retrieval quality, citation agreement, and
coverage into a deterministic, explainable confidence score.
Rule-based by design — not an LLM call — so results are reproducible
and auditable rather than an opaque model judgment.
"""
from app.models.schemas import RetrievalOutput, CitationValidationOutput, ConfidenceOutput

# Tunable thresholds — documented so the scoring logic is transparent
HIGH_THRESHOLD = 0.7
MEDIUM_THRESHOLD = 0.45


def _retrieval_quality_score(retrieval: RetrievalOutput) -> float:
    """
    Converts average cosine distance into a 0-1 quality score.
    Lower distance = higher quality. We treat distance >= 0.8 as ~0 quality,
    and distance == 0 as perfect quality (1.0), scaled linearly.
    """
    if not retrieval.chunks:
        return 0.0
    avg_distance = sum(c.relevance_score for c in retrieval.chunks) / len(retrieval.chunks)
    score = max(0.0, 1.0 - (avg_distance / 0.8))
    return round(min(score, 1.0), 3)


def _agreement_score(citation: CitationValidationOutput) -> float:
    supporting = citation.supporting_count
    total = supporting + citation.contradicting_count + citation.irrelevant_count
    if total == 0:
        return 0.0
    if citation.contradicting_count > 0:
        return round(0.3 * (supporting / total), 3)
    by_count = min(supporting / 3.0, 1.0)
    by_ratio = supporting / total
    return round(max(by_count, by_ratio), 3)

def _coverage_score(citation: CitationValidationOutput, min_supporting: int = 2) -> float:
    """
    Rewards having enough independent supporting chunks, not just one.
    Caps out once we hit min_supporting (default 2) — more isn't
    necessarily better, it's a floor-check.
    """
    return round(min(citation.supporting_count / min_supporting, 1.0), 3)


def compute_confidence(retrieval: RetrievalOutput, citation: CitationValidationOutput) -> ConfidenceOutput:
    retrieval_score = _retrieval_quality_score(retrieval)
    agreement = _agreement_score(citation)
    coverage = _coverage_score(citation)

    # Weighted combination — agreement matters most (safety-critical),
    # then coverage, then raw retrieval quality
    overall = round((agreement * 0.5) + (coverage * 0.3) + (retrieval_score * 0.2), 3)

    if overall >= HIGH_THRESHOLD:
        level = "High"
    elif overall >= MEDIUM_THRESHOLD:
        level = "Medium"
    else:
        level = "Low"

    reasoning_parts = []
    if citation.contradicting_count > 0:
        reasoning_parts.append(f"{citation.contradicting_count} source(s) contradict each other")
    reasoning_parts.append(f"{citation.supporting_count}/{citation.supporting_count + citation.contradicting_count + citation.irrelevant_count} retrieved chunks genuinely support the query")
    reasoning_parts.append(f"average retrieval similarity was {'strong' if retrieval_score > 0.6 else 'moderate' if retrieval_score > 0.3 else 'weak'}")

    reasoning = "; ".join(reasoning_parts) + "."

    return ConfidenceOutput(
        query=retrieval.query,
        confidence_level=level,
        confidence_score=overall,
        reasoning=reasoning,
        retrieval_quality_score=retrieval_score,
        agreement_score=agreement,
        coverage_score=coverage,
    )

def downgrade_for_unanswered(confidence: ConfidenceOutput) -> ConfidenceOutput:
    """
    Retrieval quality measures whether the evidence is GOOD.
    It cannot measure whether the evidence ANSWERS THE QUESTION —
    only the response agent, reading the chunks against the query, knows that.
    When it reports the evidence falls short, confidence must collapse:
    a high score on a non-answer is worse than no score at all.
    """
    return ConfidenceOutput(
        query=confidence.query,
        confidence_level="Low",
        confidence_score=min(confidence.confidence_score, 0.2),
        reasoning=(
            confidence.reasoning
            + " Downgraded: retrieved evidence was well-matched but did not "
              "address what was actually asked."
        ),
        retrieval_quality_score=confidence.retrieval_quality_score,
        agreement_score=confidence.agreement_score,
        coverage_score=confidence.coverage_score,
    )

if __name__ == "__main__":
    from app.agents.router_agent import route_query
    from app.agents.retrieval_agent import retrieve_evidence
    from app.agents.citation_agent import validate_evidence

    test_queries = [
        "Is warfarin safe during pregnancy?",
        "What's the weather like today?",  # will fail earlier, skip
        "Can I take ibuprofen with alcohol?",
    ]

    for q in test_queries:
        router_result = route_query(q)
        if not router_result.is_in_scope:
            print(f"\nQuery: {q}\n  Out of scope — skipping.")
            continue

        retrieval_result = retrieve_evidence(q, drug=router_result.identified_drug)
        citation_result = validate_evidence(q, retrieval_result.chunks)
        confidence_result = compute_confidence(retrieval_result, citation_result)

        print(f"\n{'='*60}")
        print(f"Query: {q}")
        print(f"Confidence: {confidence_result.confidence_level} (score: {confidence_result.confidence_score})")
        print(f"  Retrieval quality: {confidence_result.retrieval_quality_score}")
        print(f"  Agreement: {confidence_result.agreement_score}")
        print(f"  Coverage: {confidence_result.coverage_score}")
        print(f"  Reasoning: {confidence_result.reasoning}")
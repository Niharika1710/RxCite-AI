"""
Safety & Refusal Agent: makes the final go/no-go decision on whether
to answer, based on confidence level, evidence contradictions, and
coverage. Rule-based and deterministic — this is a safety gate, not
something an LLM should be persuadable out of.
"""
from app.models.schemas import (
    RouterOutput,
    ConfidenceOutput,
    CitationValidationOutput,
    SafetyOutput,
)

MIN_SUPPORTING_CHUNKS_TO_ANSWER = 2


def evaluate_safety(
    router: RouterOutput,
    confidence: ConfidenceOutput,
    citation: CitationValidationOutput,
) -> SafetyOutput:
    flags = []

    # Gate 1: out of scope entirely
    if not router.is_in_scope:
        return SafetyOutput(
            query=router.original_query,
            should_refuse=True,
            refusal_reason="This question is outside the pharmaceutical knowledge domain this system covers.",
            safety_flags=["out_of_scope"],
            recommendation="Please rephrase your question to focus on drug safety, usage, or interactions.",
        )

    # Gate 2: no drug identified at all
    if not router.identified_drug:
        return SafetyOutput(
            query=router.original_query,
            should_refuse=True,
            refusal_reason="No specific drug could be identified in this question from our supported knowledge base.",
            safety_flags=["no_drug_identified"],
            recommendation="Please specify the exact drug name you're asking about.",
        )

    # Gate 3: contradicting evidence — always a hard stop regardless of confidence score
    if citation.contradicting_count > 0:
        flags.append("source_contradiction")
        return SafetyOutput(
            query=router.original_query,
            should_refuse=True,
            refusal_reason="Retrieved evidence sources contain conflicting information, which cannot be safely resolved automatically.",
            safety_flags=flags,
            recommendation="Consult a healthcare professional for guidance specific to your situation.",
        )

   # Hard refusal: Low confidence OR zero supporting evidence.
    if confidence.confidence_level == "Low" or citation.supporting_count == 0:
        flags.append("low_confidence" if confidence.confidence_level == "Low" else "no_supporting_evidence")
        return SafetyOutput(
            query=router.original_query,
            should_refuse=True,
            refusal_reason=f"Available evidence is insufficient to provide a reliable answer (confidence: {confidence.confidence_level}).",
            safety_flags=flags,
            recommendation="Consult a healthcare professional for a reliable answer to this question.",
        )

    # Soft caveat: answer, but flag limited evidence (e.g. sparse OTC labels).
    if citation.supporting_count < MIN_SUPPORTING_CHUNKS_TO_ANSWER or confidence.confidence_level == "Medium":
        flags.append("limited_evidence")
        return SafetyOutput(
            query=router.original_query,
            should_refuse=False,   # we DO answer
            refusal_reason=None,
            safety_flags=flags,
            recommendation="This answer is based on limited evidence. Confirm with a healthcare professional.",
        )

    # Full pass — High confidence, strong coverage.
    return SafetyOutput(
        query=router.original_query,
        should_refuse=False,
        refusal_reason=None,
        safety_flags=[],
        recommendation=None,
    )


if __name__ == "__main__":
    from app.agents.router_agent import route_query
    from app.agents.retrieval_agent import retrieve_evidence
    from app.agents.citation_agent import validate_evidence
    from app.agents.confidence_agent import compute_confidence

    test_queries = [
        "Is warfarin safe during pregnancy?",
        "What's the weather like today?",
        "Can I take ibuprofen with alcohol?",
        "Tell me about metformin side effects",
    ]

    for q in test_queries:
        router_result = route_query(q)
        print(f"\n{'='*60}")
        print(f"Query: {q}")

        if not router_result.is_in_scope:
            # still run through safety agent to test the out-of-scope gate
            fake_confidence = None
            fake_citation = None
            # We can't compute confidence without retrieval, so build a minimal safety check
            from app.models.schemas import ConfidenceOutput, CitationValidationOutput
            dummy_confidence = ConfidenceOutput(
                query=q, confidence_level="Low", confidence_score=0.0,
                reasoning="N/A", retrieval_quality_score=0.0,
                agreement_score=0.0, coverage_score=0.0,
            )
            dummy_citation = CitationValidationOutput(
                query=q, verdicts=[], supporting_count=0,
                contradicting_count=0, irrelevant_count=0,
            )
            safety_result = evaluate_safety(router_result, dummy_confidence, dummy_citation)
            print(f"Should refuse: {safety_result.should_refuse}")
            print(f"Reason: {safety_result.refusal_reason}")
            print(f"Flags: {safety_result.safety_flags}")
            continue

        retrieval_result = retrieve_evidence(q, drug=router_result.identified_drug)
        citation_result = validate_evidence(q, retrieval_result.chunks)
        confidence_result = compute_confidence(retrieval_result, citation_result)
        safety_result = evaluate_safety(router_result, confidence_result, citation_result)

        print(f"Confidence: {confidence_result.confidence_level}")
        print(f"Should refuse: {safety_result.should_refuse}")
        if safety_result.should_refuse:
            print(f"Reason: {safety_result.refusal_reason}")
            print(f"Flags: {safety_result.safety_flags}")
            print(f"Recommendation: {safety_result.recommendation}")
        else:
            print("-> Safe to proceed to answer generation.")
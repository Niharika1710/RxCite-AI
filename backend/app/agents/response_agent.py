"""
Response Generation Agent: produces the final structured answer.
- If safety says refuse: formats a clean, honest refusal.
- If safety says proceed: generates an answer grounded ONLY in the
  supporting evidence, with citations linked to FDA label sections.
"""
import json
from app.agents.confidence_agent import downgrade_for_unanswered
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.models.schemas import (
    RetrievalOutput,
    CitationValidationOutput,
    ConfidenceOutput,
    SafetyOutput,
    ResponseOutput,
    Citation,
)
from urllib.parse import quote_plus

def _dailymed_url(drug: str) -> str:
    """Deterministic link to the official DailyMed (FDA) label search for a drug."""
    return f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={quote_plus(drug)}&labeltype=all"


GENERATION_SYSTEM_PROMPT = """You are a careful pharmaceutical information assistant.

You will be given a QUESTION and a set of EVIDENCE passages from FDA drug labels.

STRICT RULES:
- Answer ONLY using the provided evidence. Do not add outside knowledge.
- Be clear, factual, and concise. Do not give personal medical advice.
- Do not fabricate any information not present in the evidence.

ANSWERABILITY — judge this honestly and independently:
Set "answers_question" to false if the evidence does not actually address what was
asked, even if the passages are about a relevant drug. Evidence about drug A does
not answer a question about which drug B to choose. Partial or tangential coverage
counts as false. Set it to true only when the evidence genuinely supports a direct
answer to the question asked.

Respond ONLY with valid JSON in this exact format, no other text:
{{"answer": "your evidence-grounded answer here", "explanation": "one sentence on why this answer follows from the evidence", "answers_question": true}}
"""


def get_llm():
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
    )


def _extract_text(response) -> str:
    if isinstance(response.content, list):
        raw = "".join(
            block["text"] if isinstance(block, dict) and "text" in block else str(block)
            for block in response.content
        ).strip()
    else:
        raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def _call_llm(llm, system_msg, user_msg):
    return llm.invoke([("system", system_msg), ("human", user_msg)])


def generate_response(
    retrieval: RetrievalOutput,
    citation: CitationValidationOutput,
    confidence: ConfidenceOutput,
    safety: SafetyOutput,
) -> ResponseOutput:

    # --- Refusal path ---
    if safety.should_refuse:
        return ResponseOutput(
            query=safety.query,
            answer="I cannot provide a reliable recommendation for this question.",
            confidence_level=confidence.confidence_level if confidence else "Low",
            citations=[],
            explanation=safety.refusal_reason or "Insufficient reliable evidence.",
            is_refusal=True,
            recommendation=safety.recommendation,
        )

    # --- Answer path ---
    # Only feed the SUPPORTING chunks to the generator (validated evidence only)
    supporting_verdicts = [v for v in citation.verdicts if v.verdict == "supports"]

    evidence_text = "\n\n".join(
        f"[{v.drug} | {v.section} | {v.source}]\n{v.chunk_text}"
        for v in supporting_verdicts
    )

    user_msg = f"QUESTION: {retrieval.query}\n\nEVIDENCE:\n{evidence_text}"

    llm = get_llm()
    response = _call_llm(llm, GENERATION_SYSTEM_PROMPT, user_msg)
    try:
        parsed = json.loads(_extract_text(response))
    except json.JSONDecodeError:
        parsed = {
            "answer": "I could not produce a reliable answer from the retrieved evidence.",
            "explanation": "Response generation returned malformed output.",
            "answers_question": False,
        }

    answers_question = bool(parsed.get("answers_question", True))

    # The evidence didn't address the question — collapse the confidence claim.
    effective_confidence = confidence
    if not answers_question:
        effective_confidence = downgrade_for_unanswered(confidence)

    # Build citations from the supporting chunks (deduplicated by section)
    seen = set()
    citations = []
    for v in supporting_verdicts:
        key = (v.drug, v.section, v.source)
        if key not in seen:
            seen.add(key)
            citations.append(Citation(
                drug=v.drug,
                section=v.section,
                source=v.source,
                url=_dailymed_url(v.drug),
            ))
    return ResponseOutput(
        query=retrieval.query,
        answer=parsed["answer"],
        confidence_level=effective_confidence.confidence_level,
        citations=citations if answers_question else [],
        explanation=parsed["explanation"],
        is_refusal=False,
        evidence_answers_question=answers_question,
        recommendation=(
            None if answers_question
            else "Our FDA label evidence doesn't cover this specific combination. "
                 "Please consult a pharmacist or physician."
        ),
    )


if __name__ == "__main__":
    from app.agents.router_agent import route_query
    from app.agents.retrieval_agent import retrieve_evidence
    from app.agents.citation_agent import validate_evidence
    from app.agents.confidence_agent import compute_confidence
    from app.agents.safety_agent import evaluate_safety

    test_queries = [
        "Is warfarin safe during pregnancy?",
        "Can I take ibuprofen with alcohol?",
    ]

    for q in test_queries:
        router_result = route_query(q)
        retrieval_result = retrieve_evidence(q, drug=router_result.identified_drug) if router_result.is_in_scope else RetrievalOutput(query=q, drug=None, chunks=[], chunk_count=0)
        citation_result = validate_evidence(q, retrieval_result.chunks) if retrieval_result.chunks else CitationValidationOutput(query=q, verdicts=[], supporting_count=0, contradicting_count=0, irrelevant_count=0)
        confidence_result = compute_confidence(retrieval_result, citation_result)
        safety_result = evaluate_safety(router_result, confidence_result, citation_result)
        response = generate_response(retrieval_result, citation_result, confidence_result, safety_result)

        print(f"\n{'='*60}")
        print(f"QUERY: {response.query}")
        print(f"\nANSWER: {response.answer}")
        print(f"\nCONFIDENCE: {response.confidence_level}")
        print(f"REFUSAL: {response.is_refusal}")
        if response.citations:
            print("CITATIONS:")
            for c in response.citations:
                print(f"  - {c.source}: {c.drug} / {c.section}")
        print(f"EXPLANATION: {response.explanation}")
        if response.recommendation:
            print(f"RECOMMENDATION: {response.recommendation}")
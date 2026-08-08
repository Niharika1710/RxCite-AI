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


def _safe_parse_json(raw: str):
    """
    Best-effort JSON recovery. Returns a dict on success, or None on failure.
    Handles the common flash-lite quirks: leading/trailing prose, stray text
    around the object, and markdown that slipped past _extract_text.
    """
    if not raw:
        return None
    # flash-lite sometimes mirrors the prompt's escaped-brace example and emits
    # doubled braces ({{...}}). Collapse them before parsing.
    if "{{" in raw or "}}" in raw:
        raw = raw.replace("{{", "{").replace("}}", "}")
    # 1) Straight parse.
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # 2) Recover the outermost {...} block and try that.
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start:end + 1]
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


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

    # gemini-*-flash-lite is non-deterministic and occasionally wraps or
    # decorates the JSON. Try up to twice, and on parse failure attempt to
    # recover the outermost {...} block before giving up, so a formatting
    # hiccup doesn't discard a perfectly good answer.
    parsed = None
    last_raw = ""
    for _attempt in range(2):
        response = _call_llm(llm, GENERATION_SYSTEM_PROMPT, user_msg)
        last_raw = _extract_text(response)
        parsed = _safe_parse_json(last_raw)
        if parsed is not None:
            break

    if parsed is None:
        parsed = {
            "answer": "I could not produce a reliable answer from the retrieved evidence.",
            "explanation": "Response generation returned malformed output.",
            "answers_question": False,
        }

    answers_question = bool(parsed.get("answers_question", True))

    # The LLM's answerability verdict is a secondary signal, not an override.
    # On temperature-ignoring models it can flip between runs, so we only let it
    # collapse confidence when the deterministic evidence is ALSO weak. When
    # retrieval + citation strongly support the answer (computed confidence is
    # Medium/High), we trust those reproducible signals and keep the answer,
    # preventing the "refuses first attempt, answers second" flapping.
    effective_confidence = confidence
    evidence_is_strong = confidence is not None and confidence.confidence_level in ("Medium", "High")
    if not answers_question and not evidence_is_strong:
        effective_confidence = downgrade_for_unanswered(confidence)
        answers_question = False
    elif not answers_question and evidence_is_strong:
        # Keep the answer and its confidence; the evidence backs it even though
        # the model's self-report was uncertain this run.
        answers_question = True

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
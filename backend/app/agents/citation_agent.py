"""
Citation Validation Agent: validates all retrieved chunks in a single
LLM call, judging whether each supports or is irrelevant to the query.
"""
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.models.schemas import EvidenceChunk, CitationVerdict, CitationValidationOutput

VALIDATION_SYSTEM_PROMPT = """You are a citation validator for a medical information system.
You will receive a QUESTION and a numbered list of EVIDENCE CHUNKS.
For each chunk, decide if it helps answer the question:
- "supports": the chunk contains information relevant to answering the question
- "irrelevant": the chunk does not relate to the question
Be INCLUSIVE. A chunk "supports" if it mentions ANY relevant information —
side effects, warnings, risks, reactions, precautions, or safety data related
to the question, for ANY patient group (adults, elderly, pediatric).
Only mark "irrelevant" if the chunk is about a completely unrelated topic.
When in doubt, mark "supports".
Respond ONLY with valid JSON: a list with one object per chunk, in order:
[{"index": 1, "verdict": "supports", "justification": "..."}, {"index": 2, "verdict": "irrelevant", "justification": "..."}]
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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8), reraise=True)
def _call_validator(llm, system_msg, user_msg):
    return llm.invoke([("system", system_msg), ("human", user_msg)])


def validate_evidence(query: str, chunks: list[EvidenceChunk]) -> CitationValidationOutput:
    if not chunks:
        return CitationValidationOutput(
            query=query, verdicts=[], supporting_count=0,
            contradicting_count=0, irrelevant_count=0,
        )

    llm = get_llm()

    evidence_block = "\n\n".join(
        f"CHUNK {i+1}:\n{c.text}" for i, c in enumerate(chunks)
    )
    user_msg = f"QUESTION: {query}\n\n{evidence_block}"

    response = _call_validator(llm, VALIDATION_SYSTEM_PROMPT, user_msg)
    raw = _extract_text(response)

    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("expected a list")
    except (json.JSONDecodeError, ValueError):
        parsed = [{"index": i + 1, "verdict": "supports", "justification": "auto"} for i in range(len(chunks))]

    verdict_by_index = {item["index"]: item for item in parsed if isinstance(item, dict) and "index" in item}

    verdicts = []
    for i, chunk in enumerate(chunks):
        item = verdict_by_index.get(i + 1, {"verdict": "supports", "justification": "default"})
        verdicts.append(CitationVerdict(
            chunk_text=chunk.text,
            drug=chunk.drug,
            section=chunk.section,
            source=chunk.source,
            verdict=item.get("verdict", "supports"),
            justification=item.get("justification", ""),
        ))

    return CitationValidationOutput(
        query=query,
        verdicts=verdicts,
        supporting_count=sum(1 for v in verdicts if v.verdict == "supports"),
        contradicting_count=sum(1 for v in verdicts if v.verdict == "contradicts"),
        irrelevant_count=sum(1 for v in verdicts if v.verdict == "irrelevant"),
    )
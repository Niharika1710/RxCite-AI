"""
Citation Validation Agent (deterministic).

Previously this made an LLM call to judge whether each chunk "supports" the
query. On models that ignore temperature (e.g. gemini-*-flash-lite) that call
is non-reproducible: the supporting set — and therefore the downstream
confidence score — changed between identical runs, causing the same question
to flip between a confident answer and a refusal.

Retrieval distance is deterministic (fixed embedding model), so we derive the
verdict from it directly. A chunk that cleared the retrieval distance filter is
semantically relevant to the query by construction; we grade it "supports",
with a tighter band marked as strong support. This makes the whole
retrieval -> citation -> confidence path reproducible: same input, same output.
"""
from app.models.schemas import EvidenceChunk, CitationVerdict, CitationValidationOutput

# Distance bands (cosine distance; lower = closer).
# Chunks arriving here already passed retrieval's MAX_DISTANCE (0.75) filter.
SUPPORT_DISTANCE = 0.60   # <= this: counts as genuine support
# between SUPPORT_DISTANCE and the retrieval cutoff: weak/irrelevant


def validate_evidence(query: str, chunks: list[EvidenceChunk]) -> CitationValidationOutput:
    if not chunks:
        return CitationValidationOutput(
            query=query, verdicts=[], supporting_count=0,
            contradicting_count=0, irrelevant_count=0,
        )

    verdicts: list[CitationVerdict] = []
    for c in chunks:
        if c.relevance_score <= SUPPORT_DISTANCE:
            verdict = "supports"
            justification = f"Semantic distance {round(c.relevance_score, 3)} within support band."
        else:
            verdict = "irrelevant"
            justification = f"Semantic distance {round(c.relevance_score, 3)} too far to count as support."

        verdicts.append(CitationVerdict(
            chunk_text=c.text,
            drug=c.drug,
            section=c.section,
            source=c.source,
            verdict=verdict,
            justification=justification,
        ))

    return CitationValidationOutput(
        query=query,
        verdicts=verdicts,
        supporting_count=sum(1 for v in verdicts if v.verdict == "supports"),
        contradicting_count=0,  # distance alone can't detect contradiction
        irrelevant_count=sum(1 for v in verdicts if v.verdict == "irrelevant"),
    )
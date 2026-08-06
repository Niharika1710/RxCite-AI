"""Trace one query through every agent to see where confidence drops."""
import sys
from app.agents.router_agent import route_query
from app.agents.retrieval_agent import retrieve_evidence
from app.agents.citation_agent import validate_evidence
from app.agents.confidence_agent import compute_confidence

q = " ".join(sys.argv[1:]) or "What are the serious risks of taking gabapentin?"

router = route_query(q)
print(f"\nQUERY: {q}")
print(f"Drug: {router.identified_drug} | in_scope: {router.is_in_scope}")

retrieval = retrieve_evidence(q, drug=router.identified_drug)
print(f"\nRetrieved {retrieval.chunk_count} chunks (after distance filter):")
for c in retrieval.chunks:
    print(f"  dist={c.relevance_score:.3f} | {c.section}")

citation = validate_evidence(q, retrieval.chunks)
print(f"\nCitation verdicts:")
for v in citation.verdicts:
    print(f"  {v.verdict.upper():12} | {v.section} | {v.justification[:70]}")
print(f"\nSupporting: {citation.supporting_count} | Contradicting: {citation.contradicting_count} | Irrelevant: {citation.irrelevant_count}")

conf = compute_confidence(retrieval, citation)
print(f"\nConfidence: {conf.confidence_level} ({conf.confidence_score})")
print(f"  retrieval_quality={conf.retrieval_quality_score} agreement={conf.agreement_score} coverage={conf.coverage_score}")
"""
Router Agent: determines whether a query is in-scope (pharmaceutical)
and which known drug it relates to, before any retrieval happens.
"""
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.models.schemas import EvidenceChunk, CitationVerdict, CitationValidationOutput
from app.models.schemas import RouterOutput

# The drugs our knowledge base actually covers right now.
from app.retrieval.vector_store import get_or_create_collection

def get_known_drugs() -> list[str]:
    """Read the distinct drugs actually present in the vector store."""
    collection = get_or_create_collection()
    result = collection.get(include=["metadatas"])
    drugs = {m["drug"] for m in result["metadatas"] if m.get("drug")}
    return sorted(drugs)

KNOWN_DRUGS = get_known_drugs()
ROUTER_SYSTEM_PROMPT = """You are a routing classifier for a pharmaceutical safety assistant.

Given a user's question, determine:
1. is_in_scope: true if this is a genuine question about drug safety, usage, side effects, interactions, or dosage. false if it's off-topic (e.g. weather, general chit-chat, unrelated topics).
2. identified_drug: which ONE drug from this list the question is about: {known_drugs}. If the question doesn't clearly relate to any of these drugs, return null.
3. reasoning: one short sentence explaining your decision.

Respond ONLY with valid JSON in this exact format, no other text:
{{"is_in_scope": true, "identified_drug": "warfarin", "reasoning": "..."}}
"""


def get_llm():
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def route_query(query: str) -> RouterOutput:
    llm = get_llm()

    system_msg = ROUTER_SYSTEM_PROMPT.format(known_drugs=", ".join(KNOWN_DRUGS))

    response = llm.invoke([
        ("system", system_msg),
        ("human", query),
    ])

    # LangChain 1.x: response.content can be a string OR a list of content blocks
    if isinstance(response.content, list):
        raw_text = "".join(
            block["text"] if isinstance(block, dict) and "text" in block else str(block)
            for block in response.content
        ).strip()
    else:
        raw_text = response.content.strip()

    # Gemini sometimes wraps JSON in markdown code fences — strip those if present
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # LLM returned malformed JSON — fail safe rather than crash
        parsed = {
            "is_in_scope": False,
            "identified_drug": None,
            "reasoning": f"Could not parse routing response. Raw output: {raw_text[:200]}",
        }

    return RouterOutput(
        original_query=query,
        is_in_scope=parsed["is_in_scope"],
        identified_drug=parsed.get("identified_drug"),
        reasoning=parsed["reasoning"],
    )

if __name__ == "__main__":
    test_queries = [
        "Is warfarin safe during pregnancy?",
        "What's the weather like today?",
        "Can I take ibuprofen with alcohol?",
        "Tell me about metformin side effects",
    ]

    for q in test_queries:
        result = route_query(q)
        print(f"\nQuery: {q}")
        print(f"  In scope: {result.is_in_scope}")
        print(f"  Drug: {result.identified_drug}")
        print(f"  Reasoning: {result.reasoning}")
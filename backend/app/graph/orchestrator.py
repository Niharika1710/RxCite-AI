"""
LangGraph orchestration: wires all six agents into a state graph with
conditional routing. Out-of-scope queries short-circuit straight to
refusal, skipping retrieval and all downstream LLM calls.
"""

from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver
from app.agents.triage_agent import assess_intake
from app.models.schemas import IntakeSlots, TriageOutput
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, START, END

from app.agents.router_agent import route_query
from app.agents.retrieval_agent import retrieve_evidence
from app.agents.citation_agent import validate_evidence
from app.agents.confidence_agent import compute_confidence
from app.agents.safety_agent import evaluate_safety
from app.agents.response_agent import generate_response

from app.models.schemas import (
    RouterOutput,
    RetrievalOutput,
    CitationValidationOutput,
    ConfidenceOutput,
    SafetyOutput,
    ResponseOutput,
)

import sqlite3
import uuid

# --- Graph state: holds every agent's output as it flows through ---
class GraphState(TypedDict, total=False):
    query: str
    intake: Optional[IntakeSlots]
    intake_replies: list[str]
    triage_output: Optional[TriageOutput]
    router_output: Optional[RouterOutput]
    retrieval_output: Optional[RetrievalOutput]
    citation_output: Optional[CitationValidationOutput]
    confidence_output: Optional[ConfidenceOutput]
    safety_output: Optional[SafetyOutput]
    response_output: Optional[ResponseOutput]


# --- Node functions: each reads state, runs an agent, writes back ---

def router_node(state: GraphState) -> GraphState:
    result = route_query(state["query"])
    return {"router_output": result}


def retrieval_node(state: GraphState) -> GraphState:
    router = state["router_output"]
    result = retrieve_evidence(state["query"], drug=router.identified_drug)
    return {"retrieval_output": result}


def citation_node(state: GraphState) -> GraphState:
    retrieval = state["retrieval_output"]
    result = validate_evidence(state["query"], retrieval.chunks)
    return {"citation_output": result}


def confidence_node(state: GraphState) -> GraphState:
    result = compute_confidence(state["retrieval_output"], state["citation_output"])
    return {"confidence_output": result}


def safety_node(state: GraphState) -> GraphState:
    # Handle both the full path and the short-circuit path.
    # If retrieval/citation/confidence didn't run, build minimal placeholders.
    router = state["router_output"]
    confidence = state.get("confidence_output")
    citation = state.get("citation_output")

    if confidence is None:
        confidence = ConfidenceOutput(
            query=state["query"], confidence_level="Low", confidence_score=0.0,
            reasoning="Not evaluated (out of scope).", retrieval_quality_score=0.0,
            agreement_score=0.0, coverage_score=0.0,
        )
    if citation is None:
        citation = CitationValidationOutput(
            query=state["query"], verdicts=[], supporting_count=0,
            contradicting_count=0, irrelevant_count=0,
        )

    result = evaluate_safety(router, confidence, citation)
    return {"safety_output": result, "confidence_output": confidence, "citation_output": citation}


def response_node(state: GraphState) -> GraphState:
    retrieval = state.get("retrieval_output")
    if retrieval is None:
        retrieval = RetrievalOutput(query=state["query"], drug=None, chunks=[], chunk_count=0)

    result = generate_response(
        retrieval,
        state["citation_output"],
        state["confidence_output"],
        state["safety_output"],
    )
    return {"response_output": result}


MAX_TRIAGE_ROUNDS = 3


def triage_node(state: GraphState) -> GraphState:
    replies = list(state.get("intake_replies", []))
    qa_pairs: list[tuple[str, str]] = []

    result = assess_intake(state["query"], replies, qa_pairs)

    rounds = 0
    while not result.is_complete and rounds < MAX_TRIAGE_ROUNDS:
        question = result.follow_up_question
        user_reply = interrupt({
            "type": "intake_question",
            "question": question,
            "missing_slots": result.missing_slots,
        })
        reply_text = str(user_reply)
        replies.append(reply_text)
        qa_pairs.append((question, reply_text))   # remember WHAT was asked
        rounds += 1
        result = assess_intake(state["query"], replies, qa_pairs)

    if not result.is_complete:
        result.is_complete = True
        result.follow_up_question = None
        result.reasoning += " (Max intake rounds reached; proceeding.)"

    return {"intake": result.slots, "triage_output": result, "intake_replies": replies}

def route_after_router(state: GraphState) -> str:
    """Out of scope -> refuse. In scope -> gather context first."""
    router = state["router_output"]
    if not router.is_in_scope:
        return "safety"
    return "triage"


def route_after_triage(state: GraphState) -> str:
    """Intake is done by the time we get here; refuse if no drug matched."""
    if not state["router_output"].identified_drug:
        return "safety"
    return "retrieval"

# --- Build the graph ---

def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("router", router_node)
    graph.add_node("triage", triage_node)          # NEW
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("citation", citation_node)
    graph.add_node("confidence", confidence_node)
    graph.add_node("safety", safety_node)
    graph.add_node("response", response_node)

    graph.add_edge(START, "router")

    graph.add_conditional_edges(
        "router", route_after_router,
        {"triage": "triage", "safety": "safety"},
    )
    graph.add_conditional_edges(
        "triage", route_after_triage,
        {"retrieval": "retrieval", "safety": "safety"},
    )

    graph.add_edge("retrieval", "citation")
    graph.add_edge("citation", "confidence")
    graph.add_edge("confidence", "safety")
    graph.add_edge("safety", "response")
    graph.add_edge("response", END)

    # Persistent checkpointer: paused conversations survive a server restart.
    conn = sqlite3.connect("medintel_checkpoints.sqlite", check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return graph.compile(checkpointer=checkpointer)


# Compile once at import so it's reused
medintel_graph = build_graph()



def _shape(result: dict, thread_id: str) -> dict:
    """Normalise a graph result into either a question or a final answer."""
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        return {
            "thread_id": thread_id,
            "awaiting_input": True,
            "question": payload.get("question"),
            "response": None,
        }
    return {
        "thread_id": thread_id,
        "awaiting_input": False,
        "question": None,
        "response": result["response_output"],
    }


def start_query(query: str, thread_id: str | None = None) -> dict:
    """Begin a new conversation turn. May pause for intake."""
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    result = medintel_graph.invoke({"query": query, "intake_replies": []}, config)
    return _shape(result, thread_id)


def resume_query(thread_id: str, reply: str) -> dict:
    """Resume a paused conversation with the user's answer."""
    config = {"configurable": {"thread_id": thread_id}}
    result = medintel_graph.invoke(Command(resume=reply), config)
    return _shape(result, thread_id)

if __name__ == "__main__":
    scenarios = [
        ("What are metformin side effects?",
         "No further details"),
        ("Can I take ibuprofen for a headache?",
         "I'm 42, no stomach/kidney/heart problems, no allergies, no other medications"),
        ("Which painkiller is safe? I'm pregnant and on blood thinners.",
         "I'm 29, second trimester, I take warfarin, no allergies, no other conditions"),
    ]

    for query, profile in scenarios:
        print(f"\n{'='*70}\nQUERY: {query}")
        r = start_query(query)
        i = 0
        while r["awaiting_input"]:
            print(f"  Q{i+1}: {r['question']}")
            print(f"  A{i+1}: {profile}")
            r = resume_query(r["thread_id"], profile)
            i += 1
        print(f"  -> asked {i} question(s)")
        print(f"  ANSWER: {r['response'].answer[:250]}")
        print(f"  CONFIDENCE: {r['response'].confidence_level}")
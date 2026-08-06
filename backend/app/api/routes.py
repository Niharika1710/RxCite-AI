"""
API routes: exposes the MedIntel pipeline over HTTP.

A turn either returns a final answer, or pauses and returns a follow-up
question plus the thread_id needed to resume.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.graph.orchestrator import start_query, resume_query
from app.models.schemas import ResponseOutput

router = APIRouter()


class QueryRequest(BaseModel):
    query: Optional[str] = None
    thread_id: Optional[str] = None
    reply: Optional[str] = None


class QueryResponse(BaseModel):
    thread_id: str
    awaiting_input: bool
    question: Optional[str] = None
    response: Optional[ResponseOutput] = None


@router.post("/query", response_model=QueryResponse)
def submit_query(request: QueryRequest):
    """Start a new query, or resume a paused one by sending thread_id + reply."""
    if request.thread_id and request.reply is not None:
        return resume_query(request.thread_id, request.reply)
    if not request.query:
        raise HTTPException(400, "Provide either 'query', or 'thread_id' + 'reply'.")
    return start_query(request.query)
"""
API routes: exposes the MedIntel pipeline over HTTP.

A turn either returns a final answer, or pauses and returns a follow-up
question plus the thread_id needed to resume.

Text path:  POST /query          {query}  OR  {thread_id, reply}
Image path: POST /query-image    multipart: image (+ optional question)
            -> if a drug is read and a question is present: runs pipeline
            -> if a drug is read but NO question: asks what they want to know
            -> if no drug is read: clean refusal
The image follow-up (case 2) resumes through the SAME /query endpoint,
because once we have the drug + the user's reply we just build a normal query.
"""
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from app.graph.orchestrator import start_query, resume_query
from app.agents.vision_agent import extract_drug_from_image
from app.models.schemas import ResponseOutput

router = APIRouter()

# Pending image threads waiting on "what do you want to know?" (case 2).
# Maps a thread_id -> the drug name we read from the image.
# In-memory is fine for a portfolio demo; swap for Redis/DB if you ever scale.
_pending_image_drug: dict[str, str] = {}

# MIME types we accept for uploads
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}


class QueryRequest(BaseModel):
    query: Optional[str] = None
    thread_id: Optional[str] = None
    reply: Optional[str] = None


class QueryResponse(BaseModel):
    thread_id: str
    awaiting_input: bool
    question: Optional[str] = None
    response: Optional[ResponseOutput] = None


def _bind_question(drug: str, question: Optional[str]) -> str:
    """Combine a drug name with an optional user question into one query."""
    q = (question or "").strip()
    if not q:
        return f"Tell me about {drug}: key safety facts, contraindications, and common side effects."
    # Prepend the drug so the router/retrieval agents resolve "this drug".
    return f"Regarding {drug}: {q}"


@router.post("/query", response_model=QueryResponse)
def submit_query(request: QueryRequest):
    """Start a new query, or resume a paused one by sending thread_id + reply."""
    # Case 2 resume: this thread is waiting on "what do you want to know?"
    if request.thread_id and request.thread_id in _pending_image_drug and request.reply is not None:
        drug = _pending_image_drug.pop(request.thread_id)
        query = _bind_question(drug, request.reply)
        # Fresh thread for the actual pipeline run (triage may interrupt again).
        return start_query(query)

    # Normal triage resume (drug already in a running graph thread).
    if request.thread_id and request.reply is not None:
        return resume_query(request.thread_id, request.reply)

    if not request.query:
        raise HTTPException(400, "Provide either 'query', or 'thread_id' + 'reply'.")
    return start_query(request.query)


@router.post("/query-image", response_model=QueryResponse)
async def submit_image_query(
    image: UploadFile = File(...),
    question: Optional[str] = Form(None),
):
    """
    Read a drug name off a package photo, then run it through the pipeline.
    Optional typed question rides along; if absent we ask what they want to know.
    """
    if image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            400, f"Unsupported image type '{image.content_type}'. Use JPEG, PNG, WEBP, or HEIC."
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(400, "Empty image upload.")

    vision = extract_drug_from_image(image_bytes, media_type=image.content_type)

    # Case 3: nothing readable / no drug -> clean refusal, no fabrication.
    if not vision.readable or not vision.drug_name:
        note = vision.note or "No drug name could be read from the image."
        return QueryResponse(
            thread_id=str(uuid.uuid4()),
            awaiting_input=False,
            question=None,
            response=ResponseOutput(
                query="(image upload)",
                answer=(
                    f"I couldn't identify a drug from that image. {note} "
                    "Please upload a clearer photo of the package where the drug name is visible, "
                    "or type the drug name directly."
                ),
                confidence_level="Low",
                citations=[],
                is_safe=True,
            ),
        )

    drug = vision.drug_name

    # Case 1: question supplied -> run the full pipeline now.
    if question and question.strip():
        return start_query(_bind_question(drug, question))

    # Case 2: no question -> ask what they want to know about this drug.
    thread_id = str(uuid.uuid4())
    _pending_image_drug[thread_id] = drug
    return QueryResponse(
        thread_id=thread_id,
        awaiting_input=True,
        question=(
            f"I read \"{drug}\" from the package. "
            f"What would you like to know about {drug}? "
            "For example: side effects, pregnancy safety, contraindications, or dosing."
        ),
        response=None,
    )
"""
Typed contracts shared between agents. Every agent reads/writes these
Pydantic models instead of loose dicts, so data passed through the
LangGraph pipeline is validated and self-documenting.
"""
from pydantic import BaseModel, field_validator
from typing import Literal, Optional


class RouterOutput(BaseModel):
    """Output of the Router Agent."""
    original_query: str
    is_in_scope: bool                     # is this a pharmaceutical question at all?
    identified_drug: Optional[str] = None  # matched to our known drug set, if any
    reasoning: str                         # short explanation of the routing decision


class EvidenceChunk(BaseModel):
    """A single retrieved piece of evidence with full citation info."""
    text: str
    drug: str
    section: str
    source: str
    relevance_score: float   # lower = more relevant (this is cosine distance)


class RetrievalOutput(BaseModel):
    """Output of the Retrieval Agent."""
    query: str
    drug: Optional[str] = None
    chunks: list[EvidenceChunk]
    chunk_count: int

class CitationVerdict(BaseModel):
    """Verdict on whether one evidence chunk supports the query."""
    chunk_text: str
    drug: str
    section: str
    source: str
    verdict: Literal["supports", "contradicts", "irrelevant"]
    justification: str


class CitationValidationOutput(BaseModel):
    """Output of the Citation Validation Agent."""
    query: str
    verdicts: list[CitationVerdict]
    supporting_count: int
    contradicting_count: int
    irrelevant_count: int

class ConfidenceOutput(BaseModel):
    """Output of the Confidence Agent."""
    query: str
    confidence_level: Literal["High", "Medium", "Low"]
    confidence_score: float  # 0.0 to 1.0, underlying numeric score
    reasoning: str
    retrieval_quality_score: float
    agreement_score: float
    coverage_score: float

class SafetyOutput(BaseModel):
    """Output of the Safety & Refusal Agent."""
    query: str
    should_refuse: bool
    refusal_reason: Optional[str] = None
    safety_flags: list[str] = []  # e.g. ["low_confidence", "source_contradiction"]
    recommendation: Optional[str] = None  # e.g. "Consult a healthcare professional."

class Citation(BaseModel):
    """A single citation linking a claim to its source."""
    drug: str
    section: str
    source: str
    url: Optional[str] = None


class ResponseOutput(BaseModel):
    """Final structured output shown to the user."""
    query: str
    answer: str
    confidence_level: str
    citations: list[Citation]
    explanation: str          # why this answer / why this confidence
    is_refusal: bool
    evidence_answers_question: bool = True
    recommendation: Optional[str] = None

class AgentState(BaseModel):
    query: str
    router_output: Optional[RouterOutput] = None
    retrieval_output: Optional[RetrievalOutput] = None
    citation_output: Optional[CitationValidationOutput] = None
    confidence_output: Optional[ConfidenceOutput] = None
    safety_output: Optional[SafetyOutput] = None
    response_output: Optional[ResponseOutput] = None

class IntakeSlots(BaseModel):
    """Clinical context gathered from the user before we answer."""
    age: Optional[str] = None
    sex: Optional[str] = None
    allergies: Optional[str] = None
    conditions: Optional[str] = None
    current_medications: Optional[str] = None
    pregnancy_status: Optional[str] = None

    @field_validator("*", mode="before")
    @classmethod
    def coerce_to_string(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            return ", ".join(str(x) for x in v) if v else None
        if isinstance(v, dict):
            return ", ".join(f"{k}: {val}" for k, val in v.items()) or None
        if isinstance(v, (int, float, bool)):
            return str(v)
        return v

class TriageOutput(BaseModel):
    """Output of the Triage Agent."""
    slots: IntakeSlots
    missing_slots: list[str]
    is_complete: bool
    follow_up_question: Optional[str] = None
    reasoning: str
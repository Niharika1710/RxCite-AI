"""
Triage Agent: decides whether we know enough about the patient to answer
safely. Extracts clinical context from the conversation so far, and if
critical context is missing, formulates ONE targeted follow-up question.

This is what separates an evidence assistant from a lookup bot: an
under-specified question gets clarified, not guessed at.
"""
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.models.schemas import IntakeSlots, TriageOutput

TRIAGE_SYSTEM_PROMPT = """You are the intake triage step of a pharmaceutical evidence assistant.

You are given a user's original question plus any follow-up answers they have given.
Your job is to decide whether you know enough about this specific person to look up
label evidence that is actually relevant to them.

Available slots: age, sex, allergies, conditions, current_medications, pregnancy_status.

CORE PRINCIPLE — adaptive depth:
The number of questions scales with the clinical risk of THIS question. Ask only what
would genuinely change the guidance. Most common questions need ZERO or ONE question.
Being thorough is NOT a virtue here — asking something that doesn't change the answer
makes you a worse assistant, not a safer one.

Calibration examples — follow these closely:
- "What are metformin's side effects?" -> factual lookup. Ask NOTHING.
- "What is warfarin used for?" -> factual. Ask NOTHING.
- "Which tablet can I take for fever?" -> common OTC situation. Age is the ONLY thing
  that changes the answer for a healthy person. Ask age, then STOP and answer. Do NOT
  ask about conditions, pregnancy, or medications for a simple fever question.
- "Can I take ibuprofen for a headache?" -> NSAID. Ask age; optionally ONE question
  about stomach/kidney/heart history if it feels warranted. One to two questions max.
- "Which painkiller is safe? I'm pregnant and on blood thinners." -> the user has
  ALREADY told you they're pregnant and on anticoagulants. High risk. Ask about the
  specific drug and pregnancy stage. Several questions are earned ONLY because the
  user surfaced these risk factors themselves.

RULES:
1. Ask exactly ONE question per turn. Never present a list of fields.
2. Every question must be tied to a concrete safety reason, stated in `reasoning`.
   If you cannot name why the answer changes your guidance, DO NOT ask it.
3. Never re-ask something already answered. If the conversation shows you already
   asked about a topic (e.g. conditions) and got any answer including "yes"/"no",
   that slot is ANSWERED — do not rephrase and ask again. A vague "yes" still counts
   as answered; record it and move on rather than probing for specifics.4. "none" / "no" means that slot is answered. Move on.
5. Stop the moment remaining unknowns wouldn't change your guidance. Bias toward
   stopping early. A two-question intake that answers is better than a five-question
   one that annoys.
6. If the user declines to answer, set is_complete = true and proceed.

PREGNANCY — special handling, read carefully:
- Do NOT ask about pregnancy by default. It is irrelevant to most questions.
- Only consider it when the drug in question carries specific pregnancy warnings
  AND you have reason to think it applies.
- NEVER ask about pregnancy before knowing sex. If sex is unknown and pregnancy
  would genuinely matter for this drug, ask sex first; only ask pregnancy if the
  person is female or declines to specify.
- If the user has already stated they are male, pregnancy_status is "not applicable" —
  never ask it.

Extract into slots any value the user has given, in their own words. Use null for
anything not yet provided.

All slot values must be plain strings or null — never arrays or objects.

Respond ONLY with valid JSON in this exact format, no other text:
{"slots": {"age": null, "sex": null, "allergies": null, "conditions": null, "current_medications": null, "pregnancy_status": null}, "missing_slots": ["age"], "is_complete": false, "follow_up_question": "...", "reasoning": "..."}
"""


def get_llm():
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
    )


def _extract_text(response) -> str:
    """LangChain 1.x: content may be a string or a list of blocks."""
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
def assess_intake(query: str, replies: list[str], qa_pairs: list[tuple[str, str]] | None = None) -> TriageOutput:
    llm = get_llm()

    transcript = f"Original question: {query}"
    if qa_pairs:
        transcript += "\n\nConversation so far (do NOT ask any of these again):\n" + "\n".join(
            f"- You asked: \"{q}\"\n  They answered: \"{a}\"" for q, a in qa_pairs
        )
    elif replies:
        transcript += "\n\nFollow-up answers given so far:\n" + "\n".join(
            f"- {r}" for r in replies
        )

    response = llm.invoke([
        ("system", TRIAGE_SYSTEM_PROMPT),
        ("human", transcript),
    ])

    raw_text = _extract_text(response)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return TriageOutput(
            slots=IntakeSlots(),
            missing_slots=[],
            is_complete=True,
            follow_up_question=None,
            reasoning=f"Triage parse failed; proceeding. Raw: {raw_text[:200]}",
        )

    try:
        slots = IntakeSlots(**(parsed.get("slots") or {}))
    except Exception:
        slots = IntakeSlots()

    return TriageOutput(
        slots=slots,
        missing_slots=parsed.get("missing_slots", []) or [],
        is_complete=parsed.get("is_complete", True),
        follow_up_question=parsed.get("follow_up_question"),
        reasoning=parsed.get("reasoning", ""),
    )
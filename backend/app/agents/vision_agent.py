# app/agents/vision_agent.py
"""
Vision agent: reads a printed drug name off a package/blister/box photo (OCR-style).
Extracts the GENERIC drug name and hands it to the existing text pipeline.

Explicitly does NOT identify loose pills by shape/color/appearance (unsafe, out of scope).
"""
import json
from typing import Optional
from pydantic import BaseModel

import google.generativeai as genai
from app.config import settings

# NOTE: match this to however your other agents init Gemini.
# If settings uses a different field name, change `settings.gemini_api_key`.
genai.configure(api_key=settings.google_api_key)


class VisionOutput(BaseModel):
    drug_name: Optional[str] = None   # generic name, lowercase, or None
    raw_text: str = ""                # text read off the package
    readable: bool = True             # False if image is unusable
    note: str = ""                    # one-line human-readable status


_VISION_PROMPT = """You are reading a photograph of a pharmaceutical package, blister pack, or box.

Your ONLY job is to read PRINTED TEXT and identify the GENERIC drug name.

Rules:
- Return the GENERIC (International Nonproprietary) name, NOT the brand name.
  Example: package says "Utsolone-8 (Methylprednisolone)" -> generic is "methylprednisolone".
  Example: package says "Brufen" -> generic is "ibuprofen".
- If only a brand name is visible and you are confident of its generic, return the generic.
- If you cannot confidently determine a generic drug name, set drug_name to null.
- NEVER guess a drug from pill shape, color, or physical appearance. Only read printed text.
- If the image is blurry, empty, not a medicine, or has no readable drug name,
  set readable=false and drug_name=null.

Return ONLY valid JSON, no markdown, no prose:
{"drug_name": "<generic lowercase or null>", "raw_text": "<key text you read>", "readable": <true|false>, "note": "<one short sentence>"}"""


def extract_drug_from_image(image_bytes: bytes, media_type: str = "image/jpeg") -> VisionOutput:
    """Read a package photo and return the generic drug name (or None)."""
    model = genai.GenerativeModel(settings.llm_model)
    image_part = {"mime_type": media_type, "data": image_bytes}

    try:
        resp = model.generate_content([_VISION_PROMPT, image_part])
        text = (resp.text or "").strip()
    except Exception as e:
        return VisionOutput(readable=False, note=f"Vision call failed: {e}")

    # Strip accidental ```json fences if the model adds them
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[-1]
        text = text.replace("json", "", 1).strip()

    try:
        data = json.loads(text)
    except Exception:
        return VisionOutput(readable=False, raw_text=text, note="Could not parse vision output.")

    drug = data.get("drug_name")
    if isinstance(drug, str):
        drug = drug.strip().lower() or None
    else:
        drug = None

    return VisionOutput(
        drug_name=drug,
        raw_text=str(data.get("raw_text", "")),
        readable=bool(data.get("readable", True)),
        note=str(data.get("note", "")),
    )
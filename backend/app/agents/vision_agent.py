"""
Vision agent: reads a printed drug name off a package/blister/box photo.

Extracts the GENERIC drug name and hands it to the existing text pipeline.

Explicitly does NOT identify loose pills by shape/color/appearance.
"""

import json
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings


class VisionOutput(BaseModel):
    drug_name: Optional[str] = None
    raw_text: str = ""
    readable: bool = True
    note: str = ""


_VISION_PROMPT = """
You are reading a photograph of a pharmaceutical package,
blister pack, or box.

Your ONLY job is to read PRINTED TEXT and identify the GENERIC drug name.

Rules:

- Return the GENERIC (International Nonproprietary) name,
  NOT the brand name.

Example:
package says "Utsolone-8 (Methylprednisolone)"
-> generic is "methylprednisolone".

Example:
package says "Brufen"
-> generic is "ibuprofen".

- If only a brand name is visible and you are confident of its generic,
  return the generic.

- If you cannot confidently determine a generic drug name,
  set drug_name to null.

- NEVER guess a drug from pill shape, color, or physical appearance.
  Only read printed text.

- If the image is blurry, empty, not a medicine,
  or has no readable drug name,
  set readable=false and drug_name=null.

Return ONLY valid JSON, no markdown, no prose:

{
  "drug_name": "<generic lowercase or null>",
  "raw_text": "<key text you read>",
  "readable": true,
  "note": "<one short sentence>"
}
"""


def extract_drug_from_image(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
) -> VisionOutput:
    """
    Read a package photo and return the generic drug name.
    """

    try:
        api_key = settings.google_api_key

        if not api_key:
            return VisionOutput(
                readable=False,
                note="Google API key is not configured.",
            )

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=settings.llm_model,
            contents=[
                types.Part.from_text(text=_VISION_PROMPT),
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=media_type,
                ),
            ],
        )

        text = (response.text or "").strip()

    except Exception as e:
        return VisionOutput(
            readable=False,
            note=f"Vision call failed: {e}",
        )

    # Remove accidental markdown fences
    if text.startswith("```"):
        text = text.strip("`")

        if "\n" in text:
            text = text.split("\n", 1)[-1]

        text = text.replace("json", "", 1).strip()

    try:
        data = json.loads(text)

    except Exception:
        return VisionOutput(
            readable=False,
            raw_text=text,
            note="Could not parse vision output.",
        )

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

# Photo import: LLM vision reads a cookbook page/recipe photo -> structured draft.
# Never auto-saves; the parsed result is shown for review in the UI.
import base64
import json
from typing import Any

from app.services.llm_client import chat

PROMPT = (
    "You are transcribing a photo of a recipe (cookbook page, handwritten card, or screenshot). "
    "Return ONLY a JSON object with keys: title (string), description (string), servings (int), "
    "prep_minutes (int|null), cook_minutes (int|null), "
    "ingredients (list of {name, quantity (number|null), unit (string|null)}), "
    "instructions (ordered list of step strings). Transcribe faithfully — do not invent content."
)


def import_from_photo(image_bytes: bytes) -> dict[str, Any]:
    b64 = base64.b64encode(image_bytes).decode()
    text = chat(PROMPT, json_mode=True, image_b64=b64)
    try:
        draft = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI returned invalid JSON: {text[:200]}") from exc
    draft.setdefault("source_name", "Photo")
    return draft

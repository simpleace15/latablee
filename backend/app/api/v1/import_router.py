# Import: URL scrape (schema.org/JSON-LD) + LLM-vision photo (fixture-driven tests)
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app.api.v1.recipes import _recipe_out, _to_recipe
from app.core.security import require_household
from app.db.engine import get_session
from app.models import User
from app.services.recipe_url_import import import_from_url
from app.services.recipe_vision_import import import_from_photo

router = APIRouter()


class UrlIn(BaseModel):
    url: str


@router.post("/url", status_code=201)
def import_url(
    payload: UrlIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Scrape a recipe URL. Parsed result returned for review — NOT auto-saved."""
    try:
        parsed = import_from_url(payload.url)
    except Exception as exc:
        raise HTTPException(422, f"Could not parse recipe from URL: {exc}") from exc
    return {"parsed": parsed, "saved": False, "note": "Review and save via POST /recipes"}


@router.post("/photo", status_code=200)
async def import_photo(
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
    file: UploadFile,
) -> dict:
    """LLM vision reads a cookbook page/photo -> structured recipe for review (never auto-save)."""
    if not get_llm_status()["configured"]:
        raise HTTPException(409, "No AI endpoint configured — set it in Settings")
    data = await file.read()
    try:
        parsed = import_from_photo(data)
    except Exception as exc:
        raise HTTPException(502, f"AI endpoint failed: {exc}") from exc
    return {"parsed": parsed, "saved": False, "note": "Review and save via POST /recipes"}


def get_llm_status() -> dict:
    from app.services.llm_client import llm_configured
    return {"configured": llm_configured()}


# re-export for router docs
_ = _recipe_out, _to_recipe

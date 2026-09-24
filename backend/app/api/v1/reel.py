# Reel import endpoint: paste a TikTok/IG/YouTube URL -> recipe draft for review.
# Long-running (download + possible whisper) — bounded by LLM timeout + extraction budget.
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.security import require_household
from app.db.engine import get_session
from app.models import User
from app.services.recipe_reel_import import extract_url

router = APIRouter(prefix="/reel", tags=["reel"])

REEL_TIMEOUT_SECONDS = 600  # generous: reel download + CPU whisper + local LLM can be slow


class ReelIn(BaseModel):
    url: str  # accepts a bare URL or pasted share text containing one


@router.post("", status_code=200)
def import_reel(
    payload: ReelIn,
    user: Annotated[User, Depends(require_household)],  # noqa: ARG001 (auth gate)
    session: Annotated[Session, Depends(get_session)],  # noqa: ARG001
) -> dict:
    """Extract a recipe from a social video (TikTok/IG/YouTube/…). Never auto-saves —
    the parsed draft is returned for review, save via POST /recipes."""
    url = extract_url(payload.url or "")
    if not url:
        raise HTTPException(422, "No supported video URL found (TikTok, Instagram, YouTube, …)")
    try:
        from app.services.recipe_reel_import import import_from_reel  # heavy deps, import lazily

        draft = import_from_reel(url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ImportError:
        raise HTTPException(
            503, "Reel extraction deps missing — rebuild the image (yt-dlp/whisper/av)"
        ) from None
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        # yt-dlp errors often carry the reason (login wall, region block, dead link)
        raise HTTPException(502, f"Extraction failed: {detail}") from exc
    return {"parsed": draft, "saved": False, "note": "Review and save via POST /recipes"}


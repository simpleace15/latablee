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


class UrlsIn(BaseModel):
    urls: str  # free text — links pasted from anywhere; we regex-extract them

    @property
    def url_list(self) -> list[str]:
        import re
        # http(s) only; dedupe preserving order; cap 20 per batch (server time + politeness)
        found = re.findall(r'''https?://[^\s<>"')\]]+''', self.urls)
        seen: dict[str, None] = {}
        for u in found:
            seen.setdefault(u.rstrip(".,;:!?"), None)
        return list(seen)[:20]


@router.post("/urls", status_code=200)
def import_urls(
    payload: UrlsIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Scrape many recipe URLs in one call — per-URL results; one failure
    doesn't kill the batch. Sequential on purpose: polite to origin sites.
    Parsed results are drafts for review — NOT auto-saved."""
    urls = payload.url_list
    if not urls:
        raise HTTPException(422, "No http(s) URLs found in that text")
    results = []
    for u in urls:
        try:
            results.append({"url": u, "ok": True, "parsed": import_from_url(u)})
        except Exception as exc:
            results.append({"url": u, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]})
    ok_n = sum(1 for r in results if r["ok"])
    return {"results": results, "total": len(results), "ok_count": ok_n,
            "note": "Review and save via POST /recipes"}


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

# Reel import endpoint: paste a TikTok/IG/YouTube URL -> recipe draft for review.
# Safari aborts idle requests at ~60-120s but the pipeline takes 100-220s, so the POST
# returns a job_id immediately and the pipeline runs in a background thread; the client
# polls GET /llm/reel/{job_id} for per-stage progress. Finished drafts are cached in
# SQLite by normalized URL (TTL 1 day) — a re-submit returns instantly.
import threading
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session

from app.core.security import require_household
from app.db.engine import get_session
from app.models import User
from app.services.recipe_reel_import import extract_url
from app.services.reel_jobs import (
    cache_get,
    create_job,
    get_job,
    latest_job,
    normalize_url,
    run_job,
)

router = APIRouter(prefix="/reel", tags=["reel"])


class ReelIn(BaseModel):
    url: str  # accepts a bare URL or pasted share text containing one


@router.post("", status_code=202)
def import_reel(
    payload: ReelIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],  # noqa: ARG001 (auth gate)
    response: Response,
) -> dict:
    """Extract a recipe from a social video (TikTok/IG/YouTube/…). Returns a job_id —
    poll GET /llm/reel/{job_id} for stage progress and the finished draft (never
    auto-saves; save via POST /recipes after review). Cached videos return 200 + draft."""
    url = extract_url(payload.url or "")
    if not url:
        raise HTTPException(422, "No supported video URL found (TikTok, Instagram, YouTube, …)")

    # idempotent retry: a fresh cached draft returns instantly, no re-download
    key = normalize_url(url)
    cached = cache_get(key)
    if cached is not None:
        response.status_code = 200
        return {"cached": True, "parsed": cached, "saved": False,
                "note": "Cached draft for this video — review and save via POST /recipes"}

    job_id = create_job(user_id=user.id, url=url)
    threading.Thread(target=run_job, args=(job_id, url, key), daemon=True).start()
    return {"job_id": job_id, "cached": False, "poll_after_seconds": 2}


@router.get("/latest")
def reel_latest(
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],  # noqa: ARG001
) -> dict:
    """Most recent job for this user — lets a page refresh re-attach to a running job."""
    job = latest_job(user.id)
    if job is None:
        raise HTTPException(404, "No reel jobs yet")
    return job


@router.get("/{job_id}")
def reel_status(
    job_id: str,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],  # noqa: ARG001
) -> dict:
    """Job progress: {stage, detail, elapsed_seconds, done, result|error}."""
    job = get_job(job_id, user.id)
    if job is None:
        raise HTTPException(404, "Job not found (may have been trimmed, or the app restarted)")
    return {
        "job_id": job["job_id"], "stage": job["stage"], "detail": job["detail"],
        "elapsed_seconds": job["elapsed_seconds"], "done": job["done"],
        "error": job["error"], "result": job["result"],
    }

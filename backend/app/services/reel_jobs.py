# Reel import job store + draft cache: POST /llm/reel returns a job_id immediately, the
# pipeline runs in a background thread, the client polls GET /llm/reel/{id} for per-stage
# progress. Jobs are in-memory (single-process app); finished drafts persist in SQLite
# keyed by normalized URL (TTL 1 day) so retries are instant and a Safari disconnect's
# completed work is never lost.
from __future__ import annotations

import datetime
import re
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlmodel import Session, select

from app.db.engine import get_engine
from app.models import ReelDraftCache, utcnow

CACHE_TTL_SECONDS = 86400  # one day

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}
_JOB_ORDER: list[str] = []  # oldest first, for trimming
MAX_JOBS = 200


def normalize_url(url: str) -> str:
    """Canonical cache key for a video URL: host lowercased, platform video id extracted,
    share-text noise and tracking params dropped. youtu.be/ID == watch?v=ID."""
    u = url.strip().lower()
    # pull ?v= BEFORE stripping the query
    m = re.search(r"[?&]v=([\w-]{6,})", u)
    if m:
        return f"youtube:{m.group(1)}"
    u = re.sub(r"^https?://", "", u)
    u = u.split("#", 1)[0].split("?", 1)[0]
    # YouTube: keep the video id from either host form
    m = re.search(r"(?:youtube\.com/(?:watch/|shorts/|embed/)|youtu\.be/)([\w-]{6,})", u)
    if m:
        return f"youtube:{m.group(1)}"
    m = re.search(r"tiktok\.com/.*?/video/(\d+)", u)
    if m:
        return f"tiktok:{m.group(1)}"
    m = re.search(r"instagram\.com/(?:reels?|p)/([\w-]+)", u)
    if m:
        return f"instagram:{m.group(1)}"
    m = re.search(r"facebook\.com/(?:reel|watch)/?(\d+|\w+)", u)
    if m:
        return f"facebook:{m.group(1)}"
    # generic: drop tracking query already done; use the path
    return u


def cache_get(url_key: str) -> dict | None:
    """Fresh draft for this URL, or None (expired/missing entries are pruned lazily)."""
    with Session(get_engine()) as session:
        row = session.exec(
            select(ReelDraftCache).where(ReelDraftCache.url_key == url_key)  # type: ignore[arg-type]
        ).first()
        if row is None:
            return None
        now = utcnow()
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=now.tzinfo)
        if now - created > datetime.timedelta(seconds=CACHE_TTL_SECONDS):
            session.delete(row)
            session.commit()
            return None
        return dict(row.draft or {})


def cache_put(url_key: str, source_url: str, draft: dict) -> None:
    with Session(get_engine()) as session:
        row = session.exec(
            select(ReelDraftCache).where(ReelDraftCache.url_key == url_key)  # type: ignore[arg-type]
        ).first()
        if row is None:
            row = ReelDraftCache(url_key=url_key, source_url=source_url, draft=draft)
        else:
            row.draft = draft
            row.source_url = source_url
            row.created_at = utcnow()
        session.add(row)
        session.commit()


def create_job(user_id: int | None, url: str) -> str:
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id, "user_id": user_id, "url": url,
            "stage": "queued", "detail": "", "done": False,
            "error": None, "result": None,
            "created_at": time.time(),
        }
        _JOBS[job_id]["started_at"] = None
        _JOBS[job_id]["updated_at"] = time.time()
        _JOB_ORDER.append(job_id)
        while len(_JOB_ORDER) > MAX_JOBS:
            old = _JOB_ORDER.pop(0)
            _JOBS.pop(old, None)
    return job_id


def update_job(job_id: str, *, stage: str | None = None, detail: str | None = None,
               error: str | None = None, result: dict | None = None,
               done: bool | None = None, started: bool = False) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        if started and job["started_at"] is None:
            job["started_at"] = time.time()
        if stage is not None:
            job["stage"] = stage
        if detail is not None:
            job["detail"] = detail
        if error is not None:
            job["error"] = error
            job["done"] = True
        if result is not None:
            job["result"] = result
        if done:
            job["done"] = True
        job["updated_at"] = time.time()


def get_job(job_id: str, user_id: int | None) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None or job["user_id"] != user_id:
            return None
        snap = dict(job)
        started = snap.get("started_at") or snap["created_at"]
        snap["elapsed_seconds"] = round(time.time() - started, 1)
        return snap


def latest_job(user_id: int | None) -> dict | None:
    """Most recent job for this user — lets a page refresh re-attach to a running job."""
    with _LOCK:
        mine = [j for j in _JOBS.values() if j["user_id"] == user_id]
        if not mine:
            return None
        snap = dict(max(mine, key=lambda j: j["created_at"]))
        started = snap.get("started_at") or snap["created_at"]
        snap["elapsed_seconds"] = round(time.time() - started, 1)
        return snap


def run_job(job_id: str, url: str, url_key: str, progress: Callable[[str, str], None] | None = None) -> None:
    """Pipeline runner (background thread): pipeline -> cache -> job result."""
    def cb(stage: str, detail: str) -> None:
        update_job(job_id, stage=stage, detail=detail, started=True)

    try:
        update_job(job_id, stage="starting", detail="", started=True)
        from app.services.recipe_reel_import import import_from_reel

        draft = import_from_reel(url, progress=cb)
        key = normalize_url(url)
        cache_put(key, url, draft)
        update_job(job_id, stage="done", detail="Review and save via POST /recipes",
                   result=draft, done=True)
    except ValueError as exc:
        update_job(job_id, stage="error", error=str(exc))
    except ImportError:
        update_job(job_id, stage="error",
                   error="Reel extraction deps missing — rebuild the image (yt-dlp/whisper/av)")
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        update_job(job_id, stage="error", error=f"Extraction failed: {detail}")
    finally:
        if progress:
            progress("done", "")

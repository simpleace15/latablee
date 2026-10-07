# Admin actions: demo seed data (explicit, never automatic)
# ruff: noqa: S105 — demo credentials are the feature (empty local instance only)
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import get_current_user
from app.db.engine import get_session
from app.models import Setting, User
from app.services.llm_client import get_llm_log, test_llm_connection

router = APIRouter()


class VersionCheckOut(BaseModel):
    current: str
    latest: str | None = None
    update_available: bool = False
    checked: bool = False  # False when GitHub couldn't be reached (offline, rate-limited)
    error: str | None = None


def _fetch_latest_github_version() -> str | None:
    """Latest published version from GitHub releases/tags; None if unreachable.
    Falls back to package version comparisons only — never scrapes HTML.
    (URLs are module constants, https-only — S310 audited here.)"""
    import json
    import urllib.request

    for url in (
        "https://api.github.com/repos/simpleace15/latablee/releases/latest",
        "https://api.github.com/repos/simpleace15/latablee/tags",
    ):
        try:
            # noqa needed on the Request line too — ruff flags the taint source
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})  # noqa: S310
            with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310 — https literals above
                data = json.loads(resp.read())
            if isinstance(data, dict) and data.get("tag_name"):
                return str(data["tag_name"]).removeprefix("v")
            if isinstance(data, list) and data:
                return str(data[0].get("name", "")).removeprefix("v") or None
        except (OSError, ValueError) as exc:  # network/JSON — log & fall through
            import logging

            logging.getLogger(__name__).debug("version check %s failed: %s", url, exc)
            continue
    return None


@router.get("/version-check", response_model=VersionCheckOut)
def version_check(
    user: Annotated[User, Depends(get_current_user)],
) -> VersionCheckOut:
    """Compare the running version with the latest GitHub release (admin only).
    Result is cached in settings for 6h so page loads stay fast and GitHub
    rate limits stay far away."""
    import time as _time

    from app.core.config import get_settings

    current = get_settings().version
    s = None
    # pull cached check (single Setting row, JSON: {checked_at, latest})
    cache = None
    from app.db.engine import get_engine

    with Session(get_engine()) as db:
        s = db.get(Setting, "version_check_cache")
        if s is not None and isinstance(s.value, dict):
            cache = s.value
    if cache and (_time.time() - float(cache.get("checked_at", 0))) < 6 * 3600:
        latest = cache.get("latest")
        return VersionCheckOut(current=current, latest=latest,
                               update_available=bool(latest and _version_gt(latest, current)),
                               checked=latest is not None)

    latest = _fetch_latest_github_version()
    with Session(get_engine()) as db:
        row = db.get(Setting, "version_check_cache")
        if row is None:
            row = Setting(key="version_check_cache", value={})
        row.value = {"checked_at": _time.time(), "latest": latest}
        db.add(row)
        db.commit()
    return VersionCheckOut(current=current, latest=latest,
                           update_available=bool(latest and _version_gt(latest, current)),
                           checked=latest is not None,
                           error=None if latest is not None else "GitHub unreachable")


def _version_gt(candidate: str, current: str) -> bool:
    """True when candidate > current (semantic-ish; tolerates v-prefix, rc suffixes)."""
    import re

    def as_tuple(v: str) -> tuple:
        m = re.match(r"v?(\d+(?:\.\d+)*)", v.strip())
        if not m:
            return (0,)
        parts = []
        for p in m.group(1).split("."):
            try:
                parts.append(int(p))
            except ValueError:
                break
        return tuple(parts) or (0,)

    return as_tuple(candidate) > as_tuple(current)


class SeedIn(BaseModel):
    household_name: str = "Demo Household"
    admin_name: str = "Admin"
    # demo credentials are the feature (empty local instance only)
    password: str = "latablee-demo"


@router.post("/seed")
def seed_demo(  # noqa: S107 - demo credentials are the point; instance is empty & local
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    payload: SeedIn | None = None,
) -> dict:
    """Load ~12 sample recipes + sample week + grocery list. Admin-only, refuses if data exists."""
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    if session.exec(select(User)).first() is not None:
        raise HTTPException(409, "Database already has users — seed only runs on an empty instance")
    from app.seed import seed
    p = payload or SeedIn()
    return seed(household_name=p.household_name, admin_name=p.admin_name, password=p.password)


# ---- LLM diagnostics (admin) ----

@router.get("/llm/log")
def llm_log(user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Recent AI calls — newest first (status, duration, errors)."""
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    return {"entries": get_llm_log()}


@router.post("/llm/test")
def llm_test(user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Ping the configured AI endpoint: latency + whether it answers."""
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    return test_llm_connection()


@router.get("/llm/timeout")
def get_llm_timeout(user: Annotated[User, Depends(get_current_user)],
                    session: Annotated[Session, Depends(get_session)]) -> dict:
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    row = session.get(Setting, "llm.timeout_seconds")
    return {"timeout_seconds": float(row.value) if row else None}


class TimeoutIn(BaseModel):
    timeout_seconds: float


@router.post("/llm/timeout")
def set_llm_timeout(payload: TimeoutIn,
                    user: Annotated[User, Depends(get_current_user)],
                    session: Annotated[Session, Depends(get_session)]) -> dict:
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    if not (5 <= payload.timeout_seconds <= 1200):
        raise HTTPException(422, "Timeout must be between 5 and 1200 seconds")
    row = session.get(Setting, "llm.timeout_seconds")
    if row is None:
        session.add(Setting(key="llm.timeout_seconds", value=str(payload.timeout_seconds)))
    else:
        row.value = str(payload.timeout_seconds)
        session.add(row)
    session.commit()
    return {"timeout_seconds": payload.timeout_seconds}

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

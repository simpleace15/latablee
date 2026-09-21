# Admin actions: demo seed data (explicit, never automatic)
# ruff: noqa: S105 — demo credentials are the feature (empty local instance only)
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import get_current_user
from app.db.engine import get_session
from app.models import User

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

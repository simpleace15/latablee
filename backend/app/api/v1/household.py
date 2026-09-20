# Household: onboarding wizard + profile that feeds AI suggestions
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import get_current_user, require_household
from app.db.engine import get_session
from app.models import Household, User, utcnow

router = APIRouter()


class HouseholdIn(BaseModel):
    name: str
    timezone: str = "UTC"
    dietary_preferences: dict[str, str] | None = None
    allergies: list[str] | None = None
    dislikes: list[str] | None = None
    favorites: list[str] | None = None
    things_to_remember: str = ""


@router.post("/onboard")
def onboard(
    payload: HouseholdIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """First-run wizard: admin names the household + sets preferences (feeds AI suggestions)."""
    if user.role != "admin":
        raise HTTPException(403, "Only the admin completes onboarding")
    if session.exec(select(Household)).first() is not None:
        raise HTTPException(409, "Household already exists")
    h = Household(
        name=payload.name,
        timezone=payload.timezone,
        dietary_preferences=payload.dietary_preferences or {},
        allergies=payload.allergies or [],
        dislikes=payload.dislikes or [],
        favorites=payload.favorites or [],
        things_to_remember=payload.things_to_remember,
        onboarded_at=utcnow(),
    )
    session.add(h)
    session.commit()
    session.refresh(h)
    user.household_id = h.id
    session.add(user)
    session.commit()
    return {"id": h.id, "name": h.name, "timezone": h.timezone}


@router.get("")
def get_household(
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    h = session.get(Household, user.household_id)
    return {"id": h.id, "name": h.name, "timezone": h.timezone,
            "dietary_preferences": h.dietary_preferences, "allergies": h.allergies,
            "dislikes": h.dislikes, "favorites": h.favorites,
            "things_to_remember": h.things_to_remember}


@router.patch("")
def update_household(
    payload: HouseholdIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Update household profile. Non-admins may edit everything except name/timezone."""
    h = session.get(Household, user.household_id) if user.household_id else None
    if h is None:
        raise HTTPException(409, "No household yet")
    if user.role == "admin":
        h.name = payload.name or h.name
        h.timezone = payload.timezone or h.timezone
    h.dietary_preferences = payload.dietary_preferences if payload.dietary_preferences is not None else h.dietary_preferences
    h.allergies = payload.allergies if payload.allergies is not None else h.allergies
    h.dislikes = payload.dislikes if payload.dislikes is not None else h.dislikes
    h.favorites = payload.favorites if payload.favorites is not None else h.favorites
    h.things_to_remember = payload.things_to_remember if payload.things_to_remember is not None else h.things_to_remember
    session.add(h)
    session.commit()
    session.refresh(h)
    return {"id": h.id, "name": h.name, "timezone": h.timezone}

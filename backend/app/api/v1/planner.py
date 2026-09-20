# Meal planner: weekly calendar, breakfast/lunch/dinner slots, multi-week
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import require_household
from app.db.engine import get_session
from app.models import MealPlanEntry, Recipe, User
from app.services.events import record_event

router = APIRouter()

SLOTS = {"breakfast", "lunch", "dinner", "other"}


class PlanIn(BaseModel):
    date: date  # household-local date
    slot: str = "dinner"
    recipe_id: int | None = None
    title_override: str | None = None
    notes: str = ""


def _entry_out(e: MealPlanEntry) -> dict:
    return {"id": e.id, "date": e.planned_date.isoformat(), "slot": e.slot,
            "recipe_id": e.recipe_id, "title_override": e.title_override,
            "notes": e.notes}


@router.get("")
def get_plan(
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
    start: date = Query(default_factory=date.today),
    days: int = 7,
) -> dict:
    if not 1 <= days <= 60:
        raise HTTPException(422, "days must be 1-60")
    end = start + timedelta(days=days)
    entries = session.exec(
        select(MealPlanEntry).where(
            MealPlanEntry.household_id == user.household_id,
            MealPlanEntry.planned_date >= start,
            MealPlanEntry.planned_date < end,
        )
    ).all()
    recipes = {r.id: r.title for r in session.exec(
        select(Recipe).where(Recipe.household_id == user.household_id)).all()}
    out = [_entry_out(e) | {"recipe_title": recipes.get(e.recipe_id)} for e in entries]
    out.sort(key=lambda e: (e["date"], e["slot"]))
    return {"start": start.isoformat(), "days": days, "entries": out}


@router.post("", status_code=201)
def add_entry(
    payload: PlanIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    if payload.slot not in SLOTS:
        raise HTTPException(422, f"slot must be one of {sorted(SLOTS)}")
    if payload.recipe_id is None and not payload.title_override:
        raise HTTPException(422, "Provide recipe_id or title_override")
    if payload.recipe_id is not None:
        recipe = session.get(Recipe, payload.recipe_id)
        if recipe is None or recipe.household_id != user.household_id:
            raise HTTPException(404, "Recipe not found")
    e = MealPlanEntry(
        household_id=user.household_id,
        recipe_id=payload.recipe_id,
        planned_date=payload.date,
        slot=payload.slot,
        notes=payload.notes,
        title_override=payload.title_override,
    )
    session.add(e)
    session.commit()
    session.refresh(e)
    record_event(session, "meal_plan_updated", {"entry_id": e.id, "date": payload.date.isoformat()})
    return _entry_out(e)


@router.delete("/{entry_id}", status_code=204)
def delete_entry(
    entry_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    e = session.get(MealPlanEntry, entry_id)
    if e is None or e.household_id != user.household_id:
        raise HTTPException(404, "Entry not found")
    session.delete(e)
    session.commit()
    record_event(session, "meal_plan_updated", {"removed": entry_id})

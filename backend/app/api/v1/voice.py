# POST /api/v1/voice/command — transcript in, structured actions out + TTS reply.
# HA-agnostic: any client (curl, HA repo 2, future apps). Reuses the app's LLM config.
# Includes fuzzy-name handling: satellites may transcribe "LaTablée" as "la table"/"latable".
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import require_household
from app.db.engine import get_session
from app.models import MealPlanEntry, Recipe, ShoppingList, ShoppingListItem, User
from app.services import voice_nlu
from app.services.events import record_event

router = APIRouter()


class VoiceCommandIn(BaseModel):
    transcript: str
    # optional transcription hint: satellites often mangle "LaTablée" (la table, latable, etc.)
    device_hint: str | None = None
    locale: str = "en"


class Action(BaseModel):
    type: str  # add_to_list | plan_meal | query_plan | unknown
    params: dict[str, Any] = {}


@router.post("/command")
def command(
    payload: VoiceCommandIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    transcript = voice_nlu.strip_wake_word(payload.transcript, payload.device_hint)
    if not transcript:
        return {"reply": "I didn't catch that.", "actions": []}
    household_id = user.household_id
    assert household_id is not None  # require_household guarantees
    if not voice_nlu.llm_available():
        # deterministic fast-path for common commands even without an LLM
        result = voice_nlu.rule_based_parse(transcript)
        if result is not None:
            actions, reply = _apply(session, user, result)
            return {"reply": reply, "actions": actions}
        raise HTTPException(409, "No AI endpoint configured — freeform voice needs it in Settings")
    result = voice_nlu.llm_parse(transcript, session, household_id)
    actions, reply = _apply(session, user, result)
    return {"reply": reply, "actions": actions}


def _apply(session: Session, user: User, result: dict) -> tuple[list[dict], str]:
    from app.services.dates import household_today as _household_today

    today = _household_today(session, user.household_id)
    actions: list[dict] = []
    kind = result.get("intent")
    if kind == "add_to_list":
        lst = _default_list(session, user)
        item = ShoppingListItem(
            list_id=lst.id,
            name=result["item"],
            quantity=result.get("quantity"),
            unit=result.get("unit"),
            manual=True,
        )
        session.add(item)
        session.commit()
        record_event(session, "shopping_list_updated", {"list_id": lst.id})
        actions.append({"type": "add_to_list", "params": {"list_id": lst.id, "item": item.name}})
        return actions, f"Added {item.name} to {lst.name}."
    if kind == "plan_meal":
        day = voice_nlu.resolve_date(result.get("date_phrase") or "today", session, user)
        entry = MealPlanEntry(
            household_id=user.household_id,
            planned_date=day,
            slot=result.get("slot", "dinner"),
            title_override=result.get("title"),
            recipe_id=_match_recipe(session, user, result.get("title") or ""),
        )
        session.add(entry)
        session.commit()
        record_event(session, "meal_plan_updated", {"entry_id": entry.id})
        actions.append({"type": "plan_meal",
                        "params": {"date": day.isoformat(), "slot": entry.slot,
                                   "title": result.get("title")}})
        return actions, f"Planned {result.get('title')} for {voice_nlu.human_date(day, today=today)}."
    if kind == "query_plan":
        day = voice_nlu.resolve_date(result.get("date_phrase") or "tonight", session, user)
        entries = session.exec(
            select(MealPlanEntry).where(
                MealPlanEntry.household_id == user.household_id,
                MealPlanEntry.planned_date == day,
            )
        ).all()
        titles = [e.title_override or _recipe_title(session, e.recipe_id) or "something" for e in entries]
        reply = f"{voice_nlu.human_date(day, today=today)}: {', '.join(titles)}." if titles else \
            f"Nothing planned for {voice_nlu.human_date(day, today=today)} yet."
        actions.append({"type": "query_plan", "params": {"date": day.isoformat(), "found": titles}})
        return actions, reply
    return [], result.get("reply") or "I'm not sure how to help with that."


def _default_list(session: Session, user: User) -> ShoppingList:
    lst = session.exec(select(ShoppingList).where(ShoppingList.household_id == user.household_id)).first()
    if lst is None:
        lst = ShoppingList(name="Groceries", household_id=user.household_id)
        session.add(lst)
        session.commit()
        session.refresh(lst)
    return lst


def _match_recipe(session: Session, user: User, title: str) -> int | None:
    if not title:
        return None
    t = title.lower()
    recipe = session.exec(select(Recipe).where(Recipe.household_id == user.household_id)).all()
    for r in recipe:
        if r.title.lower() == t:
            return r.id
    from rapidfuzz import process

    names = {r.id: r.title for r in recipe}
    match = process.extractOne(t, names, score_threshold=88) if names else None
    return match[2] if match else None


def _recipe_title(session: Session, recipe_id: int | None) -> str | None:
    if recipe_id is None:
        return None
    r = session.get(Recipe, recipe_id)
    return r.title if r else None

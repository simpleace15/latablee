# LLM module: any OpenAI-compatible endpoint (Ollama, llama.cpp, LocalAI, cloud)
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import get_current_user, require_household
from app.db.engine import get_session
from app.models import Household, MealPlanEntry, Recipe, User
from app.services import llm_client
from app.services.events import record_event
from app.services.unit_conversion import normalize_ingredient_units

router = APIRouter()


class LLMSettingsIn(BaseModel):
    base_url: str
    api_key: str = ""
    model: str = "gpt-4o-mini"
    vision_model: str = ""


@router.get("/status")
def status(user: Annotated[User, Depends(get_current_user)]) -> dict:
    return {"configured": llm_client.llm_configured()}


@router.get("/settings")
def get_settings_endpoint(admin: Annotated[User, Depends(get_current_user)]) -> dict:
    if admin.role != "admin":
        raise HTTPException(403, "Admin only")
    s = llm_client.get_llm_settings()
    return {"base_url": s["base_url"], "model": s["model"],
            "vision_model": s["vision_model"],
            "api_key_set": bool(s["api_key"])}


@router.put("/settings")
def put_settings(
    payload: LLMSettingsIn,
    admin: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Store LLM config in DB (Setting rows) — survives restarts, admin-editable in UI."""
    if admin.role != "admin":
        raise HTTPException(403, "Admin only")
    llm_client.save_llm_settings(payload.base_url.strip(), payload.api_key, payload.model,
                      payload.vision_model)
    return {"saved": True}


@router.post("/suggest-meals")
def suggest_meals(
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
    payload: dict | None = None,
) -> dict:
    """Meal suggestions from household profile + what's on hand/preferences."""
    if not llm_client.llm_configured():
        raise HTTPException(409, "No AI endpoint configured — set it in Settings")
    h = session.get(Household, user.household_id)
    recipes = list(session.exec(select(Recipe).where(Recipe.household_id == user.household_id)))
    prompt = _suggestion_prompt(h, recipes, payload or {})
    try:
        text = llm_client.chat(prompt, json_mode=True)
    except Exception as exc:
        raise HTTPException(502, f"AI endpoint failed: {exc}") from exc
    return {"suggestions": text}


@router.post("/generate-recipe")
def generate_recipe(
    payload: dict,
    user: Annotated[User, Depends(require_household)],
) -> dict:
    """Generate a recipe draft from a prompt or ingredient list (returned for review)."""
    if not llm_client.llm_configured():
        raise HTTPException(409, "No AI endpoint configured — set it in Settings")
    prompt = ("You are a recipe writer. Create a complete recipe as JSON with keys "
              "title, description, servings, prep_minutes, cook_minutes, "
              "ingredients (list of {name, quantity, unit}), instructions (ordered list). "
              f"Request: {payload.get('prompt', '')} "
              f"Ingredients on hand: {payload.get('ingredients', [])}")
    try:
        text = llm_client.chat(prompt, json_mode=True)
    except Exception as exc:
        raise HTTPException(502, f"AI endpoint failed: {exc}") from exc
    import json as _json

    try:
        recipe = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise HTTPException(502, "AI returned invalid JSON") from exc
    recipe["ingredients"] = normalize_ingredient_units(recipe.get("ingredients", []))
    return {"parsed": recipe, "saved": False, "note": "Review and save via POST /recipes"}


@router.post("/auto-tag/{recipe_id}")
def auto_tag(
    recipe_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    from app.api.v1.recipes import get_recipe_or_404

    recipe = get_recipe_or_404(recipe_id, session, user)
    if not llm_client.llm_configured():
        raise HTTPException(409, "No AI endpoint configured — set it in Settings")
    prompt = (f"Suggest 3-6 short tags (lowercase, comma-separated, no explanations) for: "
              f"{recipe.title}. {recipe.description}")
    try:
        text = llm_client.chat(prompt)
    except Exception as exc:
        raise HTTPException(502, f"AI endpoint failed: {exc}") from exc
    tags = [t.strip().lower() for t in text.split(",") if t.strip()][:6]
    recipe.tags = sorted(set((recipe.tags or []) + tags))
    session.add(recipe)
    session.commit()
    return {"tags": recipe.tags}


class RefillProposal(BaseModel):
    date: str  # ISO
    slot: str = "dinner"
    from_book: bool
    recipe_id: int | None = None  # when from_book
    title: str = ""
    why: str = ""
    recipe: dict | None = None  # full recipe JSON when from_book=False


@router.post("/refill-week")
def refill_week(
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
    payload: dict | None = None,
) -> dict:
    """Auto-plan the empty slots of a week: pick from the household's recipe book where it
    fits, propose brand-new dishes (respecting allergies/dislikes, biasing favorites) for
    review — nothing new is saved without an explicit 'Save to book'.

    Payload: {start_date?: "YYYY-MM-DD" (defaults to today), days?: 7 (max 14),
              slots?: ["dinner"], replace?: false}. replace=true CLEARS the targeted
              slots in the window first (regenerate current/future weeks) and reports
              what it removed.
    """
    import json as _json
    from datetime import date, timedelta

    from app.services.dates import household_today

    if not llm_client.llm_configured():
        raise HTTPException(409, "No AI endpoint configured — set it in Settings")
    h = session.get(Household, user.household_id)
    today = household_today(session, user.household_id)
    p = payload or {}
    days = int(p.get("days", 7))
    slots = p.get("slots") or ["dinner"]
    start_raw = p.get("start_date")
    try:
        start = date.fromisoformat(start_raw) if start_raw else today
    except ValueError as exc:
        raise HTTPException(422, "start_date must be YYYY-MM-DD") from exc
    window = [start + timedelta(days=i) for i in range(max(1, min(days, 14)))]

    entries = session.exec(select(MealPlanEntry).where(
        MealPlanEntry.household_id == user.household_id,
        MealPlanEntry.planned_date >= start,
        MealPlanEntry.planned_date < window[-1] + timedelta(days=1),
    )).all()
    entries = [e for e in entries if e.slot in slots]
    taken = {(e.planned_date.isoformat(), e.slot) for e in entries}
    cleared: list[dict] = []
    replace = bool(p.get("replace"))
    if replace and entries:
        for e in entries:
            cleared.append({"date": e.planned_date.isoformat(), "slot": e.slot,
                            "title": e.title_override or None,
                            "recipe_id": e.recipe_id})
            session.delete(e)
        session.flush()
        taken = set()
    empty = [(d.isoformat(), slot) for d in window for slot in slots if (d.isoformat(), slot) not in taken]
    if not empty:
        session.commit()  # nothing to fill; commit any replace-clearing anyway
        return {"filled": [], "proposals": [], "cleared": cleared,
                "message": "Week is already full" if not replace else "Cleared, but nothing was planned"}

    recipes = list(session.exec(select(Recipe).where(Recipe.household_id == user.household_id)))
    prompt = _refill_prompt(h, recipes, empty)
    try:
        text = llm_client.chat(prompt, json_mode=True)
    except Exception as exc:
        raise HTTPException(502, f"AI endpoint failed: {exc}") from exc
    try:
        plan = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise HTTPException(502, "AI returned invalid JSON") from exc

    by_title = {r.title.casefold(): r for r in recipes}
    filled: list[dict] = []
    proposals: list[dict] = []
    for pick in plan.get("picks", [])[: len(empty)]:
        date_iso = pick.get("date", "")
        slot = pick.get("slot", "dinner")
        if (date_iso, slot) not in empty:
            continue
        title = (pick.get("title") or "").strip()
        match = by_title.get(title.casefold())
        if match is not None:
            entry = MealPlanEntry(household_id=user.household_id, recipe_id=match.id,
                                  planned_date=date.fromisoformat(date_iso), slot=slot)
            session.add(entry)
            filled.append({"date": date_iso, "slot": slot, "recipe_id": match.id,
                           "title": match.title, "why": pick.get("why", "")})
        else:
            proposals.append({"date": date_iso, "slot": slot, "from_book": False,
                              "title": title, "why": pick.get("why", ""),
                              "recipe": pick.get("recipe")})
    session.commit()
    record_event(session, "meal_plan_updated", {"refilled": len(filled), "cleared": len(cleared)})
    return {"filled": filled, "proposals": proposals, "cleared": cleared}


@router.post("/save-proposal")
def save_proposal(
    payload: dict,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Save an LLM-proposed new dish into the recipe book (and optionally plan it)."""
    from app.api.v1.recipes import RecipeIn, _recipe_out, _search_text, _to_recipe

    recipe_data = payload.get("recipe") or {}
    title = (recipe_data.get("title") or payload.get("title") or "").strip()
    if not title:
        raise HTTPException(422, "Proposal has no title")
    payload_in = RecipeIn(
        title=title,
        description=recipe_data.get("description", ""),
        servings=int(recipe_data.get("servings") or 4),
        prep_minutes=recipe_data.get("prep_minutes"),
        cook_minutes=recipe_data.get("cook_minutes"),
        instructions=[str(x) for x in (recipe_data.get("instructions") or [])],
        ingredients=recipe_data.get("ingredients") or [],
        tags=recipe_data.get("tags") or [],
        source_name="AI suggestion",
    )
    r = _to_recipe(payload_in, user)
    r.search_text = _search_text(r)
    session.add(r)
    session.commit()
    session.refresh(r)
    planned = False
    if payload.get("date") and payload.get("slot") and user.household_id is not None:
        entry = MealPlanEntry(
            household_id=user.household_id, recipe_id=r.id,
            planned_date=date.fromisoformat(payload["date"]), slot=payload["slot"],
        )
        session.add(entry)
        session.commit()
        planned = True
    return {**_recipe_out(r), "planned": planned}


def _refill_prompt(h: Household | None, recipes: list[Recipe], empty: list[tuple[str, str]]) -> str:
    profile = {
        "dietary_preferences": h.dietary_preferences if h else {},
        "allergies": h.allergies if h else [],
        "dislikes": h.dislikes if h else [],
        "favorites": [f for f in (h.favorites if h else [])],
        "things_to_remember": h.things_to_remember if h else "",
    }
    fav_ids = {r.id for r in recipes if r.is_favorite}
    book = [
        {"id": r.id, "title": r.title, "tags": r.tags or [], "favorite": r.id in fav_ids}
        for r in recipes[:60]
    ]
    return (
        "You are planning meals for a household. Fill each empty slot listed below. "
        "STRICTLY respect allergies and dislikes. Prefer favorite recipes when sensible, "
        "and keep variety across the week. For each empty slot either pick a recipe from "
        "their book BY EXACT TITLE, or propose a new dish with a COMPLETE recipe JSON. "
        "New dishes must respect the profile too. Reply as JSON exactly: "
        '{"picks":[{"date":string,"slot":string,"title":string,"why":short string,'
        '"recipe": null | {"title":string,"description":string,"servings":int,'
        '"prep_minutes":int,"cook_minutes":int,"tags":[string],'
        '"ingredients":[{"name":string,"quantity":number,"unit":string}],'
        '"instructions":[string]}]}. '
        f"Empty slots: {empty}. Household profile: {profile}. Their recipe book: {book}"
    )


def _suggestion_prompt(h: Household | None, recipes: list[Recipe], extra: dict) -> str:
    profile = {
        "dietary_preferences": h.dietary_preferences if h else {},
        "allergies": h.allergies if h else [],
        "dislikes": h.dislikes if h else [],
        "favorites": h.favorites if h else [],
        "things_to_remember": h.things_to_remember if h else "",
    }
    titles = [r.title for r in recipes[:40]]
    return (
        "Suggest 3 dinner ideas for a household. Respect allergies and dislikes strictly. "
        "Prefer their favorites when sensible. Reply as JSON: "
        '{"suggestions":[{"title":string,"why":string,"uses_pantry":bool}]}. '
        f"Household profile: {profile}. Existing recipes: {titles}. "
        f"Extra context: {extra}"
    )

# LLM module: any OpenAI-compatible endpoint (Ollama, llama.cpp, LocalAI, cloud)
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import get_current_user, require_household
from app.db.engine import get_session
from app.models import Household, Recipe, User
from app.services import llm_client
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

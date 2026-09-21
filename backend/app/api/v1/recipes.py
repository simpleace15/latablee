# Recipes: CRUD, search, tags. Images via /images (Docker volume).
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import require_household
from app.db.engine import get_session
from app.models import Ingredient, Recipe, User
from app.services.recipe_search import index_search_text
from app.services.unit_conversion import normalize_ingredient_units

router = APIRouter()


class RecipeIn(BaseModel):
    title: str
    description: str = ""
    servings: int = 4
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    instructions: list[str] = []
    ingredients: list[Ingredient] = []
    tags: list[str] = []
    # provenance (set by URL/photo imports, preserved on review-save)
    source_url: str | None = None
    source_name: str | None = None
    # base64 image bytes from URL import — stored locally on save
    image_b64: str | None = None


def _search_text(r: Recipe) -> str:
    parts = [r.title, r.description]
    for ing in r.ingredients or []:
        parts.append(ing.get("name", "") if isinstance(ing, dict) else str(ing))
    for t in r.tags or []:
        parts.append(t)
    return " ".join(p.lower() for p in parts if p)


def _to_recipe(payload: RecipeIn, user: User) -> Recipe:
    normalized = normalize_ingredient_units(payload.ingredients)
    return Recipe(
        title=payload.title,
        description=payload.description,
        servings=payload.servings,
        prep_minutes=payload.prep_minutes,
        cook_minutes=payload.cook_minutes,
        total_minutes=(payload.prep_minutes or 0) + (payload.cook_minutes or 0) or None,
        instructions=payload.instructions,
        ingredients=normalized,
        tags=payload.tags,
        source_url=payload.source_url,
        source_name=payload.source_name,
        created_by=user.id,
        household_id=user.household_id,
    )


def get_recipe_or_404(recipe_id: int, session: Session, user: User) -> Recipe:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(404, "Recipe not found")
    if recipe.household_id != user.household_id:
        raise HTTPException(404, "Recipe not found")  # don't leak existence
    return recipe


@router.get("")
def list_recipes(
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
    q: str = "",
    tag: str = "",
    favorite: str = "",  # "1" → only favorites
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    stmt = select(Recipe).where(Recipe.household_id == user.household_id)
    recipes = session.exec(stmt).all()
    if q:
        ql = q.lower().strip()
        recipes = [r for r in recipes if ql in (r.search_text or "")]
    if tag:
        recipes = [r for r in recipes if tag in (r.tags or [])]
    if favorite == "1":
        recipes = [r for r in recipes if r.is_favorite]
    return [_recipe_out(r) for r in recipes[offset:offset + limit]]


@router.post("", status_code=201)
def create_recipe(
    payload: RecipeIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    r = _to_recipe(payload, user)
    r.search_text = _search_text(r)
    session.add(r)
    session.commit()
    session.refresh(r)
    if payload.image_b64:
        _store_b64_image(r, payload.image_b64)
        session.add(r)
        session.commit()
        session.refresh(r)
    return _recipe_out(r)


def _store_b64_image(recipe: Recipe, b64: str) -> None:
    """Persist an imported image (validated, size-capped) to the local volume."""
    import base64
    import binascii
    import imghdr
    import uuid

    from app.core.config import IMAGES_DIR, get_settings

    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        return
    kind = imghdr.what(None, h=data)
    if kind not in ("jpeg", "png", "webp") or len(data) > get_settings().max_upload_bytes:
        return
    dest = IMAGES_DIR / f"recipe-{recipe.id}-{uuid.uuid4().hex[:8]}.{kind}"
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    recipe.image_path = str(dest.relative_to(IMAGES_DIR.parent))


@router.get("/{recipe_id}")
def get_recipe(
    recipe_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return _recipe_out(get_recipe_or_404(recipe_id, session, user))


@router.put("/{recipe_id}")
def update_recipe(
    recipe_id: int,
    payload: RecipeIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    r = get_recipe_or_404(recipe_id, session, user)
    data = payload.model_dump(exclude={"image_b64"})
    for k, v in data.items():
        setattr(r, k, v)
    r.ingredients = normalize_ingredient_units(payload.ingredients)
    r.total_minutes = (payload.prep_minutes or 0) + (payload.cook_minutes or 0) or None
    r.search_text = _search_text(r)
    session.add(r)
    session.commit()
    session.refresh(r)
    return _recipe_out(r)


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    r = get_recipe_or_404(recipe_id, session, user)
    session.delete(r)
    session.commit()


@router.post("/{recipe_id}/image", status_code=201)
async def upload_image(
    recipe_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
) -> dict:
    from app.core.config import IMAGES_DIR
    from app.services.images import save_recipe_image

    get_recipe_or_404(recipe_id, session, user)
    path = await save_recipe_image(recipe_id, file)
    recipe = session.get(Recipe, recipe_id)
    recipe.image_path = str(path.relative_to(IMAGES_DIR.parent))
    session.add(recipe)
    session.commit()
    return {"image_path": f"/images/{path.name}"}


@router.put("/{recipe_id}/favorite")
def toggle_favorite(
    recipe_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
    favorite: bool = True,
) -> dict:
    """Heart/unheart a recipe (household-wide, like the recipe itself)."""
    r = get_recipe_or_404(recipe_id, session, user)
    r.is_favorite = favorite
    session.add(r)
    session.commit()
    return {"id": r.id, "is_favorite": r.is_favorite}


def _recipe_out(r: Recipe) -> dict:
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "is_favorite": r.is_favorite,
        "servings": r.servings, "prep_minutes": r.prep_minutes,
        "cook_minutes": r.cook_minutes, "total_minutes": r.total_minutes,
        "instructions": r.instructions, "ingredients": r.ingredients, "tags": r.tags,
        "source_url": r.source_url, "source_name": r.source_name,
        "image_path": r.image_path,
        "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
    }


# keep import referenced (unit conversion module is exercised via _to_recipe)
_ = index_search_text

# Bulk migration import: Mealie backup zip / schema.org JSON → LaTablée (admin-only)
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from app.core.security import get_current_user, require_household
from app.db.engine import get_session
from app.models import User
from app.services.mealie_import import parse_upload
from app.services.recipe_search import index_search_text
from app.services.unit_conversion import normalize_ingredient_units

router = APIRouter()


def _apply_parsed(session: Session, user: User, parsed: dict, load_images: bool, dry_run: bool) -> dict:
    """Shared create path for zip + json uploads. Images keyed by exact recipe title."""
    from app.api.v1.recipes import RecipeIn
    from app.models import Recipe

    titles_in = {r["title"] for r in parsed["recipes"]}
    created, failed = 0, []
    if dry_run:
        return {"dry_run": True, "would_import": len(parsed["recipes"]), "skipped": parsed["skipped"],
                "format": parsed["format"], "with_images": sum(1 for t in parsed["images"] if t in titles_in)}
    for item in parsed["recipes"]:
        try:
            payload = RecipeIn(
                title=item["title"], description=item.get("description") or "",
                servings=item.get("servings") or 4,
                prep_minutes=item.get("prep_minutes"), cook_minutes=item.get("cook_minutes"),
                instructions=item.get("instructions") or [],
                ingredients=item.get("ingredients") or [],
                tags=item.get("tags") or [],
                source_url=item.get("source_url"), source_name=item.get("source_name"),
            )
            r = Recipe(
                title=payload.title, description=payload.description, servings=payload.servings,
                prep_minutes=payload.prep_minutes, cook_minutes=payload.cook_minutes,
                total_minutes=(payload.prep_minutes or 0) + (payload.cook_minutes or 0) or None,
                instructions=payload.instructions,
                ingredients=normalize_ingredient_units(payload.ingredients),
                tags=payload.tags, source_url=payload.source_url, source_name=payload.source_name,
                created_by=user.id, household_id=user.household_id,
            )
            r.search_text = index_search_text(r)
            session.add(r)
            session.commit()
            session.refresh(r)
            created += 1
            img = parsed["images"].get(item["title"])
            if load_images and img:
                _store_image(r, img, session)
        except Exception as e:  # noqa: BLE001 — one bad recipe must not kill the batch
            failed.append({"title": item.get("title", "?"), "error": str(e)[:120]})
            session.rollback()
    return {"imported": created, "failed": failed, "skipped": parsed["skipped"], "format": parsed["format"]}


def _store_image(recipe, data: bytes, session: Session) -> None:
    import imghdr
    import uuid

    from app.core.config import IMAGES_DIR

    kind = imghdr.what(None, h=data)
    if kind not in ("jpeg", "png", "webp"):
        return
    dest = IMAGES_DIR / f"recipe-{recipe.id}-{uuid.uuid4().hex[:8]}.{kind}"
    dest.write_bytes(data)
    recipe.image_path = str(dest.relative_to(IMAGES_DIR.parent))
    session.add(recipe)
    session.commit()


@router.post("/preview", status_code=200)
async def preview_import(
    user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File()],
) -> dict:
    """Dry-run: parse the upload and report counts without writing anything."""
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    data = await file.read()
    try:
        parsed = parse_upload(file.filename or "upload", data)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return _apply_parsed(None, user, parsed, load_images=False, dry_run=True)


@router.post("", status_code=200)
async def run_import(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
    load_images: bool = True,
) -> dict:
    """Bulk-import recipes from a Mealie backup zip or schema.org JSON file."""
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    data = await file.read()
    try:
        parsed = parse_upload(file.filename or "upload", data)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    result = _apply_parsed(session, user, parsed, load_images=load_images, dry_run=False)
    from app.services.events import record_event
    record_event(session, "recipes.imported", {"count": result["imported"], "format": result["format"]})
    return result


_ = require_household  # keep import referenced (household gating happens in recipes router)

# Recipe search: denormalized search_text maintained on write; LIKE query at read.
from sqlmodel import Session

from app.models import Recipe


def index_search_text(recipe: Recipe) -> str:
    parts = [recipe.title, recipe.description]
    for ing in recipe.ingredients or []:
        if isinstance(ing, dict):
            parts.append(str(ing.get("name", "")))
        else:
            parts.append(str(ing))
    parts.extend(recipe.tags or [])
    return " ".join(p.lower().strip() for p in parts if p)


def search(session: Session, household_id: int, query: str, tag: str | None = None) -> list[Recipe]:
    from sqlmodel import select

    recipes = list(session.exec(select(Recipe).where(Recipe.household_id == household_id)))
    ql = query.lower().strip()
    if ql:
        recipes = [r for r in recipes if ql in (r.search_text or "")]
    if tag:
        recipes = [r for r in recipes if tag in (r.tags or [])]
    return recipes

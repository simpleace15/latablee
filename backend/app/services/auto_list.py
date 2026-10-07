# Auto-add-to-list toggle (0.7.3): ingredients of AI-planned meals flow onto the
# default shopping list when the household toggle is ON (NULL/None = ON).
"""Shared helper: push a recipe's ingredients onto the household's default list.

Used by refill-week (filled picks + replace-clearing), save-proposal, and the
voice refill path — one funnel so the toggle behaves identically everywhere.
"""
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from app.models import Household, Recipe, ShoppingList, User

if TYPE_CHECKING:
    pass


def default_list(session: Session, user: User) -> ShoppingList:
    """The household's first list; create 'Groceries' if none exists yet
    (same shape as voice._default_list — kept here to avoid an import cycle)."""
    lst = session.exec(
        select(ShoppingList).where(ShoppingList.household_id == user.household_id)
    ).first()
    if lst is None:
        lst = ShoppingList(name="Groceries", household_id=user.household_id)
        session.add(lst)
        session.commit()
    return lst


def auto_add_enabled(session: Session, user: User) -> bool:
    """Household toggle; NULL column = default ON (permissive, never blocks)."""
    if user.household_id is None:
        return False
    h = session.get(Household, user.household_id)
    return True if h is None or h.auto_add_to_list is None else bool(h.auto_add_to_list)


# Kept out of the hot path: local import inside the function body keeps this
# module import-light for tools that read only the household API.
def _scale(quantity, factor: float):
    if quantity is None or factor == 1.0:
        return quantity
    from app.services.unit_conversion import scale_quantity

    try:
        return scale_quantity(float(quantity), factor)
    except (TypeError, ValueError):
        return quantity  # non-numeric ("to taste") — pass through


def add_recipe_ingredients(
    session: Session,
    user: User,
    recipes: list[Recipe],
    servings: int | None = None,
) -> int:
    """Merge each recipe's ingredients into the default list (additive — existing
    items consolidate, never deleted). Returns the number of ingredient lines added.
    Caller checks auto_add_enabled() FIRST; this assumes it's allowed."""
    if not recipes or user.household_id is None:
        return 0
    from app.api.v1.lists import ItemIn, _recipe_factor, consolidate_items

    lst = default_list(session, user)
    if lst.id is None or user.household_id is None:  # unreachable; typing guards
        return 0
    recipe_factor = _recipe_factor(recipes[0], servings, None)
    items: list[ItemIn] = []
    for r in recipes:
        for ing in r.ingredients or []:
            q = _scale(ing.get("quantity"), recipe_factor)
            items.append(ItemIn(
                name=ing.get("name", ""),
                quantity=q,
                unit=ing.get("unit"),
            ))
    consolidate_items(session, items, lst.id, user.household_id,
                      from_recipe_ids=[r.id for r in recipes if r.id is not None])
    session.commit()
    return len(items)

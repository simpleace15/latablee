# Shopping lists: generation from plan, consolidation, check-off, multi-list
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import require_household
from app.db.engine import get_session
from app.models import MealPlanEntry, Recipe, ShoppingList, ShoppingListItem, User
from app.services.events import record_event

router = APIRouter()


class ListIn(BaseModel):
    name: str = "Groceries"


class ItemIn(BaseModel):
    name: str
    quantity: float | None = None
    unit: str | None = None


class CheckIn(BaseModel):
    done: bool


def _list_or_404(list_id: int, user: User, session: Session) -> ShoppingList:
    lst = session.get(ShoppingList, list_id)
    if lst is None or lst.household_id != user.household_id:
        raise HTTPException(404, "List not found")
    return lst


def _item_out(i: ShoppingListItem) -> dict:
    return {"id": i.id, "name": i.name, "quantity": i.quantity, "unit": i.unit,
            "done": i.done, "manual": i.manual, "from_recipe_ids": i.from_recipe_ids}


def _list_out(session: Session, lst: ShoppingList) -> dict:
    items = session.exec(select(ShoppingListItem).where(ShoppingListItem.list_id == lst.id)).all()
    items.sort(key=lambda i: (i.done, i.name.lower()))
    return {"id": lst.id, "name": lst.name, "items": [_item_out(i) for i in items]}


@router.get("")
def get_lists(
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict]:
    lists_ = session.exec(select(ShoppingList).where(ShoppingList.household_id == user.household_id)).all()
    return [_list_out(session, lst) for lst in lists_]


@router.post("", status_code=201)
def create_list(
    payload: ListIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    lst = ShoppingList(name=payload.name, household_id=user.household_id)
    session.add(lst)
    session.commit()
    session.refresh(lst)
    return _list_out(session, lst)


@router.get("/{list_id}")
def get_list(
    list_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return _list_out(session, _list_or_404(list_id, user, session))


@router.delete("/{list_id}", status_code=204)
def delete_list(
    list_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    lst = _list_or_404(list_id, user, session)
    for item in session.exec(select(ShoppingListItem).where(ShoppingListItem.list_id == lst.id)):
        session.delete(item)
    session.delete(lst)
    session.commit()


@router.post("/{list_id}/items", status_code=201)
def add_item(
    list_id: int,
    payload: ItemIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    lst = _list_or_404(list_id, user, session)
    household_id = user.household_id
    assert household_id is not None  # require_household guarantees
    merged = consolidate_items(session, [payload], lst.id, household_id)
    session.commit()
    record_event(session, "shopping_list_updated", {"list_id": lst.id})
    return _item_out(merged[0])


@router.patch("/{list_id}/items/{item_id}")
def check_item(
    list_id: int,
    item_id: int,
    payload: CheckIn,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    _list_or_404(list_id, user, session)
    item = session.get(ShoppingListItem, item_id)
    if item is None or item.list_id != list_id:
        raise HTTPException(404, "Item not found")
    item.done = payload.done
    session.add(item)
    session.commit()
    session.refresh(item)
    record_event(session, "shopping_list_updated", {"list_id": list_id, "item_id": item_id})
    return _item_out(item)


@router.delete("/{list_id}/items/{item_id}", status_code=204)
def remove_item(
    list_id: int,
    item_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    _list_or_404(list_id, user, session)
    item = session.get(ShoppingListItem, item_id)
    if item is None or item.list_id != list_id:
        raise HTTPException(404, "Item not found")
    session.delete(item)
    session.commit()
    record_event(session, "shopping_list_updated", {"list_id": list_id, "removed": item_id})


@router.post("/{list_id}/generate-from-plan")
def generate_from_plan(
    list_id: int,
    user: Annotated[User, Depends(require_household)],
    session: Annotated[Session, Depends(get_session)],
    start: str | None = None,
    days: int = 7,
) -> dict:
    """Merge ingredients from planned recipes into this list (consolidates duplicates)."""
    from datetime import date as date_cls

    from app.services.dates import household_today

    lst = _list_or_404(list_id, user, session)
    start_date = date_cls.fromisoformat(start) if start else household_today(session, user.household_id)
    entries = session.exec(
        select(MealPlanEntry).where(
            MealPlanEntry.household_id == user.household_id,
            MealPlanEntry.planned_date >= start_date,
        )
    ).all()
    recipes = []
    for e in entries[: max(days, 0) * 4]:
        if e.recipe_id:
            r = session.get(Recipe, e.recipe_id)
            if r and r.household_id == user.household_id:
                recipes.append(r)
    new_items: list[ItemIn] = []
    household_id = user.household_id
    assert household_id is not None  # require_household guarantees
    for r in recipes:
        for ing in r.ingredients or []:
            new_items.append(ItemIn(
                name=ing.get("name", ""),
                quantity=ing.get("quantity"),
                unit=ing.get("unit"),
            ))
    consolidate_items(session, new_items, lst.id, user.household_id, from_recipe_ids=[r.id for r in recipes])
    session.commit()
    record_event(session, "shopping_list_updated", {"list_id": lst.id, "generated": True})
    return _list_out(session, lst)


def consolidate_items(
    session: Session,
    items: list[ItemIn],
    list_id: int,
    household_id: int,
    from_recipe_ids: list[int] | None = None,
) -> list[ShoppingListItem]:
    """Merge duplicates by (name.lower, unit); sum quantities in compatible units."""
    existing = session.exec(select(ShoppingListItem).where(ShoppingListItem.list_id == list_id)).all()
    index = {(i.name.lower(), i.unit): i for i in existing if not i.done}
    out: list[ShoppingListItem] = []
    from app.services.unit_conversion import can_add, canonical_unit, convert

    for item in items:
        if not item.name.strip():
            continue
        item.unit = canonical_unit(item.unit) or None
        key = (item.name.strip().lower(), item.unit)
        target = index.get(key)
        if target is None:
            # try unit-compatible match (e.g. 500 g + 1 kg -> 1500 g)
            for (name_l, _unit), candidate in index.items():
                if name_l == item.name.strip().lower() and candidate.unit and item.unit \
                        and can_add(candidate.unit, item.unit):
                    converted = convert(item.quantity, item.unit, candidate.unit)
                    target = candidate
                    if converted is not None and item.quantity is not None:
                        candidate.quantity = (candidate.quantity or 0) + converted
                    break
        if target is not None:
            if target.unit == item.unit and item.quantity is not None:
                target.quantity = (target.quantity or 0) + item.quantity
            if from_recipe_ids:
                ids = set(target.from_recipe_ids or []) | set(from_recipe_ids)
                target.from_recipe_ids = sorted(ids)
            session.add(target)
            out.append(target)
        else:
            new = ShoppingListItem(
                list_id=list_id,
                name=item.name.strip(),
                quantity=item.quantity,
                unit=item.unit,
                manual=from_recipe_ids is None,
                from_recipe_ids=from_recipe_ids or [],
            )
            session.add(new)
            index[key] = new
            out.append(new)
    return out

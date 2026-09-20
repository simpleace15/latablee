# Data export: full JSON of recipes/plans/lists + backup archive (DB + images)
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import DATA_DIR, IMAGES_DIR
from app.db.engine import get_engine
from app.models import Household, MealPlanEntry, Recipe, ShoppingList, ShoppingListItem


def export_json() -> dict:
    with Session(get_engine()) as session:
        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "household": [dict(row) for row in session.exec(select(Household)).all()],
            "recipes": [_recipe_row(r) for r in session.exec(select(Recipe)).all()],
            "plan": [_plan_row(p) for p in session.exec(select(MealPlanEntry)).all()],
            "lists": [_list_row(session, lst) for lst in session.exec(select(ShoppingList)).all()],
        }


def _recipe_row(r: Recipe) -> dict:
    return {"id": r.id, "title": r.title, "description": r.description,
            "servings": r.servings, "instructions": r.instructions,
            "ingredients": r.ingredients, "tags": r.tags, "image_path": r.image_path}


def _plan_row(p: MealPlanEntry) -> dict:
    return {"id": p.id, "date": p.planned_date.isoformat(), "slot": p.slot,
            "recipe_id": p.recipe_id, "title_override": p.title_override}


def _list_row(session: Session, lst: ShoppingList) -> dict:
    items = session.exec(select(ShoppingListItem).where(ShoppingListItem.list_id == lst.id)).all()
    return {"id": lst.id, "name": lst.name,
            "items": [{"id": i.id, "name": i.name, "quantity": i.quantity, "unit": i.unit,
                       "done": i.done} for i in items]}


def write_json_export() -> Path:
    dest = DATA_DIR / "exports" / f"latablee-export-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    dest.write_text(json.dumps(export_json(), indent=2))
    return dest


def build_backup_archive() -> Path:
    """ZIP of DB file + images dir + JSON export — a family's recipes are never locked in."""
    dest = DATA_DIR / "exports" / f"latablee-backup-{datetime.now(UTC):%Y%m%d-%H%M%S}.zip"
    db_path = Path(str(get_engine().url).removeprefix("sqlite:///"))
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        if db_path.exists():
            zf.write(db_path, arcname=db_path.name)
        json_bytes = json.dumps(export_json(), indent=2).encode()
        zf.writestr("export.json", json_bytes)
        if IMAGES_DIR.exists():
            for img in IMAGES_DIR.iterdir():
                if img.is_file():
                    zf.write(img, arcname=f"images/{img.name}")
    return dest

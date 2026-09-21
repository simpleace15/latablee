# Backup restore: rehydrate a LaTablée instance from a backup archive (or JSON export).
# Merge-free by design: restore replaces ALL data (wipe + restore) so IDs and image paths
# stay consistent — the UI requires an explicit confirmation before calling this.
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import IMAGES_DIR
from app.db.engine import get_engine
from app.models import (
    ApiToken,
    Household,
    InviteLink,
    MealPlanEntry,
    Recipe,
    ShoppingList,
    ShoppingListItem,
    User,
)


def restore_from_archive(data: bytes) -> dict[str, int]:
    """Accepts a backup ZIP (DB + images + export.json) or a bare export.json."""
    counts: dict[str, int] = {}
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            export_name = next((n for n in names if n.endswith("export.json")), None)
            if export_name is None:
                raise ValueError("Archive has no export.json — not a LaTablée backup")
            payload = json.loads(zf.read(export_name))
            _restore_images(zf, names)
    else:
        payload = json.loads(data.decode())
    counts = _wipe_and_restore(payload)
    counts["images"] = len(list(IMAGES_DIR.iterdir())) if IMAGES_DIR.exists() else 0
    return counts


def _restore_images(zf: zipfile.ZipFile, names: list[str]) -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    for n in names:
        if n.startswith("images/") and not n.endswith("/"):
            dest = IMAGES_DIR / Path(n).name
            if not dest.exists():
                dest.write_bytes(zf.read(n))


def _wipe_and_restore(payload: dict[str, Any]) -> dict[str, int]:
    engine = get_engine()
    with Session(engine) as session:
        # wipe order respects FKs — commit between each level so SQLAlchemy's
        # unit-of-work ordering can't interleave (no relationship() on created_by)
        for model in (ShoppingListItem, ShoppingList, MealPlanEntry, Recipe,
                      ApiToken, InviteLink, User, Household):
            for row in session.exec(select(model)).all():
                session.delete(row)
            session.commit()

        for h in payload.get("household", []):
            session.add(Household(**_clean(h, Household)))
        session.commit()
        hh = session.exec(select(Household)).first()

        id_maps: dict[str, dict[int, int]] = {"user": {}, "recipe": {}, "list": {}}
        for u in payload.get("users", []):
            row = User(**_clean(u, User))
            # keep identity + credentials so existing logins/invites survive restore
            for k in ("public_id", "password_hash"):
                if u.get(k):
                    setattr(row, k, u[k])
            session.add(row)
            session.commit()
            session.refresh(row)
            id_maps["user"][u["id"]] = row.id
        # export.json doesn't carry users (secrets) — restore creates none; callers
        # re-onboard. Recipes/plan/lists attach to the first household + first user.
        first_user = session.exec(select(User)).first()

        for r in payload.get("recipes", []):
            row = Recipe(**_clean(r, Recipe))
            row.household_id = hh.id if hh else None
            row.created_by = getattr(first_user, "id", None)
            session.add(row)
            session.commit()
            session.refresh(row)
            id_maps["recipe"][r["id"]] = row.id

        for p in payload.get("plan", []):
            row = MealPlanEntry(**_clean(p, MealPlanEntry))
            row.household_id = hh.id if hh else None
            row.recipe_id = id_maps["recipe"].get(p.get("recipe_id"))
            session.add(row)

        for lst in payload.get("lists", []):
            row = ShoppingList(**_clean(lst, ShoppingList))
            row.household_id = hh.id if hh else None
            session.add(row)
            session.commit()
            session.refresh(row)
            for item in lst.get("items", []):
                session.add(ShoppingListItem(**_clean(
                    {**item, "list_id": row.id}, ShoppingListItem)))
        session.commit()

        return {"households": 1 if hh else 0, "users": len(id_maps["user"]),
                "recipes": len(id_maps["recipe"]),
                "plan": len(payload.get("plan", [])),
                "lists": len(payload.get("lists", []))}


def _clean(row: dict[str, Any], model: type) -> dict[str, Any]:
    """Keep only fields the model declares; drop ids/timestamps/token secrets."""
    from datetime import date, datetime

    allowed = set(model.model_fields.keys())  # type: ignore[attr-defined]
    drop = {"id", "created_at", "updated_at", "token_hash", "last_used_at", "revoked_at"}
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k not in allowed or k in drop or v is None:
            continue
        ann = model.model_fields[k].annotation
        # export.json stores datetimes as ISO strings — parse them back.
        # Annotations may be Optional[datetime] — check by name, simplest & version-proof.
        name = str(ann)
        if isinstance(v, str):
            if "datetime" in name:
                v = datetime.fromisoformat(v)
            elif "date" in name and "datetime" not in name:
                v = date.fromisoformat(v)
        out[k] = v
    return out

# Mealie migration import: parse a Mealie backup zip (or plain schema.org JSON) into
# LaTablée RecipeIn-shaped dicts. The user's recipe collection must never be locked in
# to any one app — including this one.
#
# Supported inputs:
#   - Mealie admin backup zip (Settings → Backups → Create Backup):
#     * current Mealie: database.json ({"recipes": [...]}) + data/ dir with images
#     * older Mealie: recipes/<slug>/<slug>.json (+ optional images per folder)
#   - A zip of per-recipe schema.org JSON-LD files (Tandoor/Nextcloud exports)
#   - A single .json file: one recipe, or an array of them
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import PurePosixPath
from typing import Any

MAX_ZIP_BYTES = 512 * 1024 * 1024  # hard cap; Mealie collections with images run ~100-400MB
MAX_ENTRIES = 5000  # sanity cap — a household collection, not a datacenter


def parse_upload(name: str, data: bytes) -> dict:
    """Detect and parse. Returns {recipes: [...], images: {recipe_title: bytes}, skipped: n, source_format: str}."""
    if name.lower().endswith(".zip") or data[:2] == b"PK":
        return _parse_zip(data)
    return _parse_json_file(name, data)


# ---------- zip formats ----------

def _parse_zip(data: bytes) -> dict:
    if len(data) > MAX_ZIP_BYTES:
        raise ValueError(f"Backup zip too large ({len(data) // (1024 * 1024)} MB, max 512 MB)")
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()

    # path → (recipe dict, folder prefix) for per-recipe files
    recipes: list[dict] = []
    images: dict[str, bytes] = {}  # key: recipe title (slug folder preferred), fallback title
    skipped = 0
    format_ = "unknown"

    # 1) current Mealie: database.json at root with {"recipes": [...]}
    db_name = next((n for n in names if n == "database.json" or n.endswith("/database.json")), None)
    per_recipe_files = [n for n in names if _recipe_json_path(n)]

    if db_name:
        format_ = "mealie-backup"
        payload = json.loads(zf.read(db_name).decode("utf-8", "replace"))
        raw = payload.get("recipes", []) if isinstance(payload, dict) else payload
        # images live under data/... — Mealie stores recipe images by recipe slug
        slug_images = _mealie_images(zf, names)
        for item in raw:
            conv = _mealie_recipe_to_latablee(item)
            if conv is None:
                skipped += 1
                continue
            recipes.append(conv)
            slug = item.get("slug") or item.get("id")
            img = slug_images.get(str(slug)) or slug_images.get(_slugify(conv["title"]))
            if img:
                images[conv["title"]] = img
    elif per_recipe_files:
        format_ = ("mealie-legacy" if any(n.split("/")[0] == "recipes" or "/recipes/" in n for n in per_recipe_files)
                   else "json-ld-zip")
        folder_images = _folder_images(zf, names)
        for n in sorted(per_recipe_files)[:MAX_ENTRIES]:
            try:
                item = json.loads(zf.read(n).decode("utf-8", "replace"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                skipped += 1
                continue
            conv = _mealie_recipe_to_latablee(item) if _looks_like_mealie(item) else _schema_recipe_to_latablee(item)
            if conv is None:
                skipped += 1
                continue
            recipes.append(conv)
            folder = str(PurePosixPath(n).parent)
            img = folder_images.get(folder) or folder_images.get(_slugify(conv["title"]))
            if img:
                images[conv["title"]] = img
    else:
        raise ValueError("No recipes found — expected Mealie backup (database.json or recipes/<slug>/) or JSON recipe files")

    if len(recipes) > MAX_ENTRIES:
        recipes = recipes[:MAX_ENTRIES]
    return {"recipes": recipes, "images": images, "skipped": skipped, "format": format_}


def _recipe_json_path(name: str) -> bool:
    p = PurePosixPath(name)
    # <anything>/<slug>/<slug>.json — Mealie legacy layout, or a flat folder of recipe jsons
    return p.suffix == ".json" and p.name == p.parent.name + ".json" and not p.name.startswith(".")


def _mealie_images(zf: zipfile.ZipFile, names: list[str]) -> dict[str, bytes]:
    """data/recipes/<slug>/webp|original|... — Mealie stores several sizes; prefer 'webp' then 'min-original'."""
    out: dict[str, bytes] = {}
    for n in names:
        parts = PurePosixPath(n).parts
        if len(parts) >= 3 and parts[0] == "data" and parts[1] in ("recipes", "recipe"):
            slug = parts[2]
            fname = parts[-1].lower()
            if fname in ("webp.jpg", "webp.webp", "webp") or fname.startswith("webp"):
                out.setdefault(slug, zf.read(n))
    # fallback: any image in the recipe folder
    for n in names:
        parts = PurePosixPath(n).parts
        if len(parts) >= 4 and parts[0] == "data" and parts[1] in ("recipes", "recipe"):
            slug = parts[2]
            fname = parts[-1].lower()
            if fname.endswith((".jpg", ".jpeg", ".png", ".webp")) and slug not in out:
                out[slug] = zf.read(n)
    return out


def _folder_images(zf: zipfile.ZipFile, names: list[str]) -> dict[str, bytes]:
    """Images keyed by their parent folder (per-recipe folder layouts)."""
    out: dict[str, bytes] = {}
    for n in names:
        p = PurePosixPath(n)
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and len(p.parts) >= 2:
            folder = str(p.parent)
            # prefer the largest file if multiple images share a folder
            if folder not in out or zf.getinfo(n).file_size > len(out[folder]):
                out[folder] = zf.read(n)
    return out


# ---------- field mapping ----------

def _looks_like_mealie(item: dict) -> bool:
    keys = set(item.keys())
    return bool(keys & {"recipeIngredient", "recipeInstructions", "orgURL", "slug", "dateAdded"}) or "name" in keys and "recipeIngredient" in keys


def _mealie_recipe_to_latablee(item: dict) -> dict | None:
    """Mealie's recipe model → LaTablée shape. Ingredient strings preserved raw (unit
    normalization happens on save via normalize_ingredient_units)."""
    title = (item.get("name") or "").strip()
    if not title:
        return None
    return {
        "title": title,
        "description": item.get("description") or "",
        "servings": item.get("recipeServings") or 4,
        "prep_minutes": _minutes(item.get("prepTime")),
        "cook_minutes": _minutes(item.get("performTime") or item.get("cookTime")),
        "instructions": _steps(item.get("recipeInstructions")),
        "ingredients": [{"name": s} for s in (item.get("recipeIngredient") or [])],
        "tags": _tags(item),
        "source_url": item.get("orgURL"),
        "source_name": item.get("source_name") or None,
    }


def _schema_recipe_to_latablee(item: dict) -> dict | None:
    title = (item.get("name") or "").strip()
    if not title:
        return None
    return {
        "title": title,
        "description": item.get("description") or "",
        "servings": item.get("recipeYield") if isinstance(item.get("recipeYield"), int) else 4,
        "prep_minutes": _minutes(item.get("prepTime")),
        "cook_minutes": _minutes(item.get("cookTime")),
        "instructions": _steps(item.get("recipeInstructions")),
        "ingredients": [{"name": s} for s in _schema_ingredients(item)],
        "tags": [t for t in (item.get("keywords") or "").split(",") if t.strip()] if isinstance(item.get("keywords"), str) else [],
        "source_url": item.get("url") or item.get("orgURL"),
        "source_name": None,
    }


def _schema_ingredients(item: dict) -> list[str]:
    ing = item.get("recipeIngredient", [])
    out = []
    for i in ing:
        if isinstance(i, str):
            out.append(i)
        elif isinstance(i, dict):
            # schema.org ingredient objects: amount + name
            out.append(f"{i.get('amount', '')} {i.get('name', '')}".strip())
    return out


def _steps(raw: Any) -> list[str]:
    """recipeInstructions: string, list[str], list[dict('text')], or nested ItemList — same
    shapes as the URL importer, so share the flatten logic."""
    from app.services.recipe_url_import import _flatten_instructions

    return _flatten_instructions(raw)


def _tags(item: dict) -> list[str]:
    tags: list[str] = []
    for t in item.get("tags", []) or []:
        tags.append(str(t.get("name", "")).strip() if isinstance(t, dict) else str(t).strip())
    # recipeCategory: str | list[str] — check str BEFORE iterating (a str iterates per-character)
    cat = item.get("recipeCategory")
    if isinstance(cat, str):
        tags.append(cat.strip())
    elif isinstance(cat, list):
        for c in cat:
            tags.append(str(c.get("name", "")).strip() if isinstance(c, dict) else str(c).strip())
    seen: set[str] = set()
    return [t for t in (s.strip() for s in tags) if t and not (t.lower() in seen or seen.add(t.lower()))]


def _minutes(raw: Any) -> int | None:
    """Mealie durations come as 'PT15M' ISO-8601, seconds-int, or None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw) // 60 if int(raw) >= 60 else int(raw)
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("PT"):
            h = _iso_num(raw, "H")
            m = _iso_num(raw, "M")
            return (h * 60 + m) or None
        if raw.isdigit():
            return int(raw) // 60 if int(raw) >= 60 else int(raw)
    return None


def _iso_num(text: str, unit: str) -> int:
    m = re.search(rf"(\d+){unit}", text)  # ISO-8601: digits BEFORE the unit, e.g. PT20M
    return int(m.group(1)) if m else 0


def _slugify(title: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")


# ---------- plain json ----------

def _parse_json_file(name: str, data: bytes) -> dict:
    text = data.decode("utf-8", "replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    raw = payload if isinstance(payload, list) else [payload]
    recipes, skipped = [], 0
    for item in raw:
        if not isinstance(item, dict):
            skipped += 1
            continue
        conv = _mealie_recipe_to_latablee(item) if _looks_like_mealie(item) else _schema_recipe_to_latablee(item)
        if conv is None:
            skipped += 1
            continue
        recipes.append(conv)
    return {"recipes": recipes[:MAX_ENTRIES], "images": {}, "skipped": skipped, "format": "json-file"}

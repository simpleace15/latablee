# URL import: scrape recipe schema.org/JSON-LD (Recipe schema) from any recipe site.
from typing import Any

import httpx
from extruct import extract as extruct_extract

USER_AGENT = "LaTablee/0.1 (+https://latablee.io; self-hosted recipe importer)"


def import_from_url(url: str) -> dict[str, Any]:
    """Fetch + parse a recipe URL into a structured draft (not auto-saved)."""
    with httpx.Client(timeout=30, follow_redirects=True,
                      headers={"User-Agent": USER_AGENT}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text
    data = extruct_extract(html, syntaxes=["json-ld", "microdata"], uniform=True)
    recipe = _find_recipe(data)
    if recipe is None:
        raise ValueError("No schema.org Recipe found on page")
    return _to_draft(recipe, url)


def _find_recipe(data: dict[str, Any]) -> dict[str, Any] | None:
    candidates = []
    for _syntax, items in data.items():
        if isinstance(items, list):
            candidates.extend(items)
        else:
            candidates.append(items)
    for item in candidates:
        found = _walk(item)
        if found is not None:
            return found
    return None


def _walk(node: Any) -> dict[str, Any] | None:
    if isinstance(node, dict):
        t = node.get("@type")
        if (t == "Recipe") or (isinstance(t, list) and "Recipe" in t):
            return node
        # @graph containers
        graph = node.get("@graph")
        if graph:
            for child in graph:
                found = _walk(child)
                if found:
                    return found
        for value in node.values():
            if isinstance(value, (dict, list)):
                found = _walk(value)
                if found:
                    return found
    elif isinstance(node, list):
        for child in node:
            found = _walk(child)
            if found:
                return found
    return None


def _to_draft(recipe: dict[str, Any], url: str) -> dict[str, Any]:
    ings = recipe.get("recipeIngredient") or recipe.get("ingredients") or []
    ingredients = []
    for raw in ings:
        if isinstance(raw, str):
            ingredients.append(_parse_ingredient_text(raw))
        else:
            ingredients.append({"name": str(raw), "raw": str(raw), "quantity": None,
                                "unit": None})
    steps = recipe.get("recipeInstructions") or []
    if steps and isinstance(steps, list) and isinstance(steps[0], dict):
        steps = [s.get("text", "") for s in steps]
    if isinstance(steps, str):
        steps = [steps]
    draft = {
        "title": (recipe.get("name") or "").strip() or "Imported recipe",
        "description": _clean(recipe.get("description") or ""),
        "servings": _int_or(_clean(recipe.get("recipeYield")), 4),
        "prep_minutes": _duration_minutes(recipe.get("prepTime")),
        "cook_minutes": _duration_minutes(recipe.get("cookTime")),
        "instructions": [s for s in steps if s],
        "ingredients": ingredients,
        "tags": _keywords(recipe.get("keywords")),
        "source_url": url,
        "source_name": recipe.get("author") or "Web",
    }
    if isinstance(recipe.get("author"), dict):
        draft["source_name"] = recipe["author"].get("name") or "Web"
    return draft


def _parse_ingredient_text(raw: str) -> dict[str, Any]:
    """Split '2 cups flour' into quantity/unit/name; keep the raw string for editing."""
    import re

    raw = raw.strip()
    m = re.match(
        r"^(?P<qty>\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?(?:-\d+(?:[.,]\d+)?)?)\s*"
        r"(?P<unit>[a-zA-Zµ.]+)?\s+(?P<name>.+)$", raw)
    if not m:
        return {"name": raw, "quantity": None, "unit": None, "raw": raw}
    qty_text, unit_text, name = m.group("qty"), m.group("unit"), m.group("name").strip()
    quantity = _parse_quantity(qty_text)
    return {"name": name, "quantity": quantity, "unit": (unit_text or "").lower() or None,
            "raw": raw}


def _parse_quantity(qty_text: str) -> float | None:
    """Parse '2', '1.5', '1/2', '1 1/2' fractions into floats."""
    import re

    t = qty_text.strip()
    m = re.match(r"^(\d+)\s+(\d+)\s*/\s*(\d+)$", t)  # 1 1/2
    if m:
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
    m = re.match(r"^(\d+)\s*/\s*(\d+)$", t)  # 1/2
    if m:
        return int(m.group(1)) / int(m.group(2))
    m = re.match(r"^(\d+(?:[.,]\d+)?)(?:-(\d+(?:[.,]\d+)?))?$", t)
    if m:
        val = float(m.group(1).replace(",", "."))
        if m.group(2):  # range: take the upper bound for shopping
            val = max(val, float(m.group(2).replace(",", ".")))
        return val
    return None


def _clean(text: Any) -> str:
    import re

    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", str(text)).strip()


def _int_or(text: Any, default: int) -> int:
    import re

    m = re.search(r"\d+", str(text or ""))
    return int(m.group()) if m else default


def _duration_minutes(value: Any) -> int | None:
    """ISO-8601 duration (PT1H30M) or '1 hour 30 minutes' -> total minutes."""
    import re

    if not value:
        return None
    text = str(value)
    m = re.match(
        r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", text.strip().upper())
    if m:
        d, h, mi, s = (int(g) if g else 0 for g in m.groups())
        total = d * 1440 + h * 60 + mi + (1 if s else 0)
        return total or None
    m = re.search(r"(\d+)\s*hour", text)
    hours = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)\s*min", text)
    minutes = int(m.group(1)) if m else 0
    return (hours * 60 + minutes) or None


def _keywords(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()][:10]
    return [k.strip().lower() for k in str(value).split(",") if k.strip()][:10]

# Unit conversion + ingredient normalization (Pint-backed).
# Recipes store canonical units so shopping-list consolidation can merge 500 g + 1 kg.
from typing import Any

from pint import UnitRegistry

_ureg = UnitRegistry()

# display aliases -> pint-canonical unit names
_UNIT_ALIASES: dict[str, str] = {
    "g": "gram", "gr": "gram", "gram": "gram", "grams": "gram", "gramme": "gram",
    "kg": "kilogram", "kgs": "kilogram", "kilogram": "kilogram", "kilograms": "kilogram",
    "oz": "ounce", "ounce": "ounce", "ounces": "ounce", "lb": "pound", "lbs": "pound",
    "pound": "pound", "pounds": "pound",
    "ml": "milliliter", "milliliter": "milliliter", "millilitre": "milliliter",
    "l": "liter", "liter": "liter", "litre": "liter", "liters": "liter",
    "tsp": "teaspoon", "teaspoon": "teaspoon", "teaspoons": "teaspoon",
    "tbsp": "tablespoon", "tablespoon": "tablespoon", "tablespoons": "tablespoon",
    "cup": "cup", "cups": "cup",
    "clove": "clove", "cloves": "clove",
    "pinch": "pinch", "pinches": "pinch",
    "piece": "piece", "pieces": "piece", "whole": "piece", "item": "piece", "items": "piece",
}

# Pint-native volume/mass units we convert across; countable units stay as-is
_PINT_UNITS = {"gram", "kilogram", "ounce", "pound", "milliliter", "liter",
               "teaspoon", "tablespoon", "cup"}


def canonical_unit(raw: str | None) -> str | None:
    if not raw:
        return None
    return _UNIT_ALIASES.get(raw.strip().lower(), raw.strip().lower())


def _pint_name(unit: str) -> str | None:
    return unit if unit in _PINT_UNITS else None


def convert(quantity: float | None, from_unit: str | None, to_unit: str | None) -> float | None:
    """Convert between compatible canonical units. None if incompatible/no quantity."""
    if quantity is None or not from_unit or not to_unit:
        return None
    src, dst = _pint_name(from_unit), _pint_name(to_unit)
    if src is None or dst is None:
        return None
    try:
        result = _ureg.convert(quantity, src, dst)
    except Exception:  # dimensionality mismatch
        return None
    return float(result)


def can_add(unit_a: str | None, unit_b: str | None) -> bool:
    """True if quantities in these units can be summed (same or convertible)."""
    if not unit_a or not unit_b:
        return False
    if unit_a == unit_b:
        return True
    return convert(1, unit_a, unit_b) is not None


def normalize_ingredient_units(ingredients: list[Any]) -> list[dict[str, Any]]:
    """Normalize each ingredient's unit to canonical form, preserving raw text."""
    out: list[dict[str, Any]] = []
    for ing in ingredients:
        if isinstance(ing, dict):
            data = dict(ing)
        else:
            data = ing.model_dump() if hasattr(ing, "model_dump") else {"name": str(ing)}
        data["unit"] = canonical_unit(data.get("unit")) or ""
        out.append(data)
    return out

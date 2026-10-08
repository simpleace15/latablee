# Bare "Download JSON export" (full snapshot JSON) through the migration card.
# Tyler's prod→new flow: he grabbed the JSON export instead of the backup zip →
# "Found 0 recipes, 1 skipped — format: json-file". parse_upload must detect the
# latablee export envelope ({recipes: [...]}) and import its recipes.
import json

from app.services.mealie_import import parse_upload


def _export_payload() -> dict:
    return {
        "exported_at": "2026-10-07T00:00:00+00:00",
        "household": [{"id": 1, "name": "Home"}],
        "users": [{"id": 1, "name": "Tyler"}],
        "recipes": [
            {"id": 1, "title": "Chili", "servings": 6, "instructions": ["brown"],
             "ingredients": [{"name": "beef"}], "tags": ["dinner"], "image_path": None},
            {"id": 2, "title": "Pad See Ew", "servings": 2},
        ],
        "plan": [],
        "lists": [],
    }


def test_bare_latablee_json_export_imports():
    res = parse_upload("latablee-export.json", json.dumps(_export_payload()).encode())
    assert res["format"] == "latablee-export"
    assert [r["title"] for r in res["recipes"]] == ["Chili", "Pad See Ew"]
    assert res["recipes"][0]["servings"] == 6
    assert res["skipped"] == 0


def test_bare_export_with_single_recipe_slice():
    res = parse_upload("slice.json", json.dumps({"recipes": [{"title": "Solo"}]}).encode())
    assert res["format"] == "latablee-export"
    assert len(res["recipes"]) == 1


def test_bare_export_dedupes_and_counts_skips():
    payload = _export_payload()
    payload["recipes"].append({"title": "CHILI"})  # dup by casefold
    res = parse_upload("export.json", json.dumps(payload).encode())
    assert len(res["recipes"]) == 2
    assert res["skipped"] == 1


def test_bare_export_empty_recipes_raises():
    try:
        parse_upload("export.json", json.dumps({"recipes": []}).encode())
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "no recipes" in str(e).lower()


def test_schema_org_single_recipe_json_still_works():
    # pre-existing behavior must not regress: a single schema.org recipe object file
    item = {"@type": "Recipe", "name": "Pancakes", "recipeIngredient": ["flour", "milk"],
            "recipeInstructions": [{"text": "mix"}]}
    res = parse_upload("pancakes.json", json.dumps(item).encode())
    assert res["format"] == "json-file"
    assert res["recipes"][0]["title"] == "Pancakes"

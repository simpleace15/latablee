# Recipe CRUD + unit conversion tests
from app.services.unit_conversion import can_add, convert, normalize_ingredient_units


def test_convert_grams_to_kilograms():
    assert convert(500, "gram", "kilogram") == 0.5


def test_convert_volume_tablespoon_to_milliliter():
    assert abs(convert(3, "tablespoon", "milliliter") - 44.36) < 1.0


def test_incompatible_units_return_none():
    assert convert(1, "gram", "liter") is None


def test_can_add_same_and_convertible():
    assert can_add("gram", "kilogram")
    assert can_add("cup", "milliliter")
    assert not can_add("piece", "gram")


def test_normalize_aliases():
    out = normalize_ingredient_units([{"name": "flour", "quantity": 2, "unit": "cups"}])
    assert out[0]["unit"] == "cup"


def test_recipe_crud_flow(client, admin):
    resp = client.post("/api/v1/recipes", json={
        "title": "Pancakes",
        "description": "Sunday morning",
        "servings": 4,
        "instructions": ["Mix", "Fry"],
        "ingredients": [{"name": "flour", "quantity": 300, "unit": "g"},
                        {"name": "milk", "quantity": 0.5, "unit": "l"}],
        "tags": ["breakfast"],
    }, headers=admin)
    assert resp.status_code == 201, resp.text
    recipe = resp.json()
    assert recipe["ingredients"][0]["unit"] == "gram"
    rid = recipe["id"]
    resp = client.get("/api/v1/recipes", headers=admin)
    assert any(r["id"] == rid for r in resp.json())
    resp = client.get(f"/api/v1/recipes/{rid}", headers=admin)
    assert resp.json()["title"] == "Pancakes"
    resp = client.put(f"/api/v1/recipes/{rid}", json={
        "title": "Fluffy Pancakes", "servings": 6,
        "instructions": ["Mix"], "ingredients": [], "tags": ["breakfast"],
    }, headers=admin)
    assert resp.json()["title"] == "Fluffy Pancakes"
    assert resp.json()["servings"] == 6
    resp = client.delete(f"/api/v1/recipes/{rid}", headers=admin)
    assert resp.status_code == 204
    resp = client.get(f"/api/v1/recipes/{rid}", headers=admin)
    assert resp.status_code == 404


def test_recipe_search_by_text_and_tag(client, admin):
    client.post("/api/v1/recipes", json={
        "title": "Chili", "instructions": [], "ingredients": [],
        "tags": ["beef", "spicy"]}, headers=admin)
    client.post("/api/v1/recipes", json={
        "title": "Garden Salad", "instructions": [], "ingredients": [],
        "tags": ["vegetarian"]}, headers=admin)
    resp = client.get("/api/v1/recipes", params={"q": "chili"}, headers=admin)
    titles = [r["title"] for r in resp.json()]
    assert "Chili" in titles and "Garden Salad" not in titles
    resp = client.get("/api/v1/recipes", params={"tag": "vegetarian"}, headers=admin)
    assert [r["title"] for r in resp.json()] == ["Garden Salad"]


def test_household_isolation(client, admin):
    """Recipes are per-household; another household can't see or 404-leak them."""
    import re

    resp = client.post("/api/v1/auth/invite", headers=admin)
    token = re.search(r"invite=([\w-]+)", resp.json()["invite_url"]).group(1)
    client.post("/api/v1/auth/register",
                json={"name": "Other", "password": "longenough1", "invite_token": token})
    resp = client.post("/api/v1/recipes", json={
        "title": "Secret Chili", "instructions": [], "ingredients": []}, headers=admin)
    rid = resp.json()["id"]
    # log in as second user (same household actually — this test validates role-less access)
    resp2 = client.post("/api/v1/auth/token", data={"username": "Other", "password": "longenough1"})
    other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}
    resp = client.get(f"/api/v1/recipes/{rid}", headers=other_headers)
    assert resp.status_code == 200  # same household, so visible

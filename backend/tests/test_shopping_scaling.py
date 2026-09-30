# Servings scaling: planned headcount ÷ recipe servings scales shopping-list quantities.
from fastapi.testclient import TestClient


def _admin(client: TestClient):
    r = client.post("/api/v1/auth/register", json={"name": "Chef", "password": "hunter2hunter"})
    tok = r.json()["token"]
    client.post("/api/v1/household/onboard", json={
        "name": "Home", "timezone": "America/Denver", "dietary_preferences": {},
        "allergies": [], "dislikes": [], "favorites": [], "things_to_remember": "",
    }, headers={"Authorization": f"Bearer {tok}"})
    return tok


def _mk(client: TestClient, tok: str, title: str, ings: list[dict], **kw) -> dict:
    r = client.post("/api/v1/recipes", headers={"Authorization": f"Bearer {tok}"},
                    json={"title": title, "ingredients": ings, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _list(client: TestClient, tok: str) -> int:
    r = client.get("/api/v1/lists", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    lists = r.json()
    if lists:
        return lists[0]["id"]
    r = client.post("/api/v1/lists", json={"name": "Groceries"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_scale_quantity_snaps():
    from app.services.unit_conversion import scale_quantity

    assert scale_quantity(4.0, 1.0) == 4.0  # passthrough
    assert scale_quantity(4.0, 0.5) == 2.0
    assert scale_quantity(2.0, 1.5) == 3.0
    assert scale_quantity(1.0, 0.33) == 0.25  # snap to quarter under 10
    assert scale_quantity(30.0, 0.5) == 15.0
    assert scale_quantity(None, 0.5) is None


def test_add_recipe_to_list_scales_for_servings(client: TestClient):
    tok = _admin(client)
    hdrs = {"Authorization": f"Bearer {tok}"}
    rec = _mk(client, tok, "Stew", [
        {"name": "beef", "quantity": 2, "unit": "pound"},
        {"name": "carrots", "quantity": 4, "unit": "piece"},
        {"name": "salt", "quantity": None, "unit": None},  # unquantified stays
    ], servings=4)
    lst = _list(client, tok)
    # cook for 2 → half quantities
    r = client.post(f"/api/v1/lists/{lst}/add-recipe/{rec['id']}?servings=2", headers=hdrs)
    assert r.status_code == 200, r.text
    items = {i["name"]: i for i in r.json()["items"]}
    assert items["beef"]["quantity"] == 1.0
    assert items["carrots"]["quantity"] == 2.0
    assert items["salt"]["quantity"] is None
    # cook for 5 → 2.5x
    r = client.post(f"/api/v1/lists/{lst}/add-recipe/{rec['id']}?servings=5", headers=hdrs)
    items = {i["name"]: i for i in r.json()["items"]}
    assert items["beef"]["quantity"] == 3.5  # 1.0 + (2 * 1.25 = 2.5) consolidated
    assert items["carrots"]["quantity"] == 7.0  # 2 + 5 → consolidate
    # servings omitted → recipe default, no change
    r = client.post(f"/api/v1/lists/{lst}/add-recipe/{rec['id']}", headers=hdrs)
    items = {i["name"]: i for i in r.json()["items"]}
    assert items["beef"]["quantity"] == 5.5  # +2 unscaled


def test_generate_from_plan_uses_entry_servings(client: TestClient):
    tok = _admin(client)
    hdrs = {"Authorization": f"Bearer {tok}"}
    rec = _mk(client, tok, "Pasta", [
        {"name": "pasta", "quantity": 16, "unit": "ounce"},
        {"name": "garlic", "quantity": 3, "unit": "clove"},
    ], servings=8)
    today = client.get("/api/v1/plan?days=1", headers=hdrs).json()["start"]
    # plan it for 4 people → half quantities
    r = client.post("/api/v1/plan", json={"date": today, "slot": "dinner",
                                          "recipe_id": rec["id"], "servings": 4}, headers=hdrs)
    assert r.status_code == 201, r.text
    lst = _list(client, tok)
    r = client.post(f"/api/v1/lists/{lst}/generate-from-plan?days=7", headers=hdrs)
    assert r.status_code == 200, r.text
    items = {i["name"]: i for i in r.json()["items"]}
    assert items["pasta"]["quantity"] == 8.0
    assert items["garlic"]["quantity"] == 1.5
    # entry with default servings (None) stays unscaled
    from datetime import date as _d
    from datetime import timedelta as _td
    tomorrow = (_d.fromisoformat(today) + _td(days=1)).isoformat()
    r = client.post("/api/v1/plan", json={"date": tomorrow, "slot": "dinner",
                                          "recipe_id": rec["id"]}, headers=hdrs)
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/lists/{lst}/generate-from-plan?days=7", headers=hdrs)
    items = {i["name"]: i for i in r.json()["items"]}
    # generation is additive (same as add-recipe stacking): entry1 re-added (+8) + entry2 unscaled (+16)
    assert items["pasta"]["quantity"] == 32.0

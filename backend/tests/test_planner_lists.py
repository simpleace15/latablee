# Planner + lists + consolidation tests
from datetime import date, timedelta


def test_plan_add_query_delete(client, admin):
    rid = client.post("/api/v1/recipes", json={
        "title": "Tacos", "instructions": [], "ingredients": []}, headers=admin).json()["id"]
    wed = date.today() + timedelta(days=2)
    resp = client.post("/api/v1/plan", json={
        "date": wed.isoformat(), "slot": "dinner", "recipe_id": rid}, headers=admin)
    assert resp.status_code == 201, resp.text
    resp = client.get("/api/v1/plan", headers=admin)
    entries = resp.json()["entries"]
    assert any(e["recipe_title"] == "Tacos" for e in entries)
    eid = entries[0]["id"]
    resp = client.delete(f"/api/v1/plan/{eid}", headers=admin)
    assert resp.status_code == 204
    resp = client.get("/api/v1/plan", headers=admin)
    assert resp.json()["entries"] == []


def test_plan_rejects_bad_slot(client, admin):
    resp = client.post("/api/v1/plan", json={
        "date": date.today().isoformat(), "slot": "brunch"}, headers=admin)
    assert resp.status_code == 422


def test_list_add_check_remove(client, admin):
    lid = client.post("/api/v1/lists", json={"name": "Groceries"}, headers=admin).json()["id"]
    resp = client.post(f"/api/v1/lists/{lid}/items", json={"name": "Milk"}, headers=admin)
    assert resp.status_code == 201
    iid = resp.json()["id"]
    resp = client.patch(f"/api/v1/lists/{lid}/items/{iid}", json={"done": True}, headers=admin)
    assert resp.json()["done"] is True
    resp = client.delete(f"/api/v1/lists/{lid}/items/{iid}", headers=admin)
    assert resp.status_code == 204


def test_consolidation_merges_convertible_units(client, admin):
    lid = client.post("/api/v1/lists", json={"name": "Groceries"}, headers=admin).json()["id"]
    client.post(f"/api/v1/lists/{lid}/items", json={"name": "flour", "quantity": 500, "unit": "gram"},
                headers=admin)
    # 1 kg of flour merges into the 500 g row -> 1500 g
    client.post(f"/api/v1/lists/{lid}/items", json={"name": "flour", "quantity": 1, "unit": "kg"},
                headers=admin)
    items = client.get(f"/api/v1/lists/{lid}", headers=admin).json()["items"]
    flour = [i for i in items if i["name"] == "flour"]
    assert len(flour) == 1
    assert flour[0]["quantity"] == 1500 and flour[0]["unit"] == "gram"


def test_generate_from_plan(client, admin, household_id):
    rid = client.post("/api/v1/recipes", json={
        "title": "Pasta", "instructions": [],
        "ingredients": [{"name": "spaghetti", "quantity": 400, "unit": "gram"}],
    }, headers=admin).json()["id"]
    client.post("/api/v1/plan", json={
        "date": date.today().isoformat(), "slot": "dinner", "recipe_id": rid}, headers=admin)
    lid = client.post("/api/v1/lists", json={"name": "Groceries"}, headers=admin).json()["id"]
    resp = client.post(f"/api/v1/lists/{lid}/generate-from-plan", headers=admin)
    items = resp.json()["items"]
    assert any(i["name"] == "spaghetti" and i["quantity"] == 400 for i in items)

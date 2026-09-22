"""Favorites, one-click add-recipe-to-list (stacking + attribution), LLM refill-week, voice refill."""
import json

from fastapi.testclient import TestClient


def _admin(client: TestClient):
    r = client.post("/api/v1/auth/register", json={"name": "Chef", "password": "hunter2hunter"})
    tok = r.json()["token"]
    client.post("/api/v1/household/onboard", json={
        "name": "Home", "timezone": "America/Denver", "dietary_preferences": {},
        "allergies": ["shellfish"], "dislikes": [], "favorites": [], "things_to_remember": "",
    }, headers={"Authorization": f"Bearer {tok}"})
    return tok


def _mk(client: TestClient, tok: str, title: str, ings: list[dict], **kw) -> dict:
    r = client.post("/api/v1/recipes", headers={"Authorization": f"Bearer {tok}"},
                    json={"title": title, "ingredients": ings, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_favorite_toggle_and_filter(client: TestClient):
    tok = _admin(client)
    hdrs = {"Authorization": f"Bearer {tok}"}
    rec = _mk(client, tok, "Chili", [{"name": "beans", "quantity": 2, "unit": "cup"}])
    assert rec["is_favorite"] is False
    r = client.put(f"/api/v1/recipes/{rec['id']}/favorite?favorite=true", headers=hdrs)
    assert r.status_code == 200 and r.json()["is_favorite"] is True
    assert client.get("/api/v1/recipes?favorite=1", headers=hdrs).json()[0]["title"] == "Chili"
    assert client.get("/api/v1/recipes", headers=hdrs).json()[0]["is_favorite"] is True
    # unheart
    client.put(f"/api/v1/recipes/{rec['id']}/favorite?favorite=false", headers=hdrs)
    assert client.get("/api/v1/recipes?favorite=1", headers=hdrs).json() == []


def test_add_recipe_to_list_stacks_and_attributes(client: TestClient):
    tok = _admin(client)
    hdrs = {"Authorization": f"Bearer {tok}"}
    lst = client.post("/api/v1/lists", headers=hdrs, json={"name": "Groceries"}).json()

    # two recipes both using bread in compatible units: 0.5 loaf each -> 1 loaf total
    r1 = _mk(client, tok, "Toast Night", [{"name": "bread", "quantity": 0.5, "unit": "loaf"}])
    r2 = _mk(client, tok, "Sandwiches", [{"name": "BREAD", "quantity": 0.5, "unit": "loaf"}])
    for rid in (r1["id"], r2["id"]):
        res = client.post(f"/api/v1/lists/{lst['id']}/add-recipe/{rid}", headers=hdrs)
        assert res.status_code == 200, res.text
    items = client.get(f"/api/v1/lists/{lst['id']}", headers=hdrs).json()["items"]
    breads = [i for i in items if i["name"].lower() == "bread"]
    assert len(breads) == 1, "should stack into one line, not two"
    assert breads[0]["quantity"] == 1.0
    assert sorted(breads[0]["from_recipe_ids"]) == sorted([r1["id"], r2["id"]])


def test_refill_week_books_from_book_and_proposes_new(client: TestClient, monkeypatch):
    tok = _admin(client)
    hdrs = {"Authorization": f"Bearer {tok}"}
    book = _mk(client, tok, "Tacos", [{"name": "tortillas", "quantity": 8, "unit": "piece"}])
    client.put(f"/api/v1/recipes/{book['id']}/favorite?favorite=true", headers=hdrs)

    fake_reply = json.dumps({"picks": [
        {"date": "TODAY", "slot": "dinner", "title": "Tacos", "why": "a favorite"},
        {"date": "TOMORROW", "slot": "dinner", "title": "Miso Salmon", "why": "new",
         "recipe": {"title": "Miso Salmon", "servings": 2, "ingredients": [
             {"name": "salmon", "quantity": 1, "unit": "pound"}],
             "instructions": ["Broil."], "tags": ["fish"]}},
    ]})
    import app.services.llm_client as lc

    monkeypatch.setattr(lc, "llm_configured", lambda: True)

    def fake_chat(prompt, json_mode=False):
        return fake_reply.replace("TODAY", _today()).replace(
            "TOMORROW", _today(+1))

    monkeypatch.setattr(lc, "chat", fake_chat)

    res = client.post("/api/v1/llm/refill-week", headers=hdrs, json={"days": 7, "slots": ["dinner"]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["filled"]) == 1 and body["filled"][0]["title"] == "Tacos"
    assert len(body["proposals"]) == 1 and body["proposals"][0]["title"] == "Miso Salmon"

    # save the proposal → lands in book AND gets planned
    prop = body["proposals"][0]
    saved = client.post("/api/v1/llm/save-proposal", headers=hdrs, json={
        "recipe": prop_recipe(prop), "date": prop["date"], "slot": prop["slot"]})
    assert saved.status_code == 200, saved.text
    assert saved.json()["planned"] is True
    titles = [r["title"] for r in client.get("/api/v1/recipes", headers=hdrs).json()]
    assert "Miso Salmon" in titles


def prop_recipe(prop: dict) -> dict:
    return prop["recipe"]


def _today(offset: int = 0) -> str:
    import datetime
    return (datetime.date.today() + datetime.timedelta(days=offset)).isoformat()


def test_voice_refill_fast_path(client: TestClient, monkeypatch):
    tok = _admin(client)
    import app.services.llm_client as lc
    monkeypatch.setattr(lc, "llm_configured", lambda: True)
    monkeypatch.setattr(lc, "chat", lambda prompt, json_mode=False: json.dumps({"picks": []})
                        if "empty slots" in prompt.lower() else json.dumps({"intent": "refill_week"}))
    r = client.post("/api/v1/voice/command", headers={"Authorization": f"Bearer {tok}"},
                    json={"transcript": "latablee refill my week"})
    assert r.status_code == 200, r.text
    assert "refill" in r.json()["reply"].lower() or "full" in r.json()["reply"].lower() or "couldn" in r.json()["reply"].lower()

# URL import against fixture HTML (no live sites), voice command + LLM tests.
# LLM tests use a mock OpenAI-compatible server (httpx MockTransport-style fake).
import json
from datetime import date
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "recipe_page.html"


@pytest.fixture()
def recipe_html() -> str:
    return FIXTURE.read_text()


def test_url_import_parses_json_ld(client, admin, recipe_html, monkeypatch):

    from app.services import recipe_url_import as mod

    def fake_get(url, **kwargs):
        class R:
            status_code = 200
            text = recipe_html

            def raise_for_status(self):
                pass

        class Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def get(self, url, **kw):
                return R()

        return Ctx()

    monkeypatch.setattr(mod.httpx, "Client", lambda **kw: fake_get(None))
    resp = client.post("/api/v1/import/url", json={"url": "https://example.com/recipe"},
                       headers=admin)
    assert resp.status_code == 201, resp.text
    parsed = resp.json()["parsed"]
    assert parsed["title"] == "Classic Pancakes"
    assert parsed["servings"] == 4
    assert parsed["prep_minutes"] == 15
    assert any("flour" in i["name"] for i in parsed["ingredients"])
    assert parsed["ingredients"][0]["quantity"] == 1.5 or parsed["ingredients"][0]["quantity"] == 1


def test_photo_import_requires_llm(client, admin):
    resp = client.post("/api/v1/import/photo",
                       files={"file": ("page.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
                       headers=admin)
    assert resp.status_code == 409  # no LLM configured -> hidden/409 with hint


def _mock_llm(monkeypatch, response_text):
    from app.services import llm_client as mod

    monkeypatch.setattr(mod, "chat", lambda *a, **kw: response_text)
    monkeypatch.setattr(mod, "llm_configured", lambda: True)


def test_voice_add_to_list_without_llm(client, admin):
    resp = client.post("/api/v1/voice/command", json={
        "transcript": "LaTablée, add milk to my shopping list"}, headers=admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "milk" in body["reply"].lower()
    assert body["actions"][0]["type"] == "add_to_list"


def test_voice_wake_word_variants(client, admin):
    lid = client.post("/api/v1/lists", json={"name": "Groceries"}, headers=admin).json()["id"]
    for transcript in ("la table add eggs to my list", "latable add bread to the shopping list"):
        client.post("/api/v1/voice/command", json={"transcript": transcript}, headers=admin)
    items = client.get(f"/api/v1/lists/{lid}", headers=admin).json()["items"]
    names = {i["name"] for i in items}
    assert {"eggs", "bread"} <= names


def test_voice_what_is_for_dinner(client, admin):
    # All dates flow through the HOUSEHOLD clock (the brief: "tonight" resolves
    # in the household timezone, not the server's UTC date). Voice itself does
    # the planning, so test process vs container tz can never disagree.
    resp = client.post("/api/v1/voice/command", json={
        "transcript": "plan Chili for dinner tonight"}, headers=admin)
    assert resp.status_code == 200, resp.text
    reply = resp.json()["reply"]
    assert "Chili" in reply
    assert "tonight" in reply  # planned for the household's today

    # now the query answers with what we just planned
    resp = client.post("/api/v1/voice/command", json={
        "transcript": "what's for dinner tonight"}, headers=admin)
    assert resp.status_code == 200, resp.text
    assert "Chili" in resp.json()["reply"]



def test_voice_plan_meal_with_llm(client, admin, monkeypatch):
    _mock_llm(monkeypatch, json.dumps({
        "intent": "plan_meal", "title": "tacos", "date_phrase": "wednesday", "slot": "dinner"}))
    resp = client.post("/api/v1/voice/command", json={
        "transcript": "add tacos for dinner wednesday"}, headers=admin)
    assert resp.status_code == 200, resp.text
    assert "tacos" in resp.json()["reply"].lower()


def test_voice_unknown_needs_llm(client, admin):
    resp = client.post("/api/v1/voice/command", json={
        "transcript": "tell me a joke"}, headers=admin)
    assert resp.status_code == 409  # freeform needs an LLM; graceful, not a crash


def test_llm_suggest_meals_mock(client, admin, monkeypatch):
    _mock_llm(monkeypatch, json.dumps({"suggestions": [
        {"title": "Lentil Soup", "why": "uses pantry", "uses_pantry": True}]}))
    resp = client.post("/api/v1/llm/suggest-meals", json={}, headers=admin)
    assert resp.status_code == 200
    assert "Lentil Soup" in resp.text


def test_llm_generate_recipe_mock(client, admin, monkeypatch):
    _mock_llm(monkeypatch, json.dumps({
        "title": "Skillet Gnocchi", "servings": 2,
        "ingredients": [{"name": "gnocchi", "quantity": 500, "unit": "g"}],
        "instructions": ["Fry"]}))
    resp = client.post("/api/v1/llm/generate-recipe",
                       json={"prompt": "something with gnocchi"}, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["parsed"]["title"] == "Skillet Gnocchi"


def test_llm_endpoints_409_without_config(client, admin, monkeypatch):
    from app.services import llm_client as mod

    monkeypatch.setattr(mod, "llm_configured", lambda: False)
    resp = client.post("/api/v1/llm/suggest-meals", json={}, headers=admin)
    assert resp.status_code == 409
    resp = client.post("/api/v1/llm/generate-recipe", json={}, headers=admin)
    assert resp.status_code == 409


def test_events_log(client, admin):
    rid = client.post("/api/v1/recipes", json={
        "title": "X", "instructions": [], "ingredients": []}, headers=admin).json()["id"]
    client.post("/api/v1/plan", json={
        "date": date.today().isoformat(), "slot": "dinner", "recipe_id": rid}, headers=admin)
    # events endpoint lives at /api/v1/events (integration surface for repo 2)
    resp = client.get("/api/v1/events", headers=admin)
    assert resp.status_code == 200
    assert any(e["event"] == "meal_plan_updated" for e in resp.json()["events"])

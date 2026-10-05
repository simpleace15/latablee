# Discovery (LLM proposes new dishes not in the book) + ICS calendar feed.
import json


def test_discover_filters_existing_titles(client, admin, monkeypatch):
    from app.services import llm_client as mod

    # give the household one existing recipe so the dup filter has something to hit
    made = client.post("/api/v1/recipes", headers=admin, json={
        "title": "Chili", "instructions": ["Brown", "Simmer"],
        "ingredients": [{"name": "beef", "quantity": 1, "unit": "lb"}],
    })
    assert made.status_code == 201, made.text

    monkeypatch.setattr(mod, "llm_configured", lambda: True)
    monkeypatch.setattr(mod, "chat", lambda prompt, json_mode=False, image_b64=None: json.dumps({
        "ideas": [
            {"title": "Chili", "description": "dup"},          # already in book → filtered
            {"title": "Pad Thai", "cuisine": "Thai", "why": "fresh", "servings": 4,
             "ingredients": [{"name": "rice noodles", "quantity": 300, "unit": "g"}],
             "instructions": ["Soak", "Stir-fry"]},
        ],
    }))
    res = client.post("/api/v1/llm/discover", headers=admin, json={"count": 2})
    assert res.status_code == 200, res.text
    ideas = res.json()["ideas"]
    assert [i["title"] for i in ideas] == ["Pad Thai"]
    assert ideas[0]["ingredients"][0]["unit"]  # normalized to a real unit


def test_discover_requires_llm(client, admin, monkeypatch):
    from app.services import llm_client as mod

    monkeypatch.setattr(mod, "llm_configured", lambda: False)
    res = client.post("/api/v1/llm/discover", headers=admin, json={})
    assert res.status_code == 409


def test_calendar_ics_roundtrip(client, admin):
    from datetime import date, timedelta

    # The feed only includes events from today forward; use a future date
    # so this test can't time-bomb (a hardcoded date ages into the past).
    planned = date.today() + timedelta(days=7)
    planned_iso = planned.isoformat()
    planned_compact = planned.strftime("%Y%m%d")

    # plan a meal, mint a device token, fetch the feed
    client.post("/api/v1/recipes", headers=admin, json={
        "title": "Chili", "instructions": ["Brown", "Simmer"],
        "ingredients": [{"name": "beef", "quantity": 1, "unit": "lb"}],
    })
    recipes = client.get("/api/v1/recipes", headers=admin).json()
    r = client.post("/api/v1/plan", headers=admin, json={
        "date": planned_iso, "slot": "dinner", "recipe_id": recipes[0]["id"],
    })
    assert r.status_code == 201, r.text
    tok = client.post("/api/v1/tokens", headers=admin, json={"name": "ics-test"}).json()["token"]
    res = client.get(f"/api/v1/calendar?token={tok}")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/calendar")
    body = res.text
    assert "BEGIN:VCALENDAR" in body and "END:VCALENDAR" in body
    assert "SUMMARY:Dinner:" in body
    # date line for the planned day
    assert f"DTSTART;VALUE=DATE:{planned_compact}" in body


def test_calendar_ics_bad_token(client, admin):
    res = client.get("/api/v1/calendar?token=lat_deadbeef")
    assert res.status_code == 401


def test_ics_line_folding():
    from app.api.v1.calendar import _fold

    long = "SUMMARY:" + "x" * 100
    folded = _fold(long)
    for line in folded.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75

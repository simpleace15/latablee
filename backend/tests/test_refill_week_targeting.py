# Refill-week: week targeting (start_date), regenerate (replace) — "weeks in advance show
# full" regression. LLM chat is mocked; only orchestration is under test.
import json

import pytest


@pytest.fixture()
def llm_ok(monkeypatch):
    """chat() returns picks for whatever empty slots the prompt mentions."""
    from app.services import llm_client as mod

    monkeypatch.setattr(mod, "llm_configured", lambda: True)

    def fake_chat(prompt: str, json_mode: bool = False, image_b64=None) -> str:
        import ast as _ast
        import re as _re
        m = _re.search(r"Empty slots: (\[.*?\])(?:\.|$)", prompt, _re.S)
        empty = _ast.literal_eval(m.group(1)) if m else []
        picks = [{"date": d, "slot": sl, "title": "Chili", "why": "test"} for d, sl in empty]
        return json.dumps({"picks": picks})

    monkeypatch.setattr(mod, "chat", fake_chat)


@pytest.fixture()
def chili(client, admin):
    r = client.post("/api/v1/recipes", headers=admin,
                    json={"title": "Chili", "ingredients": [], "instructions": []})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def h_today(client, admin):
    """Household-local today (from the API, TZ-correct) — not the VM's date.today()."""
    return client.get("/api/v1/plan?days=1", headers=admin).json()["start"]


def _plan(client, admin):
    return client.get("/api/v1/plan?days=21", headers=admin).json()


def test_refill_targets_viewed_week_not_today(client, admin, llm_ok, chili, h_today):
    """Refill for NEXT week must fill NEXT week, even when this week is empty too."""
    from datetime import date, timedelta
    start = (date.fromisoformat(h_today) + timedelta(days=7)).isoformat()
    res = client.post("/api/v1/llm/refill-week",
                      json={"start_date": start, "days": 7, "slots": ["dinner"]},
                      headers=admin)
    assert res.status_code == 200
    body = res.json()
    assert body["filled"], "next week should be filled"
    assert all(f["date"].startswith(start[:8]) or f["date"] >= start for f in body["filled"])
    # today's week untouched
    plan = _plan(client, admin)
    assert not [e for e in plan["entries"] if e["date"] < start]


def test_future_week_reports_full_only_for_that_week(client, admin, llm_ok, chili, h_today):
    """Fill week+1, then refill week+1 again → 'already full' refers to THAT week;
    week+2 is still refillable (the old code anchored everything to today)."""
    from datetime import date, timedelta
    next_week = (date.fromisoformat(h_today) + timedelta(days=7)).isoformat()
    client.post("/api/v1/llm/refill-week",
                json={"start_date": next_week, "days": 7, "slots": ["dinner"]},
                headers=admin)
    res = client.post("/api/v1/llm/refill-week",
                      json={"start_date": next_week, "days": 7, "slots": ["dinner"]},
                      headers=admin)
    body = res.json()
    assert "full" in body["message"]

    week_after = (date.fromisoformat(h_today) + timedelta(days=14)).isoformat()
    res2 = client.post("/api/v1/llm/refill-week",
                       json={"start_date": week_after, "days": 7, "slots": ["dinner"]},
                       headers=admin)
    assert res2.status_code == 200
    assert res2.json()["filled"], "week after next should be fillable"


def test_regenerate_replaces_existing_week(client, admin, llm_ok, chili, h_today):
    """replace=true clears the week's dinners then re-plans them."""
    from datetime import date, timedelta
    start = (date.fromisoformat(h_today) + timedelta(days=7)).isoformat()
    first = client.post("/api/v1/llm/refill-week",
                        json={"start_date": start, "days": 7, "slots": ["dinner"]},
                        headers=admin).json()
    n_first = len(first["filled"])
    assert n_first > 0

    regen = client.post("/api/v1/llm/refill-week",
                        json={"start_date": start, "days": 7, "slots": ["dinner"], "replace": True},
                        headers=admin)
    assert regen.status_code == 200
    body = regen.json()
    assert len(body["cleared"]) == n_first
    # week still fully planned after regenerate (cleared then refilled)
    plan = client.get(f"/api/v1/plan?start={start}&days=7", headers=admin).json()
    dinners = [e for e in plan["entries"] if e["slot"] == "dinner"]
    assert len(dinners) == n_first


def test_regenerate_keeps_other_slots(client, admin, llm_ok, chili, h_today):
    """replace only clears the targeted slots (dinner), not lunch the user added."""
    from datetime import date, timedelta
    d = date.fromisoformat(h_today) + timedelta(days=7)
    start = d.isoformat()
    client.post("/api/v1/plan", headers=admin,
                json={"date": d.isoformat(), "slot": "lunch", "title_override": "Leftovers"})
    client.post("/api/v1/llm/refill-week",
                json={"start_date": start, "days": 7, "slots": ["dinner"]},
                headers=admin)
    regen = client.post("/api/v1/llm/refill-week",
                        json={"start_date": start, "days": 7, "slots": ["dinner"], "replace": True},
                        headers=admin)
    assert regen.status_code == 200
    plan = client.get(f"/api/v1/plan?start={start}&days=7", headers=admin).json()
    lunches = [e for e in plan["entries"] if e["slot"] == "lunch"]
    assert lunches, "user's lunch entry must survive a dinner-only regenerate"
    assert lunches[0].get("recipe_title") == "Leftovers" or lunches[0].get("title_override") == "Leftovers"

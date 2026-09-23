# Planning rules (free-text variety knobs) flow from household settings into the refill
# prompt, and the anti-repeat context (2 weeks of prior titles) is included.
import json

import pytest


@pytest.fixture()
def llm_ok(monkeypatch):
    """chat() returns picks for whatever empty slots the prompt mentions; records prompts."""
    from app.services import llm_client as mod

    monkeypatch.setattr(mod, "llm_configured", lambda: True)
    seen = {"prompts": []}

    def fake_chat(prompt: str, json_mode: bool = False, image_b64=None) -> str:
        import ast as _ast
        import re as _re
        seen["prompts"].append(prompt)
        m = _re.search(r"Empty slots: (\[.*?\])(?:\.|$)", prompt, _re.S)
        empty = _ast.literal_eval(m.group(1)) if m else []
        picks = [{"date": d, "slot": sl, "title": "Chili", "why": "test"} for d, sl in empty]
        return json.dumps({"picks": picks})

    monkeypatch.setattr(mod, "chat", fake_chat)
    return seen


@pytest.fixture()
def chili(client, admin):
    r = client.post("/api/v1/recipes", headers=admin,
                    json={"title": "Chili", "ingredients": [], "instructions": []})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def h_today(client, admin):
    return client.get("/api/v1/plan?days=1", headers=admin).json()["start"]


def _plan(client, headers, start, days=7):
    return client.get(f"/api/v1/plan?start={start}&days={days}", headers=headers).json()


def test_planning_rules_roundtrip_and_prompt(client, admin, llm_ok, chili, h_today):
    """Rules saved via PATCH /household land in the refill prompt."""
    res = client.patch("/api/v1/household", headers=admin, json={
        "name": "Example Household",
        "planning_rules": ["Only 1 chicken meal per week", "Don't repeat meals from the last 2 weeks"],
    })
    assert res.status_code == 200, res.text
    start = h_today
    res = client.post("/api/v1/llm/refill-week", headers=admin,
                      json={"start_date": start, "days": 7, "slots": ["dinner"]})
    assert res.status_code == 200, res.text
    prompt = llm_ok["prompts"][0]
    assert "Only 1 chicken meal per week" in prompt
    assert "Don't repeat meals from the last 2 weeks" in prompt
    assert "planning_rules" in prompt


def test_recent_history_shared_with_planner(client, admin, llm_ok, chili, h_today):
    """Titles planned in the 2 weeks before the target week are passed as anti-repeat context."""
    from datetime import date, timedelta
    last_week = (date.fromisoformat(h_today) - timedelta(days=7)).isoformat()
    # plan chili for dinner last week via manual entry
    res = client.post("/api/v1/plan", headers=admin,
                      json={"date": last_week, "slot": "dinner", "recipe_id": chili["id"]})
    assert res.status_code in (200, 201), res.text
    next_week = (date.fromisoformat(h_today) + timedelta(days=7)).isoformat()
    res = client.post("/api/v1/llm/refill-week", headers=admin,
                      json={"start_date": next_week, "days": 7, "slots": ["dinner"]})
    assert res.status_code == 200, res.text
    prompt = llm_ok["prompts"][0]
    assert "Chili" in prompt          # recent title surfaced
    assert "recent past" in prompt    # anti-repeat context present

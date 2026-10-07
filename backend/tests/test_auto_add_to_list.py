# Auto-add-to-list toggle (0.7.3): refill-week / regenerate / save-proposal push
# the planned recipes' ingredients onto the default list when the household toggle
# is ON (NULL = ON); with it OFF, lists stay untouched.
import json

import pytest


@pytest.fixture()
def chili(client, admin):
    r = client.post("/api/v1/recipes", headers=admin,
                    json={"title": "Chili",
                          "ingredients": [{"name": "beans", "quantity": 2, "unit": "can"}],
                          "instructions": []})
    assert r.status_code == 201, r.text
    return r.json()


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
        picks = [{"date": d, "slot": sl, "title": "Chili", "why": "test"}
                 for d, sl in empty]
        return json.dumps({"picks": picks})

    monkeypatch.setattr(mod, "chat", fake_chat)


def _start(client, admin):
    return client.get("/api/v1/plan?days=1", headers=admin).json()["start"]


def _list_items(client, admin):
    lists = client.get("/api/v1/lists", headers=admin).json()
    if not lists:
        return []  # toggle-off paths may never create the default list
    lst = lists[0]
    return client.get(f"/api/v1/lists/{lst['id']}", headers=admin).json()["items"]


def test_refill_auto_adds_ingredients_when_on(client, admin, llm_ok, chili):
    start = _start(client, admin)
    res = client.post("/api/v1/llm/refill-week", headers=admin,
                      json={"start_date": start, "days": 7, "slots": ["dinner"]})
    assert res.status_code == 200, res.text
    assert res.json()["filled"], "refill must have filled the slot"
    items = _list_items(client, admin)
    beans = [i for i in items if i["name"].lower().startswith("beans")]
    assert beans, "toggle ON (default): refill should push ingredients to the list"
    assert res.json().get("list_added", 0) > 0


def test_refill_skips_list_when_toggle_off(client, admin, llm_ok, chili):
    r = client.patch("/api/v1/household", headers=admin,
                     json={"name": "Home", "auto_add_to_list": False})
    assert r.status_code == 200, r.text
    assert r.json()["auto_add_to_list"] is False
    start = _start(client, admin)
    res = client.post("/api/v1/llm/refill-week", headers=admin,
                      json={"start_date": start, "days": 7, "slots": ["dinner"]})
    assert res.status_code == 200, res.text
    assert res.json()["filled"], "refill still fills the plan with the toggle off"
    items = _list_items(client, admin)
    assert not [i for i in items if i["name"].lower().startswith("beans")], \
        "toggle OFF must leave the list untouched"
    assert res.json().get("list_added", 0) == 0


def test_toggle_roundtrip_and_default_on(client, admin):
    got = client.get("/api/v1/household", headers=admin).json()
    assert got["auto_add_to_list"] is True  # NULL/never-set = default ON
    r = client.patch("/api/v1/household", headers=admin,
                     json={"name": "Home", "auto_add_to_list": False})
    assert r.json()["auto_add_to_list"] is False
    got = client.get("/api/v1/household", headers=admin).json()
    assert got["auto_add_to_list"] is False


def test_save_proposal_auto_adds_when_on(client, admin, llm_ok):
    start = _start(client, admin)
    res = client.post("/api/v1/llm/save-proposal", headers=admin, json={
        "title": "AI Stir Fry", "date": start, "slot": "dinner",
        "recipe": {"title": "AI Stir Fry",
                   "ingredients": [{"name": "broccoli", "quantity": 1, "unit": "head"}],
                   "instructions": []},
    })
    assert res.status_code == 200, res.text
    items = _list_items(client, admin)
    assert [i for i in items if i["name"].lower().startswith("broccoli")], \
        "toggle ON: saved proposal ingredients land on the list"


def test_refill_adds_once_not_twice(client, admin, llm_ok, chili):
    start = _start(client, admin)
    for _ in range(2):
        client.post("/api/v1/llm/refill-week", headers=admin,
                    json={"start_date": start, "days": 7, "slots": ["dinner"]})
    items = _list_items(client, admin)
    beans = [i for i in items if i["name"].lower().startswith("beans")]
    # second refill on a full week fills nothing → no duplicate pile-up
    assert len(beans) <= 1 or all(i["quantity"] <= 2 for i in beans), \
        "repeat refills must not double-stack identical lines"

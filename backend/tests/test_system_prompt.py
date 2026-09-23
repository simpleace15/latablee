# Custom AI instructions (admin-authored system prompt): stored in settings, rides on every
# chat call as a system message.

import pytest


@pytest.fixture()
def admin_and_client(client):
    r = client.post("/api/v1/auth/register", json={"name": "Admin", "password": "hunter2hunter"})
    token = r.json()["token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_system_prompt_roundtrip(client, admin):
    res = client.put("/api/v1/llm/settings", headers=admin, json={
        "base_url": "http://localhost:9/v1", "api_key": "", "model": "m1",
        "vision_model": "", "system_prompt": "Always prefer budget-friendly meals.",
    })
    assert res.status_code == 200, res.text
    got = client.get("/api/v1/llm/settings", headers=admin).json()
    assert got["system_prompt"] == "Always prefer budget-friendly meals."


def test_system_prompt_sent_on_every_chat(client, admin, monkeypatch):
    import httpx
    from app.services import llm_client as mod

    monkeypatch.setattr(mod, "llm_configured", lambda: True)
    monkeypatch.setattr(mod, "get_llm_settings", lambda: {
        "base_url": "http://mock/v1", "api_key": "", "model": "m",
        "vision_model": "", "system_prompt": "Keep replies short.",
    })
    bodies = []

    def fake_post(self, url, json=None, **kw):
        bodies.append(json)
        return httpx.Response(200, request=httpx.Request("POST", url),
                              json={"choices": [{"message": {"content": "{\"done\": true}"}}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    mod.chat("Fill slots", json_mode=True)
    mod.chat("describe", image_b64="abc")
    for b in bodies:
        roles = [m["role"] for m in b["messages"]]
        assert "system" in roles
        sysmsg = next(m for m in b["messages"] if m["role"] == "system")
        assert sysmsg["content"] == "Keep replies short."

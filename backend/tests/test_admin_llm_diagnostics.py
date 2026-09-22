# Admin LLM diagnostics: ring-buffer log, connection test, timeout setting.
import pytest


def test_llm_log_requires_admin(client, admin):
    r = client.get("/api/v1/admin/llm/log", headers=admin)
    assert r.status_code == 200
    assert "entries" in r.json()
    # non-admin blocked
    client.post("/api/v1/auth/register", json={"name": "Peon", "password": "longenough1"})
    r2 = client.get("/api/v1/admin/llm/log")
    assert r2.status_code in (401, 403)


def test_llm_test_endpoint_reports(monkeypatch, client, admin):
    from app.services import llm_client as mod

    # configured + reachable
    monkeypatch.setattr(mod, "get_llm_settings",
                        lambda: {"base_url": "http://mock/v1", "api_key": "k",
                                 "model": "m1", "vision_model": ""})

    class R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class C:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, *a, **kw):
            return R()

    monkeypatch.setattr(mod.httpx, "Client", lambda **kw: C())
    r = client.post("/api/v1/admin/llm/test", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["reply"] == "ok" and body["seconds"] >= 0

    # logged in the ring buffer
    entries = client.get("/api/v1/admin/llm/log", headers=admin).json()["entries"]
    assert any(e["kind"] == "test" and e["status"] == "ok" for e in entries)


def test_llm_timeout_setting_roundtrip(client, admin):
    r = client.get("/api/v1/admin/llm/timeout", headers=admin)
    assert r.status_code == 200 and r.json()["timeout_seconds"] is None
    r = client.post("/api/v1/admin/llm/timeout", json={"timeout_seconds": 300}, headers=admin)
    assert r.status_code == 200 and r.json()["timeout_seconds"] == 300
    assert client.get("/api/v1/admin/llm/timeout", headers=admin).json()["timeout_seconds"] == 300
    # bounds
    bad = client.post("/api/v1/admin/llm/timeout", json={"timeout_seconds": 2}, headers=admin)
    assert bad.status_code == 422


def test_chat_timeout_error_is_logged(monkeypatch, client, admin):
    """The 'timed out' failure must land in the ring buffer with guidance text."""
    from app.services import llm_client as mod

    monkeypatch.setattr(mod, "get_llm_settings",
                        lambda: {"base_url": "http://mock/v1", "api_key": "",
                                 "model": "slow-model", "vision_model": ""})

    class C:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, *a, **kw):
            raise mod.httpx.ReadTimeout("read timed out")

    monkeypatch.setattr(mod.httpx, "Client", lambda **kw: C())
    with pytest.raises(RuntimeError) as ei:
        mod.chat("hello")
    assert "Timed out" in str(ei.value) and "Settings" in str(ei.value)
    entries = client.get("/api/v1/admin/llm/log", headers=admin).json()["entries"]
    assert entries and entries[0]["status"] == "error" and "Timed out" in entries[0]["error"]

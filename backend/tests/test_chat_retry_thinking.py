# chat() hardening: 5xx retry-once with AI-busy behavior; thinking-token strip + JSON directive.
import json

import httpx
import pytest


class _R:
    def __init__(self, status_code):
        self.status_code = status_code


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"{self.status_code}", request=type("Req", (), {})(),
                                        response=_R(self.status_code))

    def json(self):
        return self._payload


def _settings():
    return {"base_url": "http://x/v1", "api_key": "", "model": "m", "vision_model": "v",
            "system_prompt": ""}


def test_chat_retries_once_on_5xx(monkeypatch):
    from app.services import llm_client as mod

    calls = []
    sleeps = []

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, json=None, headers=None):
            calls.append(1)
            if len(calls) == 1:
                return _Resp(500, {})
            return _Resp(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)
    monkeypatch.setattr(mod, "get_llm_settings", lambda: {
        "base_url": "http://x/v1", "api_key": "", "model": "m", "vision_model": "v",
        "system_prompt": ""})
    monkeypatch.setattr(mod.time, "sleep", lambda s: sleeps.append(s))
    out = mod.chat("hi")
    assert out == "ok"
    assert len(calls) == 2
    assert sleeps == [5]


def test_chat_no_retry_on_4xx(monkeypatch):
    from app.services import llm_client as mod

    calls = []

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, json=None, headers=None):
            calls.append(1)
            return _Resp(422, {})

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)
    monkeypatch.setattr(mod, "get_llm_settings", lambda: {
        "base_url": "http://x/v1", "api_key": "", "model": "m", "vision_model": "v",
        "system_prompt": ""})
    with pytest.raises(RuntimeError):
        mod.chat("hi")
    assert len(calls) == 1  # no retry on 4xx


def test_json_mode_appends_no_thinking_directive(monkeypatch):
    from app.services import llm_client as mod

    captured = {}

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, json=None, headers=None):
            captured.update(json)
            return _Resp(200, {"choices": [{"message": {"content": __import__("json").dumps({"ok": True})}}]})

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)
    monkeypatch.setattr(mod, "get_llm_settings", lambda: {
        "base_url": "http://x/v1", "api_key": "", "model": "m", "vision_model": "v",
        "system_prompt": ""})
    mod.chat("make a recipe", json_mode=True)
    user_text = captured["messages"][-1]["content"]
    assert "No thinking, no preamble — output JSON only." in user_text


def test_extract_json_strips_thinking():
    from app.services.llm_client import _extract_json

    raw = "</think>Let me analyze.\nSome preamble text {\"title\": \"Soup\"}"
    assert json.loads(_extract_json(raw)) == {"title": "Soup"}

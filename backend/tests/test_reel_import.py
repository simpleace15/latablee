# Reel import: URL detection, VTT caption parsing, endpoint flow (pipeline monkeypatched —
# no network in tests).
import json


def test_extract_url_variants():
    from app.services.recipe_reel_import import extract_url

    assert extract_url("check this https://www.tiktok.com/@chef/video/123 ok") == \
        "https://www.tiktok.com/@chef/video/123"
    assert extract_url("https://www.instagram.com/reel/AbCdEf/") .endswith("/")
    assert extract_url("youtu.be/dQw4w9WgXcQ via https://youtu.be/dQw4w9WgXcQ") == \
        "https://youtu.be/dQw4w9WgXcQ"
    assert extract_url("no link here") is None
    assert extract_url("") is None


def test_vtt_to_text_strips_markup_and_dupes(tmp_path):
    from app.services.recipe_reel_import import _vtt_to_text

    vtt = tmp_path / "cap.vtt"
    vtt.write_text(
        "WEBVTT\nKind: captions\n\n00:00:00.000 --> 00:00:02.000\nAdd two cups of flour\n\n"
        "00:00:02.000 --> 00:00:04.000\n<00:00:02.000><c> Add two cups of flour</c>\n\n"
        "00:00:04.000 --> 00:00:06.000\nthen simmer for ten minutes\n",
    )
    text = _vtt_to_text(vtt)
    assert text == "Add two cups of flour then simmer for ten minutes"


def test_reel_endpoint_requires_video_url(client, admin):
    res = client.post("/api/v1/llm/reel", headers=admin, json={"url": "not a link"})
    assert res.status_code == 422
    assert "No supported video URL" in res.json()["detail"]


def _wait_job(client, admin, job_id, timeout=5.0):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(f"/api/v1/llm/reel/{job_id}", headers=admin)
        if res.status_code == 200 and res.json()["done"]:
            return res.json()
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


def test_reel_job_flow(client, admin, monkeypatch):
    """POST returns job_id immediately; polling walks stages; done returns the draft."""
    import app.services.recipe_reel_import as mod

    called = {}

    def fake_import(url: str, progress=None) -> dict:
        called["url"] = url
        if progress:
            progress("downloading", " 42%")
            progress("thinking", "")
        return {
            "title": "Hot Honey Wings", "servings": 4,
            "ingredients": [{"name": "wings", "quantity": 2, "unit": "lb"}],
            "instructions": ["Air fry", "Toss in hot honey"],
            "source_url": url, "source_name": "Tiktok — chef",
        }

    monkeypatch.setattr(mod, "import_from_reel", fake_import)
    res = client.post("/api/v1/llm/reel", headers=admin, json={
        "url": "hey try this https://www.tiktok.com/@chef/video/999",
    })
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["cached"] is False
    job_id = body["job_id"]

    job = _wait_job(client, admin, job_id)
    assert job["stage"] == "done"
    assert job["result"]["title"] == "Hot Honey Wings"
    assert job["result"]["saved"] is False if "saved" in job["result"] else True
    assert job["elapsed_seconds"] >= 0
    assert called["url"] == "https://www.tiktok.com/@chef/video/999"


def test_reel_error_maps_to_job_error(client, admin, monkeypatch):
    import app.services.recipe_reel_import as mod

    monkeypatch.setattr(mod, "import_from_reel",
                        lambda url, progress=None: (_ for _ in ()).throw(ValueError("not_a_recipe")))
    res = client.post("/api/v1/llm/reel", headers=admin, json={"url": "https://youtu.be/x"})
    assert res.status_code == 202
    job = _wait_job(client, admin, res.json()["job_id"])
    assert job["stage"] == "error"
    assert "not_a_recipe" in job["error"]


def test_reel_cached_retry_skips_pipeline(client, admin, monkeypatch):
    """Second submit of the same URL returns the cached draft without re-downloading."""
    import app.services.recipe_reel_import as mod
    from app.services.reel_jobs import cache_put, normalize_url

    calls = []

    def fake_import(url: str, progress=None) -> dict:
        calls.append(url)
        return {"title": "Wings", "ingredients": [], "instructions": []}

    monkeypatch.setattr(mod, "import_from_reel", fake_import)

    # pre-warm the cache directly
    cache_put(normalize_url("https://www.tiktok.com/@chef/video/777"),
              "https://www.tiktok.com/@chef/video/777",
              {"title": "Cached Wings", "ingredients": [], "instructions": []})

    res = client.post("/api/v1/llm/reel", headers=admin, json={
        "url": "https://www.tiktok.com/@chef/video/777"})
    assert res.status_code == 200, res.text
    assert res.json()["cached"] is True
    assert res.json()["parsed"]["title"] == "Cached Wings"
    assert calls == []  # pipeline never ran

    # same URL in share-text noise form hits the same cache entry
    res2 = client.post("/api/v1/llm/reel", headers=admin, json={
        "url": "check it https://vm.tiktok.com/ZMabc/ https://www.tiktok.com/@chef/video/777"})
    assert res2.json()["cached"] is True


def test_normalize_url_variants():
    from app.services.reel_jobs import normalize_url

    assert normalize_url("https://youtu.be/dQw4w9WgXcQ") == "youtube:dqw4w9wgxcq"
    assert normalize_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s") == "youtube:dqw4w9wgxcq"
    assert normalize_url("https://www.tiktok.com/@chef/video/7311111111111111111?is_copy=1") ==         "tiktok:7311111111111111111"
    assert normalize_url("https://www.instagram.com/reel/CxAbCdEfghi/") == "instagram:cxabcdefghi"


def test_reel_latest_reattach(client, admin, monkeypatch):
    import app.services.recipe_reel_import as mod

    monkeypatch.setattr(mod, "import_from_reel",
                        lambda url, progress=None: {"title": "T", "ingredients": [], "instructions": []})
    res = client.post("/api/v1/llm/reel", headers=admin, json={"url": "https://youtu.be/latest123"})
    job_id = res.json()["job_id"]
    _wait_job(client, admin, job_id)
    latest = client.get("/api/v1/llm/reel/latest", headers=admin)
    assert latest.status_code == 200
    assert latest.json()["job_id"] == job_id


def test_chat_accepts_multiple_frames(monkeypatch):
    # multi-image message shape: one text part + N image parts
    from app.services import llm_client as mod

    captured = {}

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"ok": True})}}]}

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, json=None, headers=None):
            captured["messages"] = json["messages"]
            return FakeResp()

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)
    monkeypatch.setattr(mod, "get_llm_settings", lambda: {
        "base_url": "http://x/v1", "api_key": "", "model": "m",
        "vision_model": "v", "system_prompt": ""})
    out = mod.chat("see frames", json_mode=True, image_b64=["AAA", "BBB"])
    assert out == json.dumps({"ok": True})
    user_msg = captured["messages"][-1]
    assert len(user_msg["content"]) == 3
    assert user_msg["content"][0]["type"] == "text"
    assert user_msg["content"][1]["image_url"]["url"].endswith(",AAA")
    assert user_msg["content"][2]["image_url"]["url"].endswith(",BBB")

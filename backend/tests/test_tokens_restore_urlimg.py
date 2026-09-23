"""Device/API tokens (repo-2 auth), backup restore round-trip, URL-import image capture."""
import base64
import io
import zipfile

from fastapi.testclient import TestClient


def _admin(client: TestClient):
    r = client.post("/api/v1/auth/register", json={"name": "Boss", "password": "hunter2hunter"})
    tok = r.json()["token"]
    client.post("/api/v1/household/onboard", json={
        "name": "Home", "timezone": "America/Denver", "dietary_preferences": {},
        "allergies": [], "dislikes": [], "favorites": [], "things_to_remember": "",
    }, headers={"Authorization": f"Bearer {tok}"})
    return tok


PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def test_device_token_auth_roundtrip(client: TestClient):
    hdrs = {"Authorization": f"Bearer {_admin(client)}"}
    created = client.post("/api/v1/tokens", headers=hdrs, json={"name": "Home Assistant"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["token"].startswith("lat_")
    raw = body["token"]

    # device token works on a normal authed endpoint
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert me.status_code == 200 and me.json()["name"] == "Boss"

    # last_used_at tracked; listing shows no raw token
    rows = client.get("/api/v1/tokens", headers=hdrs).json()["tokens"]
    assert rows[0]["revoked"] is False and "token" not in rows[0]
    assert rows[0]["last_used_at"] is not None

    # revoke kills it
    tid = rows[0]["id"]
    assert client.delete(f"/api/v1/tokens/{tid}", headers=hdrs).status_code == 204
    dead = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert dead.status_code == 401

    # JWT still works (fallback not broken)
    assert client.get("/api/v1/auth/me", headers=hdrs).status_code == 200

    # garbage token still 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer lat_deadbeef"}).status_code == 401


def test_backup_restore_roundtrip(client: TestClient):
    hdrs = {"Authorization": f"Bearer {_admin(client)}"}
    # seed: recipe (favorite, with image), plan entry, list with items
    rec = client.post("/api/v1/recipes", headers=hdrs, json={
        "title": "Restore Me", "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
        "tags": ["test"], "source_url": "https://example.com/r", "source_name": "Example",
    }).json()
    client.put(f"/api/v1/recipes/{rec['id']}/favorite?favorite=true", headers=hdrs)
    client.post(f"/api/v1/recipes/{rec['id']}/image", headers=hdrs,
                files={"file": ("x.png", io.BytesIO(PNG_1PX), "image/png")})
    # seed relative to the household's actual today — hardcoded dates rollover at midnight
    today = client.get("/api/v1/plan?days=1", headers=hdrs).json()["start"]
    client.post("/api/v1/plan", headers=hdrs, json={
        "date": today, "slot": "dinner", "recipe_id": rec["id"]})
    lst = client.post("/api/v1/lists", headers=hdrs, json={"name": "Backup test"}).json()
    client.post(f"/api/v1/lists/{lst['id']}/add-recipe/{rec['id']}", headers=hdrs)

    # export archive
    zbytes = client.get("/api/export/archive", headers=hdrs).content
    assert zbytes[:2] == b"PK"

    # mutate state (delete plan entry + recipe) so restore has something to bring back
    plan = client.get("/api/v1/plan", headers=hdrs).json()["entries"]
    for e in plan:
        client.delete(f"/api/v1/plan/{e['id']}", headers=hdrs)
    client.delete(f"/api/v1/recipes/{rec['id']}", headers=hdrs)
    assert client.get("/api/v1/recipes", headers=hdrs).json() == []

    # restore
    res = client.post("/api/v1/export/restore", headers=hdrs,
                      files={"file": ("backup.zip", io.BytesIO(zbytes), "application/zip")})
    assert res.status_code == 200, res.text
    counts = res.json()["restored"]
    assert counts["recipes"] == 1

    # recipe back with favorite + source + image
    recs = client.get("/api/v1/recipes", headers=hdrs).json()
    assert len(recs) == 1
    back = recs[0]
    assert back["is_favorite"] is True
    assert back["source_url"] == "https://example.com/r"
    assert back["image_path"] is not None

    # logins survive: same admin token still valid (public_id preserved)
    assert client.get("/api/v1/auth/me", headers=hdrs).json()["name"] == "Boss"

    # bare JSON export restores too
    jbytes = client.get("/api/v1/export/download-json", headers=hdrs).content
    plan = client.get("/api/v1/plan", headers=hdrs).json()["entries"]
    for e in plan:
        client.delete(f"/api/v1/plan/{e['id']}", headers=hdrs)
    client.delete(f"/api/v1/recipes/{back['id']}", headers=hdrs)
    res2 = client.post("/api/v1/export/restore", headers=hdrs,
                       files={"file": ("export.json", io.BytesIO(jbytes), "application/json")})
    assert res2.status_code == 200 and res2.json()["restored"]["recipes"] == 1

    # non-backup zip rejected cleanly
    junk = io.BytesIO()
    with zipfile.ZipFile(junk, "w") as zf:
        zf.writestr("readme.txt", "hi")
    junk.seek(0)
    bad = client.post("/api/v1/export/restore", headers=hdrs,
                      files={"file": ("junk.zip", junk, "application/zip")})
    assert bad.status_code == 422

    # non-admin blocked
    inv = client.post("/api/v1/auth/invite?expires_days=1", headers=hdrs)
    inv_body = inv.json()
    inv_body = inv.json()
    token_part = inv_body.get("token") or inv_body["invite_url"].split("invite=")[1]
    r2 = client.post("/api/v1/auth/register", json={
        "name": "Plain", "password": "hunter2hunter", "invite_token": token_part})
    user_hdrs = {"Authorization": f"Bearer {r2.json()['token']}"}
    assert client.post("/api/v1/export/restore", headers=user_hdrs,
                       files={"file": ("b.zip", io.BytesIO(zbytes), "application/zip")}).status_code == 403


def test_url_import_fetches_image(client: TestClient, monkeypatch):
    """URL import grabs the schema/og image, and saving the draft stores it locally."""
    html = '''<html><head>
      <meta property="og:image" content="https://example.com/pasta.jpg">
      <script type="application/ld+json">{"@context":"https://schema.org","@type":"Recipe",
        "name":"Test Pasta","recipeIngredient":["2 cups flour"],
        "recipeInstructions":["Boil."],"image":"https://example.com/schema.jpg"}</script>
      </head><body></body></html>'''
    fake_png = PNG_1PX

    class FakeResp:
        status_code = 200
        text = html
        content = fake_png

        def raise_for_status(self):
            pass

    import app.services.recipe_url_import as mod

    calls = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            calls.append(url)
            return FakeResp()

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)

    tok = _admin(client)
    hdrs = {"Authorization": f"Bearer {tok}"}
    parsed = client.post("/api/v1/import/url", headers=hdrs,
                         json={"url": "https://example.com/recipe"}).json()["parsed"]
    # schema.org Recipe.image preferred; og:image is the fallback
    assert calls == ["https://example.com/recipe", "https://example.com/schema.jpg"]
    assert "image_b64" in parsed and parsed["image_b64"]

    # save flow persists the image locally
    saved = client.post("/api/v1/recipes", headers=hdrs, json={
        "title": parsed["title"], "ingredients": parsed["ingredients"],
        "instructions": parsed["instructions"], "image_b64": parsed["image_b64"],
        "source_url": parsed["source_url"], "source_name": parsed["source_name"]})
    assert saved.status_code == 201
    assert saved.json()["image_path"] is not None

    # image fetch failure never blocks import
    class BoomClient(FakeClient):
        def get(self, url):
            calls.append(url)
            if "example.com" in url and not url.endswith(("recipe2", "/recipe")):
                raise ConnectionError("dead")
            return FakeResp()

    monkeypatch.setattr(mod.httpx, "Client", BoomClient)
    ok = client.post("/api/v1/import/url", headers=hdrs,
                     json={"url": "https://example.com/recipe2"})
    assert ok.status_code == 201
    assert "image_b64" not in ok.json()["parsed"]

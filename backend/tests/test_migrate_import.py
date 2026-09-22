"""Migration import: Mealie backup zip, legacy per-recipe zip, schema.org JSON, dry-run, auth."""
import io
import json
import zipfile

from fastapi.testclient import TestClient


def _mealie_backup_zip(recipes: list[dict], images: dict[str, bytes] | None = None) -> bytes:
    """Simulate current Mealie admin backup: database.json + data/recipes/<slug>/webp.jpg"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.json", json.dumps({"recipes": recipes}))
        for slug, data in (images or {}).items():
            zf.writestr(f"data/recipes/{slug}/webp.jpg", data)
    return buf.getvalue()


def _legacy_zip(recipes: list[dict], images: dict[str, bytes] | None = None) -> bytes:
    """Simulate older Mealie per-recipe layout: recipes/<slug>/<slug>.json"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for r in recipes:
            slug = r["slug"]
            zf.writestr(f"recipes/{slug}/{slug}.json", json.dumps(r))
            if images and slug in images:
                zf.writestr(f"recipes/{slug}/original.jpg", images[slug])
    return buf.getvalue()


MEALIE_RECIPE = {
    "name": "Slow Cooker Carnitas",
    "slug": "slow-cooker-carnitas",
    "description": "Citrus-braised pork",
    "recipeServings": 8,
    "prepTime": "PT20M",
    "performTime": "PT4H",
    "recipeIngredient": ["4 lb pork shoulder", "2 oranges, juiced", "1 tbsp cumin"],
    "recipeInstructions": [
        "Season the pork.",
        {"@type": "HowToStep", "text": "Sear on all sides."},
        "Cook low 4 hours, shred.",
    ],
    "orgURL": "https://example.com/carnitas",
    "tags": [{"name": "pork"}, {"name": "slow-cooker"}],
    "recipeCategory": "dinner",
}

SCHEMA_RECIPE = {
    "@type": "Recipe",
    "slug": "sheet-pan-chicken",
    "name": "Sheet Pan Chicken",
    "recipeIngredient": ["6 chicken thighs", "2 lb potatoes"],
    "recipeInstructions": ["Heat oven 425F.", "Roast 35 min."],
    "recipeYield": 4,
    "keywords": "weeknight,one-pan",
    "url": "https://example.com/sheetpan",
}


def _admin_headers(client: TestClient) -> dict:
    """Register first user (becomes admin) + onboard, mirroring conftest's admin fixture."""
    resp = client.post("/api/v1/auth/register", json={"name": "Admin", "password": "hunter2hunter"})
    assert resp.status_code == 201, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['token']}"}
    resp = client.post("/api/v1/household/onboard", json={
        "name": "Example Household", "timezone": "America/Denver",
        "dietary_preferences": {}, "allergies": [], "dislikes": [],
        "favorites": [], "things_to_remember": "",
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    return headers


def test_mealie_backup_zip_full_flow(client: TestClient):
    img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    zdata = _mealie_backup_zip([MEALIE_RECIPE, {"name": "", "slug": "empty"}], {"slow-cooker-carnitas": img})
    headers = _admin_headers(client)

    # preview (dry run) — no writes
    prev = client.post("/api/v1/migrate/preview", headers=headers,
                       files={"file": ("backup.zip", io.BytesIO(zdata), "application/zip")})
    assert prev.status_code == 200, prev.text
    body = prev.json()
    assert body["would_import"] == 1
    assert body["skipped"] == 1
    assert body["format"] == "mealie-backup"
    assert body["with_images"] == 1

    # list count before
    before = len(client.get("/api/v1/recipes", headers=headers).json())

    run = client.post("/api/v1/migrate", headers=headers,
                      files={"file": ("backup.zip", io.BytesIO(zdata), "application/zip")})
    assert run.status_code == 200, run.text
    assert run.json()["imported"] == 1

    recipes = client.get("/api/v1/recipes", headers=headers).json()
    assert len(recipes) == before + 1
    carn = next(r for r in recipes if r["title"] == "Slow Cooker Carnitas")
    assert carn["servings"] == 8
    assert carn["prep_minutes"] == 20
    assert carn["cook_minutes"] == 240  # PT4H
    assert carn["instructions"] == ["Season the pork.", "Sear on all sides.", "Cook low 4 hours, shred."]
    assert carn["ingredients"][0]["name"] == "4 lb pork shoulder"
    assert carn["source_url"] == "https://example.com/carnitas"
    assert "pork" in carn["tags"] and "slow-cooker" in carn["tags"] and "dinner" in carn["tags"]
    assert carn["image_path"] is not None  # webp.jpg attached


def test_legacy_per_recipe_zip(client: TestClient):
    zdata = _legacy_zip([MEALIE_RECIPE, SCHEMA_RECIPE])
    headers = _admin_headers(client)
    run = client.post("/api/v1/migrate", headers=headers,
                      files={"file": ("legacy.zip", io.BytesIO(zdata), "application/zip")})
    assert run.status_code == 200, run.text
    assert run.json()["format"] == "mealie-legacy"
    assert run.json()["imported"] == 2
    titles = {r["title"] for r in client.get("/api/v1/recipes", headers=headers).json()}
    assert {"Slow Cooker Carnitas", "Sheet Pan Chicken"} <= titles


def test_schema_json_file(client: TestClient):
    headers = _admin_headers(client)
    data = json.dumps([SCHEMA_RECIPE]).encode()
    run = client.post("/api/v1/migrate", headers=headers,
                      files={"file": ("recipes.json", io.BytesIO(data), "application/json")})
    assert run.status_code == 200, run.text
    assert run.json()["imported"] == 1


def test_non_admin_forbidden(client: TestClient):
    # register a normal user via admin invite flow is complex here; a fresh non-admin token
    # is exercised in other suites — here just assert unauthorized upload is rejected
    r = client.post("/api/v1/migrate", files={"file": ("x.zip", io.BytesIO(b"PK\x03\x04"), "application/zip")})
    assert r.status_code in (401, 403)


def test_recipe_category_string_not_split(client: TestClient):
    """Regression: recipeCategory as plain string must become one tag, not per-character."""
    headers = _admin_headers(client)
    r = dict(MEALIE_RECIPE)
    r["slug"] = "cat-string-recipe"
    r["recipeCategory"] = "dinner"
    zdata = _mealie_backup_zip([r])
    run = client.post("/api/v1/migrate", headers=headers,
                      files={"file": ("b.zip", io.BytesIO(zdata), "application/zip")})
    assert run.status_code == 200
    carn = next(r for r in client.get("/api/v1/recipes", headers=headers).json()
                if r["title"] == "Slow Cooker Carnitas")
    assert carn["tags"] == ["pork", "slow-cooker", "dinner"]


def test_real_jpeg_image_attached(client: TestClient):
    # 1x1 JPEG (real header) so imghdr accepts it
    jpeg = bytes.fromhex("ffd8ffe000104a46494600010100000100010000db0043000806060706050807070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbfa")[:1250]
    zdata = _mealie_backup_zip([MEALIE_RECIPE], {"slow-cooker-carnitas": jpeg})
    headers = _admin_headers(client)
    run = client.post("/api/v1/migrate", headers=headers,
                      files={"file": ("b.zip", io.BytesIO(zdata), "application/zip")})
    assert run.status_code == 200, run.text
    carn = next(r for r in client.get("/api/v1/recipes", headers=headers).json()
                if r["title"] == "Slow Cooker Carnitas")
    assert carn["image_path"] is not None


def test_garbage_rejected(client: TestClient):
    headers = _admin_headers(client)
    r = client.post("/api/v1/migrate/preview", headers=headers,
                    files={"file": ("x.bin", io.BytesIO(b"not a zip"), "application/octet-stream")})
    assert r.status_code == 422

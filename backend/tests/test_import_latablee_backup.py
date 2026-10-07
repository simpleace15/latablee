# LaTablée backup zip imported through the "Import from Mealie or other apps" card.
# Tyler hit this: download his prod backup → upload → 422 "No recipes found".
# parse_upload must detect our own backup (latablee.db + export.json) and import it.
import io
import json
import zipfile

from app.services.mealie_import import parse_upload


def _zip_with(export_recipes: list[dict], image_files: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("latablee.db", b"fake-db-bytes")  # presence is the format signal
        zf.writestr("export.json", json.dumps({"recipes": export_recipes}))
        for name, data in (image_files or {}).items():
            zf.writestr(f"images/{name}", data)
    return buf.getvalue()


def test_latablee_backup_zip_imports():
    data = _zip_with([
        {"id": 1, "title": "Chili", "description": "red", "servings": 6,
         "instructions": ["brown meat"], "ingredients": [{"name": "beef"}],
         "tags": ["dinner"], "image_path": None, "source_url": None},
        {"id": 2, "title": "Pad See Ew", "servings": 2,
         "instructions": ["soak noodles"], "ingredients": [{"name": "rice noodles"}]},
    ])
    res = parse_upload("latablee-backup-20261007.zip", data)
    assert res["format"] == "latablee-backup"
    assert res["skipped"] == 0
    titles = [r["title"] for r in res["recipes"]]
    assert titles == ["Chili", "Pad See Ew"]
    chili = res["recipes"][0]
    assert chili["ingredients"] == [{"name": "beef"}]
    assert chili["instructions"] == ["brown meat"]
    assert chili["servings"] == 6


def test_latablee_backup_with_images_maps_by_filename():
    png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")  # header suffices for detection
    data = _zip_with(
        [{"title": "Chili", "image_path": "images/recipe-1-abc.png", "ingredients": []}],
        {"recipe-1-abc.png": png + b"\x00"},
    )
    res = parse_upload("backup.zip", data)
    assert res["images"].get("Chili") == png + b"\x00"


def test_latablee_backup_dedupes_titles():
    data = _zip_with([
        {"title": "Chili", "ingredients": []},
        {"title": "chili", "ingredients": []},
    ])
    res = parse_upload("backup.zip", data)
    assert len(res["recipes"]) == 1
    assert res["skipped"] == 1


def test_latablee_backup_empty_recipes_raises():
    data = _zip_with([])
    try:
        parse_upload("backup.zip", data)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "no recipes" in str(e).lower()

# Image storage on the local volume (no CDN/S3). Validated + size-capped.
import imghdr  # noqa: DEP008 (stdlib, fine for v1)
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import IMAGES_DIR, get_settings

ALLOWED = {"jpeg", "png", "webp"}


async def save_recipe_image(recipe_id: int, file: UploadFile) -> Path:
    settings = get_settings()
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "Image too large")
    kind = imghdr.what(None, h=data)
    if kind not in ALLOWED:
        raise HTTPException(415, f"Unsupported image type {kind!r} (jpeg/png/webp only)")
    dest = IMAGES_DIR / f"recipe-{recipe_id}-{uuid.uuid4().hex[:8]}.{kind}"
    dest.write_bytes(data)
    return dest

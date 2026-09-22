# LaTablée FastAPI app — versioned REST API under /api/v1
import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import IMAGES_DIR, STATIC_DIR, ensure_dirs, get_settings
from app.db.engine import create_all

app = FastAPI(
    title="LaTablée",
    description="Self-hosted recipe & meal planning for the whole table.",
    version=get_settings().version,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

ensure_dirs()

# Wait for the DB (docker compose races api vs db on first boot; Postgres
# needs a few seconds to init). Retry up to ~60s, then fail loudly.
logger = logging.getLogger("uvicorn.error")
for _attempt in range(30):
    try:
        create_all()
        break
    except Exception as exc:
        if _attempt == 29:
            raise
        logger.warning("DB not ready (attempt %d/30): %s", _attempt + 1, exc)
        time.sleep(2)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Recipe/user images served from the Docker volume by the app itself (no CDN/S3)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": "LaTablée", "version": get_settings().version}


@app.get("/api/export/archive")
def download_archive():
    """Full backup archive (DB + images). One-click data-out."""
    from app.services.export import build_backup_archive

    path = build_backup_archive()
    return FileResponse(path, filename=path.name, media_type="application/zip")


app.include_router(api_router, prefix=get_settings().api_v1_prefix)

# Single-container mode: serve the built web UI (Next.js static export) from the API.
# Empty LATABLEE_STATIC_DIR (two-container nginx mode) disables it.
# Registered LAST so the catch-all never shadows API routes above.
if STATIC_DIR is not None:
    from fastapi.responses import FileResponse, RedirectResponse

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    @app.get("/", include_in_schema=False)
    def _root() -> RedirectResponse:
        return RedirectResponse(url="/static/index.html")

    # SPA fallback: any non-API GET without a file → the SPA shell (client router takes over)
    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")

# LaTablée FastAPI app — versioned REST API under /api/v1
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import IMAGES_DIR, ensure_dirs, get_settings
from app.db.engine import create_all

app = FastAPI(
    title="LaTablée",
    description="Self-hosted recipe & meal planning for the whole table.",
    version=get_settings().version,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

ensure_dirs()
create_all()

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


# Serve the built frontend (PWA) if present — single-container deploys
FRONTEND_DIST = Path("frontend/dist")
if FRONTEND_DIST.is_dir():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIST / "app"), html=True), name="spa")

app.include_router(api_router, prefix=get_settings().api_v1_prefix)

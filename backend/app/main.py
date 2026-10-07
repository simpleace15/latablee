# LaTablée FastAPI app — versioned REST API under /api/v1
import logging
import time
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import IMAGES_DIR, STATIC_DIR, ensure_dirs, get_settings
from app.db.engine import create_all, get_engine

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


@app.middleware("http")
async def security_headers(request, call_next):
    """Baseline hardening for the single-container app (serves its own UI):
    no-Sniff, frame-deny, referrer policy, and a conservative CSP. API JSON
    responses carry them too — harmless there, protective on the SPA."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
    )
    return response

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


@app.get("/api/export/archive/cron")
def cron_archive(token: str = ""):
    """Scheduled-backup variant of /api/export/archive for cron/User Scripts:
    auth by device token (Settings → Device tokens, `lat_…`) as a QUERY PARAM
    (curl-friendly), returns the zip. Keeps unauthenticated instances from
    leaking data while letting a nightly job fetch a copy with no session."""
    import hashlib

    from sqlmodel import Session, select

    from app.models import ApiToken
    from app.services.export import build_backup_archive

    if not token.startswith("lat_"):
        raise HTTPException(status_code=401, detail="Device token required (Settings → Device tokens)")
    h = hashlib.sha256(token.encode()).hexdigest()
    with Session(get_engine()) as session:
        row = session.exec(select(ApiToken).where(ApiToken.token_hash == h)).first()
        if row is None or row.revoked_at is not None:
            raise HTTPException(status_code=401, detail="Unknown or revoked token")
        row.last_used_at = datetime.now(UTC)
        session.add(row)
        session.commit()
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

    # SPA fallback: non-API GET without a file → the SPA shell (client router takes over).
    # Next.js static export writes directory indexes (settings/index.html, trailingSlash mode),
    # so resolve those too — otherwise /settings (no slash) serves the ROOT index.html and the
    # user sees the Today page under the /settings URL.
    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = candidate / "index.html" if full_path else None
        if index is not None and index.is_file():
            return FileResponse(index)
        return FileResponse(STATIC_DIR / "index.html")

# Export endpoints (JSON export + backup archive also mounted at /api/export/archive)
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.security import require_admin, require_household
from app.models import User
from app.services.export import write_json_export

router = APIRouter()


@router.get("/json")
def export_json_endpoint(user: Annotated[User, Depends(require_household)]) -> dict:
    from app.services.export import export_json

    return export_json()


@router.get("/download-json")
def download_json(user: Annotated[User, Depends(require_household)]):
    path = write_json_export()
    return FileResponse(path, filename=path.name, media_type="application/json")


@router.post("/restore", status_code=200)
async def restore_backup(
    user: Annotated[User, Depends(require_admin)],
    file: UploadFile,
) -> dict:
    """Wipe + restore from a backup archive (zip) or JSON export. Destructive — the
    UI requires confirmation; every existing record (except the calling admin's
    re-imported logins) is replaced by the backup's contents."""
    from app.services.restore import restore_from_archive

    data = await file.read()
    try:
        counts = restore_from_archive(data)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, f"Not a valid LaTablée backup: {exc}") from exc
    return {"restored": counts}

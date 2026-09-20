# Export endpoints (JSON export + backup archive also mounted at /api/export/archive)
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.core.security import require_household
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

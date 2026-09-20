# Run: python -m app  (uvicorn)
import uvicorn

from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.debug and "0.0.0.0" or "0.0.0.0",  # containerized; bind all
        port=8000,
        reload=settings.debug,
    )

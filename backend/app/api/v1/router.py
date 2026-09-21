# Versioned REST API — /api/v1/*
from fastapi import APIRouter

from app.api.v1 import (
                        admin,
                        auth,
                        events,
                        export,
                        household,
                        import_router,
                        lists,
                        llm,
                        planner,
                        recipes,
                        voice,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(household.router, prefix="/household", tags=["household"])
api_router.include_router(recipes.router, prefix="/recipes", tags=["recipes"])
api_router.include_router(planner.router, prefix="/plan", tags=["plan"])
api_router.include_router(lists.router, prefix="/lists", tags=["lists"])
api_router.include_router(import_router.router, prefix="/import", tags=["import"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

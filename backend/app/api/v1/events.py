# Event log for integration clients (repo 2, automations): poll since last id.
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.security import get_current_user
from app.db.engine import get_session
from app.models import User
from app.services.events import events_since

router = APIRouter()


@router.get("")
def get_events(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    rows = events_since(session, after_id, limit)
    return {"events": [
        {"id": e.id, "event": e.event, "payload": e.payload,
         "delivered_at": e.delivered_at.isoformat() if e.delivered_at else None}
        for e in rows
    ]}

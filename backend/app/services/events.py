# Integration events (webhook/event log for repo 2 clients + automations)
from sqlmodel import Session

from app.models import WebhookEvent, utcnow


def record_event(session: Session, event: str, payload: dict) -> None:
    """Append to the event log (committed immediately; callers have finished their writes)."""
    session.add(WebhookEvent(event=event, payload=payload, delivered_at=utcnow()))
    session.commit()


def events_since(session: Session, after_id: int, limit: int = 100) -> list[WebhookEvent]:
    from sqlmodel import select

    return list(session.exec(
        select(WebhookEvent).where(WebhookEvent.id > after_id).order_by(WebhookEvent.id).limit(limit)
    ))

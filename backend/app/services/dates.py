# Household-local date/time resolution.
# The brief requires "tonight"/"Wednesday" to resolve against the household
# timezone — server UTC must never be used as a household-local "today".
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlmodel import Session

from app.models import Household


def _household_tz(session: Session, household_id: int | None) -> ZoneInfo:
    household = session.get(Household, household_id) if household_id else None
    tzname = household.timezone if household else "UTC"
    try:
        return ZoneInfo(tzname)
    except Exception:
        return ZoneInfo("UTC")


def household_now(session: Session, household_id: int | None) -> datetime:
    return datetime.now(_household_tz(session, household_id))


def household_today(session: Session, household_id: int | None) -> date:
    """'Today' as the household experiences it — never the server's UTC date."""
    return household_now(session, household_id).date()

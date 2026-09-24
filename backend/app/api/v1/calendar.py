# ICS calendar feed: /api/calendar.ics?token=lat_... — subscribe from any phone calendar
# (or a Home Assistant calendar card later). Token = existing device token, scoped to the
# household's planned meals.
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sqlmodel import Session, select

from app.core.security import _device_token_user
from app.db.engine import get_engine
from app.models import MealPlanEntry, Recipe
from app.services.dates import household_today

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets are folded with CRLF + single space."""
    out: list[str] = []
    raw = line.encode("utf-8")
    while len(raw) > 73:
        cut = 73
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 char
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = b" " + raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n".join(out)


@router.get("/.ics", include_in_schema=False)
@router.get("")
def calendar_ics(
    token: str = Query(..., description="Device token (lat_…), minted in Settings"),
    days: int = Query(30, ge=1, le=120),
) -> Response:
    with Session(get_engine()) as session:
        user = _device_token_user(token, session)
        if user is None:
            raise HTTPException(401, "Invalid token")
        today = household_today(session, user.household_id)
        end = today + timedelta(days=days)
        rows = session.exec(
            select(MealPlanEntry, Recipe)  # type: ignore[call-overload]
            .join(Recipe, MealPlanEntry.recipe_id == Recipe.id)  # type: ignore[arg-type]
            .where(MealPlanEntry.household_id == user.household_id,
                   MealPlanEntry.planned_date >= today,
                   MealPlanEntry.planned_date < end)
            .order_by(MealPlanEntry.planned_date)
        ).all()
        tzid = "UTC"
        lines = [
            "BEGIN:VCALENDAR", "VERSION:2.0",
            "PRODID:-//LaTablee//Meal Plan//EN", "CALSCALE:GREGORIAN",
            "X-WR-CALNAME:LaTablée meal plan", f"X-WR-TIMEZONE:{tzid}",
        ]
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        for entry, recipe in rows:
            dt = entry.planned_date.strftime("%Y%m%d")
            lines += [
                "BEGIN:VEVENT",
                f"UID:latablee-plan-{entry.id}@localhost",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{dt}",
                f"DTEND;VALUE=DATE:{(entry.planned_date + timedelta(days=1)).strftime('%Y%m%d')}",
                _fold(f"SUMMARY:{entry.slot.title()}: {_ics_escape(recipe.title)}"),
                "CATEGORIES:MEAL",
                "END:VEVENT",
            ]
        lines.append("END:VCALENDAR")
        return Response(
            content="\r\n".join(lines) + "\r\n",
            media_type="text/calendar",
            headers={"Content-Disposition": 'inline; filename="latablee.ics"'},
        )

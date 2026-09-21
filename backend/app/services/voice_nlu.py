# Voice NLU helpers: wake-word stripping, date resolution, rule-based fast path, LLM parse.
# Satellites transcribe "LaTablée" loosely; accept common variants as wake words.
import unicodedata
from datetime import date, timedelta
from typing import Any

from sqlmodel import Session

from app.models import User
from app.services import llm_client

_WAKE_VARIANTS = ("latablee", "la table", "la tablee", "latable", "la tabli",
                  "la tabby", "luh tah blay", "la tableau")


def _norm(text: str) -> str:
    """Lowercase + strip accents so 'LaTablée' -> 'latablee' matches mangled STT output."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)
    )


def llm_available() -> bool:
    return llm_client.llm_configured()


def strip_wake_word(transcript: str, device_hint: str | None = None) -> str:
    t = (transcript or "").strip()
    tn = _norm(t)
    for w in _WAKE_VARIANTS:
        wn = _norm(w)
        if wn and tn.startswith(wn):
            rest = t[len(w):]
            if not rest or rest[0] in " ,.!?" :
                return rest.strip(" ,.!?")
    return t


def resolve_date(phrase: str, session: Session, user: User) -> date:
    """Resolve 'tonight'/'Wednesday' against the household timezone (today)."""
    from app.services.dates import household_today

    now = household_today(session, user.household_id)  # household-local 'today'
    p = phrase.lower().strip()
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if p in ("today", "tonight", "this evening"):
        return now
    if p == "tomorrow":
        return now + timedelta(days=1)
    for i, wd in enumerate(weekdays):
        if wd in p:
            delta = (i - now.weekday()) % 7
            if delta == 0 and ("next" in p):
                delta = 7
            return now + timedelta(days=delta)
    return now


def human_date(d: date, today: date | None = None) -> str:
    """Humanize a planned date. Pass household-local 'today' when available."""
    today = today or date.today()
    if d == today:
        return "tonight"
    if d == today + timedelta(days=1):
        return "tomorrow"
    return d.strftime("%A")


def rule_based_parse(transcript: str) -> dict[str, Any] | None:
    """Deterministic parser for the most common commands (works with no LLM configured)."""
    import re

    t = transcript.lower().strip()
    for prefix in ("add ", "put "):
        if t.startswith(prefix):
            rest = t[len(prefix):]
            m = re.search(r"\s+(?:to|in)\s+(?:(?:my|the|grocery)\s+)?(?:shopping\s+)?list\b", rest)
            if m:
                rest = rest[:m.start()].strip()
                if rest:
                    return {"intent": "add_to_list", "item": rest,
                            "quantity": None, "unit": None}
    m = re.match(r"^plan\s+(?P<title>.+?)\s+for\s+(?P<slot>breakfast|lunch|dinner)"
                 r"(?:\s+(?P<when>tonight|today|tomorrow|next\s+\w+|\w+day))?$", t)
    if m:
        return {"intent": "plan_meal", "title": m.group("title").title(),
                "slot": m.group("slot"),
                "date_phrase": m.group("when") or "today"}
    if (t.startswith("what's for dinner") or t.startswith("whats for dinner")
            or "what is for dinner" in t):
        return {"intent": "query_plan", "date_phrase": "tonight"}
    if re.search(r"refill|fill (?:out )?(?:my |the |this )?week|plan (?:my |the |this )?week", t) \
            and "week" in t:
        return {"intent": "refill_week"}
    return None


def llm_parse(transcript: str, session: Session, household_id: int) -> dict[str, Any]:
    """Freeform fallback: the app's LLM turns the transcript into a structured intent."""

    names = [r.title for r in session.exec(
        select_recipe_stmt(household_id)).all()][:60]
    prompt = (
        "You are the NLU for a household recipe app. Convert the spoken request into JSON. "
        'Allowed intents: {"intent":"add_to_list","item":string,"quantity":number|null,"unit":string|null} '
        '| {"intent":"plan_meal","title":string,"date_phrase":string,"slot":"breakfast"|"lunch"|"dinner"} '
        '| {"intent":"query_plan","date_phrase":string} '
        '| {"intent":"refill_week"} '
        '| {"intent":"unknown","reply":string}. date_phrase is like "tonight", "tomorrow", '
        '"Wednesday", "next Monday". Recipe names for matching: ' + str(names[:40]) + ". "
        f'Request: "{transcript}"'
    )
    import json

    return json.loads(llm_client.chat(prompt, json_mode=True))


def select_recipe_stmt(household_id: int):
    from sqlmodel import select

    from app.models import Recipe

    return select(Recipe).where(Recipe.household_id == household_id)

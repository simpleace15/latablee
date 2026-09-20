# OpenAI-compatible LLM client. Reads env first, then DB Setting rows (admin-editable).
import json
import logging
from typing import Any

import httpx
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.engine import get_engine
from app.models import Setting

logger = logging.getLogger(__name__)


def _db_settings() -> dict[str, Any]:
    try:
        with Session(get_engine()) as session:
            from sqlmodel import col

            rows = session.exec(select(Setting).where(col(Setting.key).like("llm.%"))).all()
            return {r.key.removeprefix("llm."): r.value for r in rows}
    except Exception:  # DB not ready (e.g. tests) — env only
        return {}


def get_llm_settings() -> dict[str, Any]:
    env = get_settings()
    db = _db_settings()
    base_url = db.get("base_url") or env.llm_base_url or ""
    return {
        "base_url": base_url,
        "api_key": db.get("api_key") or env.llm_api_key or "",
        "model": db.get("model") or env.llm_model,
        "vision_model": db.get("vision_model") or env.llm_vision_model or "",
    }


def llm_configured() -> bool:
    return bool(get_llm_settings()["base_url"])


def save_llm_settings(base_url: str, api_key: str, model: str, vision_model: str) -> None:
    with Session(get_engine()) as session:
        for key, value in (("base_url", base_url), ("api_key", api_key), ("model", model),
                           ("vision_model", vision_model)):
            row = session.get(Setting, f"llm.{key}")
            if row is None:
                session.add(Setting(key=f"llm.{key}", value=value))
            else:
                row.value = value
                session.add(row)
        session.commit()


def chat(prompt: str, json_mode: bool = False, image_b64: str | None = None) -> str:
    """One-shot chat completion. Raises on failure so callers can 502 gracefully."""
    s = get_llm_settings()
    if not s["base_url"]:
        raise RuntimeError("LLM not configured")
    url = s["base_url"].rstrip("/") + "/chat/completions"
    content: Any = prompt
    if image_b64:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]
    body: dict[str, Any] = {
        "model": s["vision_model"] if image_b64 and s["vision_model"] else s["model"],
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.4,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {}
    if s["api_key"]:
        headers["Authorization"] = f"Bearer {s['api_key']}"
    with httpx.Client(timeout=60) as client:
        resp = client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    text = data["choices"][0]["message"]["content"]
    if json_mode:
        return _extract_json(text)
    return text


def _extract_json(text: str) -> str:
    """Tolerate models that wrap JSON in prose/code fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        return t[start:end + 1]
    json.loads(t)  # raise if truly invalid
    return t

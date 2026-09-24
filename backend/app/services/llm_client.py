# OpenAI-compatible LLM client. Reads env first, then DB Setting rows (admin-editable).
import json
import logging
import time
from typing import Any

import httpx
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.engine import get_engine
from app.models import Setting

logger = logging.getLogger(__name__)

# Diagnostics ring buffer: last N LLM calls (success + failure) for the admin UI.
# Not a substitute for real logging — a lightweight "what did the AI actually do" view.
LLM_LOG_MAX = 50
_llm_log: list[dict[str, Any]] = []


def _log_call(entry: dict[str, Any]) -> None:
    from datetime import UTC, datetime
    entry["at"] = datetime.now(UTC).isoformat(timespec="seconds")
    _llm_log.append(entry)
    del _llm_log[:-LLM_LOG_MAX]


def get_llm_log() -> list[dict[str, Any]]:
    """Most recent first."""
    return list(reversed(_llm_log))


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
        "system_prompt": db.get("system_prompt") or "",
    }


def llm_configured() -> bool:
    return bool(get_llm_settings()["base_url"])


def save_llm_settings(base_url: str, api_key: str, model: str, vision_model: str,
                      system_prompt: str | None = None) -> None:
    with Session(get_engine()) as session:
        pairs: list[tuple[str, str]] = [("base_url", base_url), ("api_key", api_key),
                                        ("model", model), ("vision_model", vision_model)]
        if system_prompt is not None:
            pairs.append(("system_prompt", system_prompt))
        for key, value in pairs:
            row = session.get(Setting, f"llm.{key}")
            if row is None:
                session.add(Setting(key=f"llm.{key}", value=value))
            else:
                row.value = value
                session.add(row)
        session.commit()


def _llm_timeout() -> httpx.Timeout:
    """Connect 10s, read configurable (default 120s). Local models cold-start slowly:
    a single float timeout makes Ollama loading a big model look like a timeout."""
    db = _db_settings()
    read = float(db.get("timeout_seconds") or get_settings().llm_timeout_seconds or 120)
    return httpx.Timeout(connect=10.0, read=read, write=30.0, pool=10.0)


def test_llm_connection() -> dict[str, Any]:
    """Admin diagnostics: ping /models + a 1-token chat, measure latency."""
    s = get_llm_settings()
    if not s["base_url"]:
        return {"ok": False, "error": "No AI endpoint configured"}
    url = s["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {s['api_key']}"} if s["api_key"] else {}
    body = {"model": s["model"], "messages": [{"role": "user", "content": "Reply with the word: ok"}],
            "max_tokens": 5, "temperature": 0}
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=_llm_timeout()) as client:
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        dt = round(time.monotonic() - t0, 2)
        text = (data["choices"][0]["message"]["content"] or "")[:80]
        _log_call({"kind": "test", "model": s["model"], "status": "ok", "seconds": dt})
        return {"ok": True, "seconds": dt, "model": s["model"], "reply": text}
    except Exception as exc:
        dt = round(time.monotonic() - t0, 2)
        msg = f"{type(exc).__name__}: {exc}"[:300]
        _log_call({"kind": "test", "model": s["model"], "status": "error", "seconds": dt, "error": msg})
        return {"ok": False, "seconds": dt, "model": s["model"], "error": msg}


def chat(
    prompt: str, json_mode: bool = False, image_b64: str | list[str] | None = None
) -> str:
    """One-shot chat completion. Raises on failure so callers can 502 gracefully.
    image_b64 accepts one base64 JPEG or a list (multi-frame, e.g. video reels)."""
    s = get_llm_settings()
    if not s["base_url"]:
        raise RuntimeError("LLM not configured")
    url = s["base_url"].rstrip("/") + "/chat/completions"
    t0 = time.monotonic()
    content: Any = prompt
    if image_b64:
        frames = image_b64 if isinstance(image_b64, list) else [image_b64]
        content = [{"type": "text", "text": prompt}]
        content += [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            for b64 in frames
        ]
    messages: list[dict[str, Any]] = []
    # Admin-authored extra instructions ride along as a system message on EVERY call
    # (refill, suggestions, vision, voice) so one edit retunes the whole AI.
    if s.get("system_prompt", "").strip():
        messages.append({"role": "system", "content": s["system_prompt"]})
    messages.append({"role": "user", "content": content})
    body: dict[str, Any] = {
        "model": s["vision_model"] if image_b64 and s["vision_model"] else s["model"],
        "messages": messages,
        "temperature": 0.4,
    }
    want_json = json_mode
    if want_json:
        body["response_format"] = {"type": "json_object"}
    headers = {}
    if s["api_key"]:
        headers["Authorization"] = f"Bearer {s['api_key']}"
    try:
        with httpx.Client(timeout=_llm_timeout()) as client:
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        dt = round(time.monotonic() - t0, 2)
        _log_call({"kind": "chat", "model": body["model"], "status": "ok",
                   "seconds": dt, "prompt_chars": len(prompt),
                   "image": bool(image_b64),
                   "images": len(image_b64) if isinstance(image_b64, list) else (1 if image_b64 else 0)})
    except httpx.ReadTimeout as exc:
        dt = round(time.monotonic() - t0, 2)
        msg = f"Timed out after {dt}s — raise the AI timeout in Settings if your model is slow or cold-loading"
        _log_call({"kind": "chat", "model": body["model"], "status": "error",
                   "seconds": dt, "error": msg, "prompt_chars": len(prompt), "image": bool(image_b64)})
        raise RuntimeError(msg) from exc
    except Exception as exc:
        dt = round(time.monotonic() - t0, 2)
        msg = f"{type(exc).__name__}: {exc}"[:300]
        _log_call({"kind": "chat", "model": body["model"], "status": "error",
                   "seconds": dt, "error": msg, "prompt_chars": len(prompt), "image": bool(image_b64)})
        raise RuntimeError(msg) from exc
    text = data["choices"][0]["message"]["content"]
    if want_json:
        # Many local servers (llama.cpp, older Ollama) ignore response_format — fall back to
        # plain prompt + extraction instead of failing.
        try:
            return _extract_json(text)
        except Exception:
            retry_prompt = prompt + "\n\nRespond with ONLY a JSON object."
            body2 = dict(body)
            # keep the admin system message; replace only the user turn
            body2["messages"] = [m for m in body["messages"] if m["role"] == "system"]
            body2["messages"].append({"role": "user", "content": retry_prompt})
            body2.pop("response_format", None)
            with httpx.Client(timeout=_llm_timeout()) as client:
                resp = client.post(url, json=body2, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            _log_call({"kind": "chat", "model": body["model"], "status": "ok",
                       "seconds": round(time.monotonic() - t0, 2), "note": "json retry (no response_format)"})
            return _extract_json(data["choices"][0]["message"]["content"])
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

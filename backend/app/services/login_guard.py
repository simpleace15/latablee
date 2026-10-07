# Login rate limiting: in-process sliding window per (ip, username).
# Single-process deploy (uvicorn direct, one container) → a dict is exact.
# If ever scaled to multiple workers, swap for a tiny sqlite-backed window —
# the interface (check + record) stays the same.
import threading
import time
from collections import defaultdict, deque

from app.core.config import get_settings

_lock = threading.Lock()
_failures: dict[str, deque[float]] = defaultdict(deque)


def _key(ip: str, username: str) -> str:
    return f"{ip}|{username.casefold()}"


def is_locked(ip: str, username: str) -> int:
    """Seconds remaining on the lockout (0 = allowed)."""
    settings = get_settings()
    cutoff = time.monotonic() - settings.login_window_seconds
    with _lock:
        dq = _failures.get(_key(ip, username))
        if not dq:
            return 0
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= settings.login_max_attempts:
            return max(1, int(settings.login_window_seconds - (time.monotonic() - dq[0])))
        return 0


def record_failure(ip: str, username: str) -> None:
    with _lock:
        _failures[_key(ip, username)].append(time.monotonic())


def clear(ip: str, username: str) -> None:
    with _lock:
        _failures.pop(_key(ip, username), None)


def reset_for_tests() -> None:
    with _lock:
        _failures.clear()

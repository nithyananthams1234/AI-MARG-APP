"""Simple in-process sliding-window limiter for login attempts.

Adequate for a single backend instance. For multiple instances, replace the
store with Redis (documented in the deployment guide).
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.core.config import settings

_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def _key(request: Request, email: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}|{email.strip().lower()}"


def check_login_allowed(request: Request, email: str) -> None:
    window = settings.login_rate_limit_window_seconds
    now = time.monotonic()
    key = _key(request, email)
    with _lock:
        q = _attempts[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= settings.login_rate_limit_attempts:
            retry_after = int(window - (now - q[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )


def record_failed_login(request: Request, email: str) -> None:
    with _lock:
        _attempts[_key(request, email)].append(time.monotonic())


def reset_login_attempts(request: Request, email: str) -> None:
    with _lock:
        _attempts.pop(_key(request, email), None)


def reset_all() -> None:  # used by tests
    with _lock:
        _attempts.clear()

"""HTTP client for the MARG Classroom Coach service (educational LLM + RAG).

The backend is the only component that talks to the Coach; the frontend
never sees the Coach URL or its service key.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("marg.classroom_coach")


class CoachError(Exception):
    """Base error. ``status_code`` is what the backend should return."""

    status_code = 502
    public_message = "The Classroom Coach returned an unexpected response."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.public_message)
        self.public_message = message or self.public_message


class CoachUnavailable(CoachError):
    status_code = 503
    public_message = "The Classroom Coach is currently unavailable. Please try again shortly."


class CoachTimeout(CoachError):
    status_code = 504
    public_message = "The Classroom Coach took too long to respond. Please try again."


class CoachRejected(CoachError):
    status_code = 422
    public_message = "The Classroom Coach could not process this request."


def _headers(request_id: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.classroom_coach_api_key:
        headers["X-API-Key"] = settings.classroom_coach_api_key
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


async def _post(path: str, body: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    url = settings.classroom_coach_url.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=settings.classroom_coach_timeout_seconds) as client:
            response = await client.post(url, json=body, headers=_headers(request_id))
    except httpx.TimeoutException as exc:
        raise CoachTimeout() from exc
    except httpx.RequestError as exc:
        logger.warning("Classroom Coach unreachable at %s: %s", url, type(exc).__name__)
        raise CoachUnavailable() from exc

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as exc:
            raise CoachError() from exc

    detail = None
    try:
        detail = response.json().get("detail")
    except ValueError:
        pass
    logger.warning("Classroom Coach %s -> %s", path, response.status_code)
    if response.status_code in (401, 403):
        # Misconfiguration between services; do not expose details to users.
        raise CoachUnavailable("The Classroom Coach is not configured correctly.")
    if response.status_code == 503:
        raise CoachUnavailable(detail if isinstance(detail, str) else None)
    if response.status_code == 422:
        raise CoachRejected()
    if response.status_code == 504:
        raise CoachTimeout()
    raise CoachError(detail if isinstance(detail, str) and response.status_code == 502 else None)


async def chat(question: str, context: dict | None = None, request_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"question": question}
    if context:
        body["context"] = {k: v for k, v in context.items() if v}
    return await _post("/api/v1/chat", body, request_id)


async def analyze_observation(payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    return await _post("/api/v1/analyze/observation", payload, request_id)


async def readiness() -> dict[str, Any]:
    url = settings.classroom_coach_url.rstrip("/") + "/health/ready"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
        body = r.json()
        return {"available": r.status_code == 200, **{k: body.get(k) for k in ("checks", "llm_model", "embedding_model", "knowledge_chunks")}}
    except (httpx.RequestError, ValueError):
        return {"available": False, "checks": {"service": "unreachable"}}

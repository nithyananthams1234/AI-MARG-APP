"""HTTP adapter for the real MARG backend (BACKEND_MODE=marg).

Implements the MentorDataAdapter port against the backend's service API
``/api/v1/integrations/mentor-intelligence`` (verified against the backend
source; see docs/INTEGRATION.md):

  GET   /mentors
  GET   /mentors/{mentor_id}/snapshot
  POST  /mentors/{mentor_id}/visits                      (approved schedule_visit)
  PATCH /mentors/{mentor_id}/visits/{visit_id}/reschedule (approved reschedule_visit)
  PATCH /mentors/{mentor_id}/tasks/{task_id}/due-date     (approved update_task_due_date)

The backend authenticates this engine with X-Service-Key and scopes every
call to the given mentor, so the engine can never read another mentor's
records. The engine never accesses the MARG database directly.

Failures are raised (never silently replaced by DEMO DATA).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from pydantic import ValidationError

from app.integrations.base_adapter import AdapterError, MentorDataAdapter, RecordNotFound
from app.schemas.records import MentorSnapshot

logger = logging.getLogger(__name__)

BASE_PATH = "/api/v1/integrations/mentor-intelligence"


class BackendIntegrationNotAuthorised(RuntimeError):
    """Kept for backwards compatibility with earlier imports."""


class BackendUnavailable(AdapterError):
    pass


class BackendRejected(AdapterError):
    """The backend refused the operation (business rule / validation)."""


class HttpMARGBackendAdapter(MentorDataAdapter):
    def __init__(
        self,
        base_url: str,
        service_key: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not service_key:
            raise ValueError("MARG backend service key is required")
        self._base = base_url.rstrip("/") + BASE_PATH
        self._headers = {"X-Service-Key": service_key, "Accept": "application/json"}
        self._timeout = timeout_seconds
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Any) -> HttpMARGBackendAdapter:
        return cls(
            base_url=settings.marg_backend_url,
            service_key=settings.marg_backend_service_key.get_secret_value(),
            timeout_seconds=settings.marg_backend_timeout_seconds,
        )

    async def _request(self, method: str, path: str, json: dict | None = None) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                r = await client.request(method, self._base + path, json=json, headers=self._headers)
        except httpx.TimeoutException as exc:
            raise BackendUnavailable("MARG backend timed out") from exc
        except httpx.RequestError as exc:
            raise BackendUnavailable("MARG backend is unreachable") from exc

        if r.status_code in (200, 201):
            return r.json()
        detail = None
        try:
            detail = r.json().get("detail")
        except ValueError:
            pass
        if r.status_code == 404:
            raise RecordNotFound(str(detail or "Record not found in MARG backend"))
        if r.status_code in (400, 409, 422):
            # Business rule rejection, e.g. visit no longer 'planned'.
            raise BackendRejected(str(detail or "MARG backend rejected the operation"))
        if r.status_code in (401, 403):
            logger.error("MARG backend rejected the service key (%s)", r.status_code)
            raise BackendUnavailable("MARG backend authentication failed")
        raise BackendUnavailable(f"MARG backend error {r.status_code}")

    async def list_mentors(self) -> list[dict[str, str]]:
        return await self._request("GET", "/mentors")

    async def get_mentor_snapshot(self, mentor_ref: str) -> MentorSnapshot:
        data = await self._request("GET", f"/mentors/{mentor_ref}/snapshot")
        try:
            return MentorSnapshot.model_validate(data)
        except ValidationError as exc:
            # A contract mismatch is a server-side integration fault, not a client 422.
            logger.error("Invalid snapshot from MARG backend: %s", str(exc)[:500])
            raise BackendUnavailable("MARG backend returned an invalid snapshot") from exc

    async def reschedule_visit(self, mentor_ref: str, visit_ref: str, start: datetime, end: datetime) -> dict:
        return await self._request(
            "PATCH",
            f"/mentors/{mentor_ref}/visits/{visit_ref}/reschedule",
            {"start": start.isoformat(), "end": end.isoformat()},
        )

    async def schedule_visit(
        self, mentor_ref: str, school_ref: str, start: datetime, end: datetime, purpose: str
    ) -> dict:
        return await self._request(
            "POST",
            f"/mentors/{mentor_ref}/visits",
            {"school_ref": school_ref, "start": start.isoformat(), "end": end.isoformat(), "purpose": purpose},
        )

    async def update_task_due_date(self, mentor_ref: str, task_ref: str, due_at: datetime) -> dict:
        return await self._request(
            "PATCH", f"/mentors/{mentor_ref}/tasks/{task_ref}/due-date", {"due_at": due_at.isoformat()}
        )

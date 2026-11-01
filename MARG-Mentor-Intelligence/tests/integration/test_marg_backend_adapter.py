"""HTTP adapter for the real MARG backend, against a mocked backend transport."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.integrations.base_adapter import RecordNotFound
from app.integrations.marg_backend.client import BackendRejected, BackendUnavailable, HttpMARGBackendAdapter

MENTOR = "0b1a6f0e-7f57-4d60-9d43-3b7a2f2b9e11"
KEY = "svc-test-key-0123456789abcdef"
NOW = datetime(2026, 11, 2, 4, 30, tzinfo=UTC)


def snapshot() -> dict:
    return {
        "data_source": "marg",
        "is_demo": True,
        "mentor": {
            "id": MENTOR, "tenant_ref": "marg", "name": "Kavya", "role_title": "Mentor", "block": "Arcot",
            "work_start": "09:00:00", "work_end": "17:00:00", "working_days": [1, 2, 3, 4, 5, 6],
            "timezone": "Asia/Kolkata", "preferred_language": "en",
        },
        "schools": [{"id": "s1", "name": "GMS", "village": None, "block": "Arcot", "school_type": None,
                     "travel_minutes_from_base": 35, "available_days": None}],
        "teachers": [{"id": "t1", "school_ref": "s1", "name": "Meena", "subject": None, "grades": None,
                      "preferred_language": "en"}],
        "tasks": [{
            "id": "k1", "title": "Report", "description": None, "category": "reporting", "status": "pending",
            "due_at": (NOW + timedelta(days=1)).isoformat(), "estimated_minutes": 120, "urgency": 80, "impact": 70,
            "risk": 60, "depends_on": [], "school_ref": None, "created_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(), "completed_at": None,
        }],
        "visits": [{"id": "v1", "school_ref": "s1", "status": "planned", "scheduled_start": NOW.isoformat(),
                    "scheduled_end": (NOW + timedelta(hours=3)).isoformat(), "purpose": "Observe", "completed_at": None}],
        "observations": [], "action_plans": [], "followups": [], "schedule_items": [], "workload_activities": [],
    }


def adapter(handler) -> HttpMARGBackendAdapter:
    return HttpMARGBackendAdapter("http://marg.test", KEY, transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_snapshot_uses_service_key_and_validates():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("X-Service-Key")
        return httpx.Response(200, json=snapshot())

    snap = await adapter(handler).get_mentor_snapshot(MENTOR)
    assert seen["path"] == f"/api/v1/integrations/mentor-intelligence/mentors/{MENTOR}/snapshot"
    assert seen["key"] == KEY
    assert snap.data_source.value == "marg"
    assert snap.tasks[0].estimated_minutes == 120


@pytest.mark.asyncio
async def test_write_operations_map_to_backend_endpoints():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        return httpx.Response(200 if request.method == "PATCH" else 201, json={"ok": True})

    a = adapter(handler)
    await a.schedule_visit(MENTOR, "s1", NOW, NOW + timedelta(hours=3), "Follow-up")
    await a.reschedule_visit(MENTOR, "v1", NOW, NOW + timedelta(hours=2))
    await a.update_task_due_date(MENTOR, "k1", NOW)
    base = "/api/v1/integrations/mentor-intelligence/mentors/" + MENTOR
    assert [(m, p) for m, p, _ in calls] == [
        ("POST", base + "/visits"),
        ("PATCH", base + "/visits/v1/reschedule"),
        ("PATCH", base + "/tasks/k1/due-date"),
    ]
    assert calls[0][2]["school_ref"] == "s1" and calls[0][2]["purpose"] == "Follow-up"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "exc"),
    [(404, RecordNotFound), (409, BackendRejected), (422, BackendRejected), (401, BackendUnavailable), (500, BackendUnavailable)],
)
async def test_error_mapping(status, exc):
    a = adapter(lambda r: httpx.Response(status, json={"detail": "nope"}))
    with pytest.raises(exc):
        await a.get_mentor_snapshot(MENTOR)


@pytest.mark.asyncio
async def test_unreachable_backend_is_not_silently_replaced():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(BackendUnavailable):
        await adapter(handler).list_mentors()


@pytest.mark.asyncio
async def test_invalid_snapshot_is_an_integration_fault():
    bad = snapshot()
    bad["tasks"][0]["status"] = "not-a-status"
    with pytest.raises(BackendUnavailable, match="invalid snapshot"):
        await adapter(lambda r: httpx.Response(200, json=bad)).get_mentor_snapshot(MENTOR)

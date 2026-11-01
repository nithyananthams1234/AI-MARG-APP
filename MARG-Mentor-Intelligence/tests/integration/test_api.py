"""HTTP API tests (FastAPI app with in-memory SQLite DEMO DATA, AI disabled)."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.main import create_app
from tests.conftest import HEADERS, build_container, make_settings

AGENT_ENDPOINTS = [
    ("/api/v1/tasks/prioritise", {}),
    ("/api/v1/time/analysis", {}),
    ("/api/v1/schedule/analysis", {}),
    ("/api/v1/workload/analysis", {}),
    ("/api/v1/followups/analysis", {}),
    ("/api/v1/school-visits/plan", {}),
    ("/api/v1/plans/daily", {"date": "2026-11-02"}),
    ("/api/v1/plans/weekly", {"week_start": "2026-11-02"}),
    ("/api/v1/reports", {"period": "weekly"}),
    ("/api/v1/communications/drafts", {"followup_ref": "FU-001", "language": "en"}),
]


async def test_health(client):
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    r = await client.get("/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"]["status"] == "ok"
    assert r.json()["checks"]["redis"]["status"] == "not_configured"


@pytest.mark.parametrize("path,body", AGENT_ENDPOINTS)
async def test_every_agent_endpoint(client, path, body):
    r = await client.post(path, json={"mentor_ref": "MEN-001", **body}, headers=HEADERS)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["success"] and payload["schema_version"] == "v1"
    data = payload["data"]
    assert data["status"] == "completed" and data["result"]["is_demo_data"] is True
    assert data["result"]["data_source"] == "demo"
    status = await client.get(f"/api/v1/executions/{data['execution_id']}", headers=HEADERS)
    assert status.status_code == 200 and status.json()["data"]["steps"]


async def test_identity_header_required(client):
    r = await client.post("/api/v1/tasks/prioritise", json={"mentor_ref": "MEN-001"})
    assert r.status_code == 401 and r.json()["success"] is False


async def test_cross_mentor_request_forbidden(client):
    r = await client.post("/api/v1/tasks/prioritise", json={"mentor_ref": "MEN-002"}, headers=HEADERS)
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"


async def test_validation_errors_use_envelope(client):
    r = await client.post(
        "/api/v1/time/analysis", json={"mentor_ref": "MEN-001", "days": 99}, headers=HEADERS
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = await client.post("/api/v1/communications/drafts", json={"mentor_ref": "MEN-001"}, headers=HEADERS)
    assert r.status_code == 422


async def test_unknown_record_returns_not_found_with_execution(client):
    r = await client.post(
        "/api/v1/communications/drafts",
        json={"mentor_ref": "MEN-001", "teacher_ref": "TCH-012"},
        headers=HEADERS,
    )  # teacher belongs to another mentor's school
    assert r.status_code == 422 and "execution_id" in r.json()["error"]


async def test_approval_flow_over_http(client):
    run = (
        await client.post("/api/v1/schedule/analysis", json={"mentor_ref": "MEN-001"}, headers=HEADERS)
    ).json()
    pid = run["data"]["result"]["proposals"][0]["proposal_id"]
    listed = (
        await client.get(
            "/api/v1/proposals", params={"mentor_ref": "MEN-001", "status": "pending"}, headers=HEADERS
        )
    ).json()["data"]
    assert any(p["proposal_id"] == pid for p in listed)
    r = await client.post(
        f"/api/v1/proposals/{pid}/approve",
        json={"note": "Approved in demo"},
        headers={"X-Actor-Ref": "MEN-002"},
    )
    assert r.status_code == 403
    r = await client.post(
        f"/api/v1/proposals/{pid}/approve", json={"note": "Approved in demo"}, headers=HEADERS
    )
    assert r.status_code == 200 and r.json()["data"]["status"] == "executed"
    r = await client.post(f"/api/v1/proposals/{pid}/reject", headers=HEADERS)
    assert r.status_code == 409


async def test_events_are_idempotent_by_event_id(client):
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "FOLLOWUP_OVERDUE",
        "mentor_ref": "MEN-001",
        "occurred_at": "2026-11-02T08:00:00+05:30",
        "entity_type": "followup",
        "entity_ref": "FU-001",
    }
    first = (await client.post("/api/v1/events", json=event, headers=HEADERS)).json()
    second = (await client.post("/api/v1/events", json=event, headers=HEADERS)).json()
    assert first["meta"]["routed_to"] == "followup_management"
    assert second["meta"]["replayed"] and second["data"]["execution_id"] == first["data"]["execution_id"]
    bad = event | {"event_id": str(uuid.uuid4()), "occurred_at": "2026-11-02T08:00:00"}
    assert (await client.post("/api/v1/events", json=bad, headers=HEADERS)).status_code == 422


async def test_plans_are_persisted(client):
    await client.post("/api/v1/plans/daily", json={"mentor_ref": "MEN-001"}, headers=HEADERS)
    plans = (await client.get("/api/v1/plans", params={"mentor_ref": "MEN-001"}, headers=HEADERS)).json()[
        "data"
    ]
    assert plans and plans[0]["plan_type"] == "daily_plan"
    detail = (await client.get(f"/api/v1/plans/{plans[0]['plan_id']}", headers=HEADERS)).json()["data"]
    assert detail["content"]["facts"]["timeline"]


async def test_missing_working_hours_reported_for_second_mentor(client):
    r = await client.post(
        "/api/v1/plans/daily", json={"mentor_ref": "MEN-002"}, headers={"X-Actor-Ref": "MEN-002"}
    )
    data = r.json()["data"]["result"]
    assert data["facts"]["working_window"] is None
    assert any(m["field"] == "work_start" for m in data["missing_data"])


async def test_api_key_enforced_when_configured(db):
    c = build_container(make_settings(engine_api_key="engine-key-123"), db)
    app = create_app(c)
    app.state.container = c
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/api/v1/mentors", headers=HEADERS)
        assert r.status_code == 401
        r = await client.get("/api/v1/mentors", headers=HEADERS | {"X-API-Key": "engine-key-123"})
        assert r.status_code == 200 and r.json()["meta"]["label"] == "DEMO DATA"
        ready = (await client.get("/health/ready")).text
        assert "engine-key-123" not in ready

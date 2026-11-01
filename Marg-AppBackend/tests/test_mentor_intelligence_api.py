"""Service API used by Mentor Intelligence, and the mentor-facing proxy."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models.schedule import Schedule
from app.models.school_visits import SchoolVisit
from tests.conftest import auth_headers

pytestmark = pytest.mark.anyio

SERVICE_KEY = "mi-service-key-for-tests-0123456789"
BASE = "/api/v1/integrations/mentor-intelligence"


@pytest.fixture
def service_key(monkeypatch):
    monkeypatch.setattr(settings, "mentor_intelligence_service_key", SERVICE_KEY)
    return {"X-Service-Key": SERVICE_KEY}


async def test_service_key_required(world, client, service_key):
    assert (await client.get(f"{BASE}/mentors")).status_code == 401
    assert (await client.get(f"{BASE}/mentors", headers={"X-Service-Key": "wrong"})).status_code == 401
    # A mentor JWT is not a service credential.
    h = await auth_headers(client, "mentor.a@test.marg")
    assert (await client.get(f"{BASE}/mentors", headers=h)).status_code == 401


async def test_not_configured_fails_closed(world, client, monkeypatch):
    monkeypatch.setattr(settings, "mentor_intelligence_service_key", None)
    assert (await client.get(f"{BASE}/mentors", headers={"X-Service-Key": "anything"})).status_code == 503


async def test_list_mentors_and_scoped_snapshot(world, client, service_key):
    mentors = (await client.get(f"{BASE}/mentors", headers=service_key)).json()
    assert {m["name"] for m in mentors} == {"Mentor A", "Mentor B"}

    # Give mentor B a visit and a task; they must never appear in A's snapshot.
    hb = await auth_headers(client, "mentor.b@test.marg")
    await client.post(
        "/api/v1/school-visits/",
        json={"school_id": str(world["school_b"]), "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
        headers=hb,
    )
    await client.post("/api/v1/mentor-tasks/", json={"title": "B task"}, headers=hb)

    ha = await auth_headers(client, "mentor.a@test.marg")
    await client.post(
        "/api/v1/mentor-tasks/",
        json={"title": "A task", "estimated_minutes": 45, "category": "reporting",
              "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()},
        headers=ha,
    )

    snap = (await client.get(f"{BASE}/mentors/{world['mentor_a']}/snapshot", headers=service_key)).json()
    assert snap["data_source"] == "marg"
    assert snap["mentor"]["working_days"] == [1, 2, 3, 4, 5, 6]
    assert [s["id"] for s in snap["schools"]] == [str(world["school_a"])]
    assert [t["name"] for t in snap["teachers"]] == ["Teacher A"]
    assert [t["title"] for t in snap["tasks"]] == ["A task"]
    assert snap["tasks"][0]["estimated_minutes"] == 45 and snap["tasks"][0]["category"] == "reporting"
    assert snap["visits"] == []


async def test_unknown_mentor_is_404(world, client, service_key):
    r = await client.get(f"{BASE}/mentors/{world['admin']}/snapshot", headers=service_key)
    assert r.status_code == 404


async def test_visit_creation_and_reschedule_persist_schedule_interval(world, client, service_key):
    start = datetime.now(timezone.utc) + timedelta(days=4)
    end = start + timedelta(hours=2, minutes=30)
    created = await client.post(
        f"{BASE}/mentors/{world['mentor_a']}/visits",
        json={
            "school_ref": str(world["school_a"]),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "purpose": "Follow-up observation",
        },
        headers=service_key,
    )
    assert created.status_code == 201
    assert set(created.json()) == {"visit_ref", "school_ref", "start", "end", "status", "data_source"}
    visit_id = created.json()["visit_ref"]

    async with AsyncSessionLocal() as db:
        visit = await db.get(SchoolVisit, UUID(visit_id))
        schedules = (
            await db.execute(
                select(Schedule).where(
                    Schedule.school_visit_id == UUID(visit_id),
                    Schedule.status == "accepted",
                )
            )
        ).scalars().all()
    assert visit is not None and visit.scheduled_at == start
    assert len(schedules) == 1
    assert schedules[0].proposed_start_at == start
    assert schedules[0].proposed_end_at == end

    new_start = start + timedelta(days=1)
    new_end = new_start + timedelta(hours=3)
    rescheduled = await client.patch(
        f"{BASE}/mentors/{world['mentor_a']}/visits/{visit_id}/reschedule",
        json={"start": new_start.isoformat(), "end": new_end.isoformat()},
        headers=service_key,
    )
    assert rescheduled.status_code == 200
    assert set(rescheduled.json()) == {"visit_ref", "previous", "new", "data_source"}
    assert rescheduled.json()["new"] == {"start": new_start.isoformat(), "end": new_end.isoformat()}

    async with AsyncSessionLocal() as db:
        visit = await db.get(SchoolVisit, UUID(visit_id))
        schedules = (
            await db.execute(
                select(Schedule).where(
                    Schedule.school_visit_id == UUID(visit_id),
                    Schedule.status == "accepted",
                )
            )
        ).scalars().all()
    assert visit is not None and visit.scheduled_at == new_start
    assert len(schedules) == 1
    assert schedules[0].proposed_start_at == new_start
    assert schedules[0].proposed_end_at == new_end


async def test_visit_creation_rolls_back_when_action_recording_fails(
    world, client, service_key, monkeypatch
):
    from app.mentor_ai import integration_router

    async def fail_notify(*args, **kwargs):
        raise RuntimeError("notification write failed")

    monkeypatch.setattr(integration_router, "notify", fail_notify)
    start = datetime.now(timezone.utc) + timedelta(days=4)
    with pytest.raises(RuntimeError, match="notification write failed"):
        await client.post(
            f"{BASE}/mentors/{world['mentor_a']}/visits",
            json={
                "school_ref": str(world["school_a"]),
                "start": start.isoformat(),
                "end": (start + timedelta(hours=2)).isoformat(),
                "purpose": "Follow-up observation",
            },
            headers=service_key,
        )

    async with AsyncSessionLocal() as db:
        visits = (
            await db.execute(
                select(SchoolVisit).where(SchoolVisit.mentor_id == world["mentor_a"])
            )
        ).scalars().all()
        schedules = (
            await db.execute(
                select(Schedule).where(Schedule.created_by == world["mentor_a"])
            )
        ).scalars().all()
    assert visits == []
    assert schedules == []


async def test_visit_reschedule_rolls_back_visit_and_schedule_when_action_recording_fails(
    world, client, service_key, monkeypatch
):
    start = datetime.now(timezone.utc) + timedelta(days=4)
    end = start + timedelta(hours=2)
    created = await client.post(
        f"{BASE}/mentors/{world['mentor_a']}/visits",
        json={
            "school_ref": str(world["school_a"]),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "purpose": "Follow-up observation",
        },
        headers=service_key,
    )
    assert created.status_code == 201
    visit_id = created.json()["visit_ref"]

    from app.mentor_ai import integration_router

    async def fail_notify(*args, **kwargs):
        raise RuntimeError("notification write failed")

    monkeypatch.setattr(integration_router, "notify", fail_notify)
    new_start = start + timedelta(days=1)
    with pytest.raises(RuntimeError, match="notification write failed"):
        await client.patch(
            f"{BASE}/mentors/{world['mentor_a']}/visits/{visit_id}/reschedule",
            json={"start": new_start.isoformat(), "end": (new_start + timedelta(hours=3)).isoformat()},
            headers=service_key,
        )

    async with AsyncSessionLocal() as db:
        visit = await db.get(SchoolVisit, UUID(visit_id))
        schedule = (
            await db.execute(
                select(Schedule).where(
                    Schedule.school_visit_id == UUID(visit_id),
                    Schedule.status == "accepted",
                )
            )
        ).scalar_one()
    assert visit is not None and visit.scheduled_at == start
    assert schedule.proposed_start_at == start
    assert schedule.proposed_end_at == end


async def test_approved_actions_use_business_rules_and_scope(world, client, service_key):
    start = datetime.now(timezone.utc) + timedelta(days=3)
    r = await client.post(
        f"{BASE}/mentors/{world['mentor_a']}/visits",
        json={"school_ref": str(world["school_a"]), "start": start.isoformat(),
              "end": (start + timedelta(hours=3)).isoformat(), "purpose": "Follow-up observation"},
        headers=service_key,
    )
    assert r.status_code == 201, r.text
    visit_id = r.json()["visit_ref"]

    # Cannot schedule into a school the mentor is not assigned to.
    r = await client.post(
        f"{BASE}/mentors/{world['mentor_a']}/visits",
        json={"school_ref": str(world["school_b"]), "start": start.isoformat(),
              "end": (start + timedelta(hours=3)).isoformat(), "purpose": "x"},
        headers=service_key,
    )
    assert r.status_code == 404

    new_start = start + timedelta(days=1)
    r = await client.patch(
        f"{BASE}/mentors/{world['mentor_a']}/visits/{visit_id}/reschedule",
        json={"start": new_start.isoformat(), "end": (new_start + timedelta(hours=3)).isoformat()},
        headers=service_key,
    )
    assert r.status_code == 200, r.text

    # Mentor B cannot be used to move mentor A's visit.
    r = await client.patch(
        f"{BASE}/mentors/{world['mentor_b']}/visits/{visit_id}/reschedule",
        json={"start": new_start.isoformat(), "end": (new_start + timedelta(hours=3)).isoformat()},
        headers=service_key,
    )
    assert r.status_code == 404

    ha = await auth_headers(client, "mentor.a@test.marg")
    visit = (await client.get(f"/api/v1/school-visits/{visit_id}", headers=ha)).json()
    assert visit["scheduled_at"].startswith(new_start.date().isoformat())
    assert visit["mentor_id"] == str(world["mentor_a"])

    # Completed visits can no longer be rescheduled (same rule as the UI).
    await client.patch(f"/api/v1/school-visits/{visit_id}/status", json={"status": "in_progress"}, headers=ha)
    r = await client.patch(
        f"{BASE}/mentors/{world['mentor_a']}/visits/{visit_id}/reschedule",
        json={"start": new_start.isoformat(), "end": (new_start + timedelta(hours=3)).isoformat()},
        headers=service_key,
    )
    assert r.status_code == 409

    notes = (await client.get("/api/v1/notifications/", headers=ha)).json()["notifications"]
    assert sum(n["notification_type"] == "mentor_ai_action" for n in notes) == 2


async def test_mentor_proxy_asserts_own_identity(world, client, monkeypatch):
    from app.mentor_ai import router as mentor_ai_router

    captured = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, method, url, json=None, params=None, headers=None):
            captured.update(method=method, url=url, json=json, headers=headers)
            return httpx.Response(200, json={"success": True, "data": {"execution_id": "x"}})

    monkeypatch.setattr(mentor_ai_router.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(settings, "mentor_intelligence_api_key", "engine-key-test")
    h = await auth_headers(client, "mentor.a@test.marg")

    # Client tries to impersonate mentor B via the body: ignored.
    r = await client.post(
        "/api/v1/mentor-ai/agents/daily_plan", json={"mentor_ref": str(world["mentor_b"]), "use_ai": False}, headers=h
    )
    assert r.status_code == 200, r.text
    assert captured["url"].endswith("/api/v1/plans/daily")
    assert captured["json"]["mentor_ref"] == str(world["mentor_a"])
    assert captured["headers"]["X-Actor-Ref"] == str(world["mentor_a"])
    assert captured["headers"]["X-API-Key"] == "engine-key-test"

    assert (await client.post("/api/v1/mentor-ai/agents/drop_tables", json={}, headers=h)).status_code == 404

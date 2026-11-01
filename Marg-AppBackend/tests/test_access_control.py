"""School-level data isolation (IDOR / cross-school leakage)."""

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

pytestmark = pytest.mark.anyio


def _future(days: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


async def _visit(client, h, school_id) -> dict:
    r = await client.post("/api/v1/school-visits/", json={"school_id": str(school_id), "scheduled_at": _future()}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


async def test_school_list_and_get_are_scoped(world, client):
    ha = await auth_headers(client, "mentor.a@test.marg")
    schools = (await client.get("/api/v1/schools/", headers=ha)).json()
    assert [s["code"] for s in schools] == ["TSA"]
    assert (await client.get(f"/api/v1/schools/{world['school_b']}", headers=ha)).status_code == 404
    assert (await client.get(f"/api/v1/schools/{world['school_a']}", headers=ha)).status_code == 200


async def test_cannot_create_visit_in_unassigned_school(world, client):
    ha = await auth_headers(client, "mentor.a@test.marg")
    r = await client.post(
        "/api/v1/school-visits/", json={"school_id": str(world["school_b"]), "scheduled_at": _future()}, headers=ha
    )
    assert r.status_code == 404


async def test_other_mentors_visit_and_observation_are_invisible(world, client):
    hb = await auth_headers(client, "mentor.b@test.marg")
    visit_b = await _visit(client, hb, world["school_b"])
    await client.patch(f"/api/v1/school-visits/{visit_b['id']}/status", json={"status": "in_progress"}, headers=hb)
    obs = await client.post(
        "/api/v1/observations/",
        json={
            "school_visit_id": visit_b["id"],
            "teacher_id": str(world["teacher_b"]),
            "classroom_id": str(world["class_b"]),
            "subject": "Mathematics",
        },
        headers=hb,
    )
    assert obs.status_code == 201, obs.text

    ha = await auth_headers(client, "mentor.a@test.marg")
    assert (await client.get(f"/api/v1/school-visits/{visit_b['id']}", headers=ha)).status_code == 404
    assert (
        await client.patch(f"/api/v1/school-visits/{visit_b['id']}/status", json={"status": "cancelled"}, headers=ha)
    ).status_code == 404
    assert (await client.get(f"/api/v1/observations/{obs.json()['id']}", headers=ha)).status_code == 404
    assert (await client.get("/api/v1/school-visits/", headers=ha)).json() == []
    assert (await client.get("/api/v1/observations/", headers=ha)).json() == []


async def test_teachers_and_classrooms_are_scoped(world, client):
    ha = await auth_headers(client, "mentor.a@test.marg")
    teachers = (await client.get("/api/v1/teachers/", headers=ha)).json()
    assert [t["employee_code"] for t in teachers] == ["T-A"]
    assert (await client.get(f"/api/v1/teachers/{world['teacher_b']}", headers=ha)).status_code == 404
    classrooms = (await client.get("/api/v1/classrooms/", headers=ha)).json()
    assert [c["name"] for c in classrooms] == ["6-A"]
    assert (await client.get(f"/api/v1/schools/{world['school_b']}/teachers", headers=ha)).status_code == 404


async def test_cannot_observe_with_foreign_teacher(world, client):
    ha = await auth_headers(client, "mentor.a@test.marg")
    visit = await _visit(client, ha, world["school_a"])
    r = await client.post(
        "/api/v1/observations/",
        json={
            "school_visit_id": visit["id"],
            "teacher_id": str(world["teacher_b"]),
            "classroom_id": str(world["class_a"]),
            "subject": "Science",
        },
        headers=ha,
    )
    assert r.status_code == 404


async def test_tasks_are_private_to_owner(world, client):
    hb = await auth_headers(client, "mentor.b@test.marg")
    t = await client.post("/api/v1/mentor-tasks/", json={"title": "B private task"}, headers=hb)
    assert t.status_code == 201, t.text
    ha = await auth_headers(client, "mentor.a@test.marg")
    assert (await client.get("/api/v1/mentor-tasks/", headers=ha)).json() == []
    assert (await client.get(f"/api/v1/mentor-tasks/{t.json()['id']}", headers=ha)).status_code == 404


async def test_mentor_cannot_self_assign_schools(world, client):
    ha = await auth_headers(client, "mentor.a@test.marg")
    r = await client.post(
        "/api/v1/mentor-schools/",
        json={"user_id": str(world["mentor_a"]), "school_id": str(world["school_b"])},
        headers=ha,
    )
    assert r.status_code == 403


async def test_mentor_cannot_create_schools(world, client):
    ha = await auth_headers(client, "mentor.a@test.marg")
    r = await client.post("/api/v1/schools/", json={"name": "Rogue School", "code": "ROGUE"}, headers=ha)
    assert r.status_code == 403


async def test_admin_assignment_grants_access(world, client):
    hadm = await auth_headers(client, "admin@test.marg")
    r = await client.post(
        "/api/v1/mentor-schools/",
        json={"user_id": str(world["mentor_a"]), "school_id": str(world["school_b"])},
        headers=hadm,
    )
    assert r.status_code == 201, r.text
    ha = await auth_headers(client, "mentor.a@test.marg")
    codes = sorted(s["code"] for s in (await client.get("/api/v1/schools/", headers=ha)).json())
    assert codes == ["TSA", "TSB"]

    # Deactivation removes access again.
    r = await client.patch(f"/api/v1/mentor-schools/{r.json()['id']}/deactivate", headers=hadm)
    assert r.status_code == 200
    codes = [s["code"] for s in (await client.get("/api/v1/schools/", headers=ha)).json()]
    assert codes == ["TSA"]


async def test_reports_do_not_leak_other_schools(world, client):
    hb = await auth_headers(client, "mentor.b@test.marg")
    await _visit(client, hb, world["school_b"])
    ha = await auth_headers(client, "mentor.a@test.marg")
    dash = (await client.get("/api/v1/reports/dashboard", headers=ha)).json()
    assert dash["total_schools"] == 1
    assert dash["total_visits"] == 0
    assert (await client.get(f"/api/v1/reports/schools/{world['school_b']}", headers=ha)).status_code == 404

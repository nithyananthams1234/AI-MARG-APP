"""End-to-end mentor workflow through the real API and database."""

from datetime import date, datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers, new_key

pytestmark = pytest.mark.anyio

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


async def _ok(resp, code=200):
    assert resp.status_code == code, f"{resp.request.method} {resp.request.url} -> {resp.status_code}: {resp.text}"
    return resp.json() if resp.content else None


async def test_full_classroom_improvement_cycle(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    api = "/api/v1"
    today = date.today()

    # 1. Plan and start a visit
    visit = await _ok(
        await client.post(
            f"{api}/school-visits/",
            json={
                "school_id": str(world["school_a"]),
                "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "notes": "Focus on Grade 6 fractions",
            },
            headers=h,
        ),
        201,
    )
    assert visit["status"] == "planned" and visit["version"] == 1
    visit = await _ok(await client.patch(f"{api}/school-visits/{visit['id']}/status", json={"status": "in_progress"}, headers=h))
    assert visit["version"] == 2

    # 2. Observation -> submitted
    obs = await _ok(
        await client.post(
            f"{api}/observations/",
            json={
                "school_visit_id": visit["id"],
                "teacher_id": str(world["teacher_a"]),
                "classroom_id": str(world["class_a"]),
                "subject": "Mathematics",
                "topic": "Equivalent fractions",
                "notes": "Most students could not explain why 2/4 equals 1/2.",
            },
            headers=h,
        ),
        201,
    )
    await _ok(await client.patch(f"{api}/observations/{obs['id']}/status", json={"status": "submitted"}, headers=h))

    # 3. Evidence photo for the observation
    ev = await _ok(
        await client.post(
            f"{api}/evidence/",
            data={"observation_id": obs["id"], "description": "Board work"},
            files={"file": ("board.png", PNG_1PX, "image/png")},
            headers=h,
        ),
        201,
    )
    dl = await client.get(f"{api}/evidence/{ev['id']}/download", headers=h)
    assert dl.status_code == 200 and dl.content == PNG_1PX

    # 4. Finding -> approved
    finding = await _ok(
        await client.post(
            f"{api}/observation-findings/",
            json={"observation_id": obs["id"], "title": "Conceptual gap in fractions", "description": "Rote procedure only", "category": "Conceptual understanding"},
            headers=h,
        ),
        201,
    )
    await _ok(await client.patch(f"{api}/observation-findings/{finding['id']}/decision", json={"status": "mentor_approved"}, headers=h))

    # 5. Learning gap (version bumps on update even though the router never did)
    gap = await _ok(
        await client.post(
            f"{api}/learning-gaps/",
            json={
                "observation_id": obs["id"],
                "observation_finding_id": finding["id"],
                "title": "Equivalent fractions",
                "description": "Cannot reason about equivalence",
                "subject": "Mathematics",
                "grade": "6",
                "severity": "high",
            },
            headers=h,
        ),
        201,
    )
    gap2 = await _ok(await client.put(f"{api}/learning-gaps/{gap['id']}", json={"severity": "critical"}, headers=h))
    assert gap2["severity"] == "critical"

    # 6. Recommendation -> mentor approval (official record only after approval)
    rec = await _ok(
        await client.post(
            f"{api}/recommendations/",
            json={
                "learning_gap_id": gap["id"],
                "title": "Use fraction strips",
                "description": "Hands-on equivalence with paper strips",
                "rationale": "Concrete-pictorial-abstract sequence",
                "category": "Pedagogy",
            },
            headers=h,
        ),
        201,
    )
    assert rec["status"] == "ai_suggested"
    # Action plan cannot be created before approval
    r = await client.post(
        f"{api}/action-plans/",
        json={"recommendation_id": rec["id"], "title": "Fractions plan", "description": "Two-week plan", "responsible_person": "Teacher A", "start_date": str(today), "due_date": str(today + timedelta(days=14))},
        headers=h,
    )
    assert r.status_code == 400, r.text
    await _ok(await client.patch(f"{api}/recommendations/{rec['id']}/decision", json={"status": "mentor_approved"}, headers=h))

    # 7. Action plan -> approved
    plan = await _ok(
        await client.post(
            f"{api}/action-plans/",
            json={"recommendation_id": rec["id"], "title": "Fractions plan", "description": "Two-week plan", "responsible_person": "Teacher A", "start_date": str(today), "due_date": str(today + timedelta(days=14))},
            headers=h,
        ),
        201,
    )
    for s in ("pending_approval", "approved"):
        plan = await _ok(await client.patch(f"{api}/action-plans/{plan['id']}/status", json={"status": s}, headers=h))
    assert plan["status"] == "approved"

    # 8. Step + follow-up lifecycle
    step = await _ok(
        await client.post(
            f"{api}/action-plan-steps/",
            json={"action_plan_id": plan["id"], "title": "Model with fraction strips", "description": "Demo lesson", "responsible_person": "Teacher A", "due_date": str(today + timedelta(days=7))},
            headers=h,
        ),
        201,
    )
    fu = await _ok(
        await client.post(
            f"{api}/follow-ups/",
            json={"action_plan_step_id": step["id"], "teacher_id": str(world["teacher_a"]), "description": "Share a photo of the strips lesson"},
            headers=h,
        ),
        201,
    )
    await _ok(await client.patch(f"{api}/follow-ups/{fu['id']}/teacher-response", json={"teacher_response": "Lesson done"}, headers=h))
    await _ok(await client.patch(f"{api}/follow-ups/{fu['id']}/evidence", json={"teacher_response": "Photo attached"}, headers=h))

    dash = await _ok(await client.get(f"{api}/reports/dashboard", headers=h))
    assert dash["follow_ups_awaiting_verification"] == 1

    await _ok(await client.patch(f"{api}/follow-ups/{fu['id']}/mentor-decision", json={"status": "mentor_verified", "mentor_notes": "Good"}, headers=h))
    fu = await _ok(await client.patch(f"{api}/follow-ups/{fu['id']}/close", json={"status": "closed"}, headers=h))
    assert fu["status"] == "closed"

    # 9. Complete the visit; reports reflect real records
    await _ok(await client.patch(f"{api}/school-visits/{visit['id']}/status", json={"status": "completed"}, headers=h))
    dash = await _ok(await client.get(f"{api}/reports/dashboard", headers=h))
    assert dash["total_schools"] == 1
    assert dash["total_visits"] == 1 and dash["completed_visits"] == 1
    assert dash["total_observations"] == 1
    assert dash["total_learning_gaps"] == 1
    assert dash["total_action_plans"] == 1 and dash["active_action_plans"] == 1
    assert dash["open_follow_ups"] == 0

    school = await _ok(await client.get(f"{api}/reports/schools/{world['school_a']}", headers=h))
    assert school["total_action_plans"] == 1 and school["total_observations"] == 1

    gaps = await _ok(await client.get(f"{api}/reports/learning-gaps", headers=h))
    assert gaps[0]["critical_severity"] == 1

    activity = await _ok(await client.get(f"{api}/reports/activity?days=7", headers=h))
    assert sum(d["visits_completed"] for d in activity["days"]) == 1
    assert sum(d["observations_recorded"] for d in activity["days"]) == 1


async def test_task_lifecycle_and_priority(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    t = await _ok(
        await client.post(
            "/api/v1/mentor-tasks/",
            json={
                "school_id": str(world["school_a"]),
                "title": "Prepare Grade 6 feedback",
                "due_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "urgency": 90, "impact": 80, "risk": 70, "deadline_proximity": 90, "workload_dependency": 50,
            },
            headers=h,
        ),
        201,
    )
    assert t["priority"] in ("high", "critical")
    dash = await _ok(await client.get("/api/v1/reports/dashboard", headers=h))
    assert dash["pending_tasks"] == 1 and dash["overdue_tasks"] == 1
    await _ok(await client.patch(f"/api/v1/mentor-tasks/{t['id']}/status", json={"status": "in_progress"}, headers=h))
    t = await _ok(await client.patch(f"/api/v1/mentor-tasks/{t['id']}/status", json={"status": "completed"}, headers=h))
    assert t["status"] == "completed" and t["completed_at"]


async def test_whatsapp_queue_table_exists_and_is_owned(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    key = new_key()
    m = await _ok(
        await client.post(
            "/api/v1/whatsapp/messages",
            json={"recipient": "+919800000001", "message_type": "text", "content": "Reminder", "idempotency_key": key},
            headers=h,
        ),
        201,
    )
    assert m["status"] == "queued"
    hb = await auth_headers(client, "mentor.b@test.marg")
    assert (await client.get("/api/v1/whatsapp/messages", headers=hb)).json() == []
    # Idempotency key is global even across owners.
    r = await client.post(
        "/api/v1/whatsapp/messages",
        json={"recipient": "+919800000001", "message_type": "text", "content": "x", "idempotency_key": key},
        headers=hb,
    )
    assert r.status_code == 409


async def test_unhandled_errors_do_not_leak_details(world, client):
    from app.main import app

    @app.get("/__boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    import httpx

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/__boom")
    assert r.status_code == 500
    assert "secret" not in r.text
    assert r.json()["detail"] == "Internal server error"

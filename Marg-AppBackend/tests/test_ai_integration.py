"""Backend <-> Classroom Coach integration (Coach replaced by a fake) and reminders."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.integrations import classroom_coach
from tests.conftest import auth_headers

pytestmark = pytest.mark.anyio

NOTES = (
    "Teacher explained equivalent fractions using only the textbook. Most students copied "
    "the steps; when asked why 2/4 equals 1/2 only two students could explain."
)

FAKE_ANALYSIS = {
    "summary": "Students followed procedures without conceptual understanding.",
    "findings": [
        {"title": "Procedure-focused explanation", "description": "Only textbook steps used", "category": "Pedagogy",
         "confidence": 0.8, "evidence_reference": "used only the textbook"},
    ],
    "learning_gaps": [
        {"title": "Equivalent fractions reasoning", "description": "Cannot justify equivalence", "subject": "Mathematics",
         "grade": "6", "severity": "high"},
    ],
    "recommendations": [
        {"title": "Fraction strips", "description": "Use paper strips to compare fractions",
         "rationale": "Concrete materials build understanding [S1]", "category": "Pedagogy"},
    ],
    "sources": [{"document": "12.pdf", "title": "Teaching Fractions", "page": 4, "relevance": 0.71, "excerpt": "..."}],
    "model": "qwen2.5:3b",
    "status": "ai_suggested",
}


@pytest.fixture
def fake_coach(monkeypatch):
    calls = []

    async def fake_post(path, body, request_id=None):
        calls.append((path, body))
        if path == "/api/v1/analyze/observation":
            return FAKE_ANALYSIS
        if path == "/api/v1/chat":
            return {
                "question": body["question"],
                "answer": "Use concrete materials [S1].",
                "sources": [{"document": "12.pdf", "title": "Teaching Fractions", "page": 4, "relevance": 0.7, "excerpt": "..."}],
                "grounded": True,
                "model": "qwen2.5:3b",
            }
        raise AssertionError(path)

    monkeypatch.setattr(classroom_coach, "_post", fake_post)
    return calls


async def _submitted_observation(client, h, world, notes=NOTES):
    v = await client.post(
        "/api/v1/school-visits/",
        json={"school_id": str(world["school_a"]), "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
        headers=h,
    )
    await client.patch(f"/api/v1/school-visits/{v.json()['id']}/status", json={"status": "in_progress"}, headers=h)
    o = await client.post(
        "/api/v1/observations/",
        json={"school_visit_id": v.json()["id"], "teacher_id": str(world["teacher_a"]),
              "classroom_id": str(world["class_a"]), "subject": "Mathematics", "topic": "Fractions", "notes": notes},
        headers=h,
    )
    assert o.status_code == 201, o.text
    await client.patch(f"/api/v1/observations/{o.json()['id']}/status", json={"status": "submitted"}, headers=h)
    return o.json()


async def test_observation_analysis_job_end_to_end(world, client, fake_coach):
    h = await auth_headers(client, "mentor.a@test.marg")
    obs = await _submitted_observation(client, h, world)

    r = await client.post(
        "/api/v1/ai/jobs",
        json={"job_type": "observation_analysis", "entity_type": "observation", "entity_id": obs["id"],
              "input_payload": {"observation_notes": "client-supplied text must be ignored"}},
        headers=h,
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    # Input was built server-side from the DB, without names.
    path, body = fake_coach[-1]
    assert path == "/api/v1/analyze/observation"
    assert body["observation_notes"] == NOTES and body["grade"] == "6"
    assert "Teacher A" not in str(body)

    job = (await client.get(f"/api/v1/ai/jobs/{job_id}", headers=h)).json()
    assert job["status"] == "completed"
    assert job["result_payload"]["provider"] == "classroom_coach"
    assert job["result_payload"]["sources"][0]["title"] == "Teaching Fractions"

    notes = (await client.get("/api/v1/notifications/", headers=h)).json()
    assert any(n["notification_type"] == "ai_job_completed" for n in notes["notifications"])

    applied = await client.post(
        f"/api/v1/ai/jobs/{job_id}/apply",
        json={"finding_indexes": [0], "learning_gap_indexes": [0], "recommendations": [{"index": 0, "learning_gap_index": 0}]},
        headers=h,
    )
    assert applied.status_code == 201, applied.text
    ids = applied.json()
    again = await client.post(
        f"/api/v1/ai/jobs/{job_id}/apply",
        json={"finding_indexes": [0], "learning_gap_indexes": [0], "recommendations": []},
        headers=h,
    )
    assert again.status_code == 409  # never recorded twice
    rec = (await client.get(f"/api/v1/recommendations/{ids['recommendation_ids'][0]}", headers=h)).json()
    finding = (await client.get(f"/api/v1/observation-findings/{ids['finding_ids'][0]}", headers=h)).json()
    # AI output is not official until the mentor approves it.
    assert rec["status"] == "ai_suggested" and finding["status"] == "ai_suggested"
    today = datetime.now(timezone.utc).date()
    blocked = await client.post(
        "/api/v1/action-plans/",
        json={"recommendation_id": rec["id"], "title": "Plan", "description": "Plan text", "responsible_person": "Teacher A",
              "start_date": str(today), "due_date": str(today + timedelta(days=7))},
        headers=h,
    )
    assert blocked.status_code == 400


async def test_cannot_analyse_other_mentors_observation(world, client, fake_coach):
    hb = await auth_headers(client, "mentor.b@test.marg")
    # Mentor B's observation in school B
    v = await client.post(
        "/api/v1/school-visits/",
        json={"school_id": str(world["school_b"]), "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
        headers=hb,
    )
    await client.patch(f"/api/v1/school-visits/{v.json()['id']}/status", json={"status": "in_progress"}, headers=hb)
    o = await client.post(
        "/api/v1/observations/",
        json={"school_visit_id": v.json()["id"], "teacher_id": str(world["teacher_b"]),
              "classroom_id": str(world["class_b"]), "subject": "Science", "notes": NOTES},
        headers=hb,
    )
    ha = await auth_headers(client, "mentor.a@test.marg")
    r = await client.post(
        "/api/v1/ai/jobs",
        json={"job_type": "observation_analysis", "entity_type": "observation", "entity_id": o.json()["id"]},
        headers=ha,
    )
    assert r.status_code == 404
    assert fake_coach == []


async def test_short_notes_rejected_before_calling_ai(world, client, fake_coach):
    h = await auth_headers(client, "mentor.a@test.marg")
    obs = await _submitted_observation(client, h, world, notes="too short")
    r = await client.post(
        "/api/v1/ai/jobs",
        json={"job_type": "observation_analysis", "entity_type": "observation", "entity_id": obs["id"]},
        headers=h,
    )
    assert r.status_code == 422
    assert fake_coach == []


async def test_coach_unavailable_marks_job_failed_with_safe_message(world, client, monkeypatch):
    async def down(path, body, request_id=None):
        raise classroom_coach.CoachUnavailable()

    monkeypatch.setattr(classroom_coach, "_post", down)
    h = await auth_headers(client, "mentor.a@test.marg")
    obs = await _submitted_observation(client, h, world)
    r = await client.post(
        "/api/v1/ai/jobs",
        json={"job_type": "observation_analysis", "entity_type": "observation", "entity_id": obs["id"]},
        headers=h,
    )
    job = (await client.get(f"/api/v1/ai/jobs/{r.json()['id']}", headers=h)).json()
    assert job["status"] == "failed"
    assert "unavailable" in job["error_message"].lower()

    # Coach comes back: retry re-runs the job immediately (no separate worker needed).
    async def back_up(path, body, request_id=None):
        return FAKE_ANALYSIS

    monkeypatch.setattr(classroom_coach, "_post", back_up)
    retried = await client.patch(f"/api/v1/ai/jobs/{job['id']}/retry", headers=h)
    assert retried.status_code == 200
    assert (await client.get(f"/api/v1/ai/jobs/{job['id']}", headers=h)).json()["status"] == "completed"

    monkeypatch.setattr(classroom_coach, "_post", down)  # Coach unavailable again

    chat = await client.post("/api/v1/coach/chat", json={"question": "How to teach fractions?"}, headers=h)
    assert chat.status_code == 503
    assert "unavailable" in chat.json()["detail"].lower()


async def test_coach_chat_grounded_in_observation(world, client, fake_coach):
    h = await auth_headers(client, "mentor.a@test.marg")
    obs = await _submitted_observation(client, h, world)
    r = await client.post(
        "/api/v1/coach/chat",
        json={"question": "How can the teacher improve this lesson?", "observation_id": obs["id"]},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["grounded"] is True and r.json()["sources"][0]["page"] == 4
    _, body = fake_coach[-1]
    assert body["context"]["subject"] == "Mathematics" and body["context"]["grade"] == "6"

    r = await client.post(
        "/api/v1/coach/chat", json={"question": "Hello there", "observation_id": str(uuid.uuid4())}, headers=h
    )
    assert r.status_code == 404


async def test_reminders_are_generated_once_and_only_for_owner(world, client):
    from app.database.session import AsyncSessionLocal
    from app.services.notifications import generate_reminders

    h = await auth_headers(client, "mentor.a@test.marg")
    now = datetime.now(timezone.utc)
    await client.post("/api/v1/mentor-tasks/", json={"title": "Overdue report", "due_at": (now - timedelta(hours=3)).isoformat()}, headers=h)
    await client.post("/api/v1/mentor-tasks/", json={"title": "Due soon", "due_at": (now + timedelta(hours=3)).isoformat()}, headers=h)
    await client.post("/api/v1/mentor-tasks/", json={"title": "Far away", "due_at": (now + timedelta(days=9)).isoformat()}, headers=h)
    await client.post(
        "/api/v1/school-visits/",
        json={"school_id": str(world["school_a"]), "scheduled_at": (now + timedelta(hours=5)).isoformat()},
        headers=h,
    )

    async with AsyncSessionLocal() as db:
        first = await generate_reminders(db)
    async with AsyncSessionLocal() as db:
        second = await generate_reminders(db)
    assert first == 3 and second == 0

    body = (await client.get("/api/v1/notifications/", headers=h)).json()
    types = sorted(n["notification_type"] for n in body["notifications"])
    assert types == ["task_due_soon", "task_overdue", "visit_upcoming"]
    assert body["unread_count"] == 3

    hb = await auth_headers(client, "mentor.b@test.marg")
    assert (await client.get("/api/v1/notifications/", headers=hb)).json()["total"] == 0

"""Offline synchronisation: push (apply + conflicts + idempotency) and pull."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

pytestmark = pytest.mark.anyio

DEVICE = "test-device-1"


def op(entity_type, entity_id, operation_type, payload, client_version=1, key=None):
    return {
        "idempotency_key": key or uuid.uuid4().hex,
        "device_id": DEVICE,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "operation_type": operation_type,
        "payload": payload,
        "client_version": client_version,
    }


async def push(client, h, ops):
    r = await client.post("/api/v1/sync/push", json={"operations": ops}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def visit_payload(world):
    return {
        "school_id": str(world["school_a"]),
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "notes": "Offline-planned visit",
    }


async def test_offline_creates_use_client_ids_and_chain(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    visit_id, obs_id = uuid.uuid4(), uuid.uuid4()
    res = await push(
        client,
        h,
        [
            op("school_visit", visit_id, "create", visit_payload(world)),
            op("school_visit", visit_id, "update", {"_action": "status", "status": "in_progress"}, client_version=1),
            op(
                "observation",
                obs_id,
                "create",
                {
                    "school_visit_id": str(visit_id),
                    "teacher_id": str(world["teacher_a"]),
                    "classroom_id": str(world["class_a"]),
                    "subject": "English",
                    "notes": "Recorded offline in the classroom",
                },
            ),
            op("observation", obs_id, "update", {"notes": "Edited offline"}, client_version=1),
        ],
    )
    assert res["synced"] == 4, res
    assert [o["server_version"] for o in res["operations"]] == [1, 2, 1, 2]

    v = (await client.get(f"/api/v1/school-visits/{visit_id}", headers=h)).json()
    assert v["status"] == "in_progress"
    o = (await client.get(f"/api/v1/observations/{obs_id}", headers=h)).json()
    assert o["notes"] == "Edited offline"


async def test_repush_is_idempotent_and_creates_no_duplicates(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    visit_id = uuid.uuid4()
    batch = [op("school_visit", visit_id, "create", visit_payload(world))]
    first = await push(client, h, batch)
    second = await push(client, h, batch)
    assert first["accepted"] == 1 and second["already_received"] == 1
    assert second["operations"][0]["status"] == "synced"
    # Same create with a fresh key (e.g. device lost its outbox state)
    third = await push(client, h, [op("school_visit", visit_id, "create", visit_payload(world))])
    assert third["synced"] == 1
    visits = (await client.get("/api/v1/school-visits/", headers=h)).json()
    assert len(visits) == 1


async def test_stale_update_is_a_conflict_and_server_data_wins(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    task_id = uuid.uuid4()
    await push(client, h, [op("mentor_task", task_id, "create", {"title": "Collect lesson plans"})])

    # Online edit on another device moves the server to version 2.
    r = await client.put(f"/api/v1/mentor-tasks/{task_id}", json={"title": "Collect lesson plans (online)"}, headers=h)
    assert r.status_code == 200 and r.json()["title"].endswith("(online)")

    # Offline device still holds version 1.
    res = await push(client, h, [op("mentor_task", task_id, "update", {"title": "Offline title"}, client_version=1)])
    o = res["operations"][0]
    assert o["status"] == "conflict" and o["server_version"] == 2
    assert "server version 2" in o["error_message"]
    t = (await client.get(f"/api/v1/mentor-tasks/{task_id}", headers=h)).json()
    assert t["title"] == "Collect lesson plans (online)"


async def test_partial_failure_does_not_block_other_operations(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    good, bad = uuid.uuid4(), uuid.uuid4()
    res = await push(
        client,
        h,
        [
            op("school_visit", good, "create", visit_payload(world)),
            # Invalid transition planned -> completed: rejected by the same rule as online
            op("school_visit", good, "update", {"_action": "status", "status": "completed"}, client_version=1),
            # Validation error
            op("mentor_task", bad, "create", {"title": ""}),
            # Unsupported offline entity
            op("school", uuid.uuid4(), "create", {"name": "X", "code": "X1"}),
            op("mentor_task", uuid.uuid4(), "create", {"title": "Valid task"}),
        ],
    )
    statuses = [o["status"] for o in res["operations"]]
    assert statuses == ["synced", "conflict", "failed", "failed", "synced"], res
    assert all(o["error_message"] for o in res["operations"] if o["status"] != "synced")


async def test_offline_cannot_write_to_unassigned_school(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    payload = visit_payload(world) | {"school_id": str(world["school_b"])}
    res = await push(client, h, [op("school_visit", uuid.uuid4(), "create", payload)])
    assert res["operations"][0]["status"] == "failed"

    # Nor update another mentor's record by id.
    hb = await auth_headers(client, "mentor.b@test.marg")
    vb = uuid.uuid4()
    await push(client, hb, [op("school_visit", vb, "create", visit_payload(world) | {"school_id": str(world["school_b"])})])
    res = await push(client, h, [op("school_visit", vb, "update", {"notes": "hijack"}, client_version=1)])
    assert res["operations"][0]["status"] == "failed"
    assert (await client.get(f"/api/v1/school-visits/{vb}", headers=hb)).json()["notes"] != "hijack"


async def test_idempotency_key_reuse_by_other_user_rejected(world, client):
    ha = await auth_headers(client, "mentor.a@test.marg")
    hb = await auth_headers(client, "mentor.b@test.marg")
    key = uuid.uuid4().hex
    await push(client, ha, [op("mentor_task", uuid.uuid4(), "create", {"title": "A"}, key=key)])
    r = await client.post(
        "/api/v1/sync/push",
        json={"operations": [op("mentor_task", uuid.uuid4(), "create", {"title": "B"}, key=key)]},
        headers=hb,
    )
    assert r.status_code == 409


async def test_pull_paginates_and_returns_tombstones(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    visit_id, obs_id = uuid.uuid4(), uuid.uuid4()
    await push(
        client,
        h,
        [
            op("school_visit", visit_id, "create", visit_payload(world)),
            op("school_visit", visit_id, "update", {"_action": "status", "status": "in_progress"}),
            op(
                "observation",
                obs_id,
                "create",
                {"school_visit_id": str(visit_id), "teacher_id": str(world["teacher_a"]), "classroom_id": str(world["class_a"]), "subject": "Science"},
            ),
            op("mentor_task", uuid.uuid4(), "create", {"title": "No-school task"}),
        ],
    )
    # Delete the draft observation offline -> tombstone
    res = await push(client, h, [op("observation", obs_id, "delete", {}, client_version=1)])
    assert res["synced"] == 1

    seen, cursor = [], {}
    for _ in range(50):
        r = await client.post("/api/v1/sync/pull", json={"limit": 1, **cursor}, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        seen.extend(body["changes"])
        if not body["has_more"]:
            break
        cursor = {
            "cursor_updated_at": body["next_cursor_updated_at"],
            "cursor_entity_type": body["next_cursor_entity_type"],
            "cursor_entity_id": body["next_cursor_entity_id"],
        }

    keys = [(c["entity_type"], c["entity_id"]) for c in seen]
    assert len(keys) == len(set(keys)), "pagination returned duplicates"
    by_id = {c["entity_id"]: c for c in seen}
    assert by_id[str(obs_id)]["operation_type"] == "delete"
    assert by_id[str(obs_id)]["payload"]["deleted"] is True
    assert by_id[str(visit_id)]["operation_type"] == "update"
    assert any(c["entity_type"] == "mentor_task" for c in seen), "school-less tasks must sync"
    # Mentor B's data never appears
    assert all(c["entity_type"] != "school" or c["entity_id"] == str(world["school_a"]) for c in seen)

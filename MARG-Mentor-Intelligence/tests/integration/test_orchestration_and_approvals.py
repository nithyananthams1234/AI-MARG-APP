"""Orchestrator idempotency, policy enforcement, failure handling and the approval workflow."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.agents.base_agent import AgentContext, Analysis, BaseAgent, ProposedAction
from app.agents.task_agent import TaskPrioritisationInput
from app.core.agent_registry import AgentRegistry, default_registry
from app.core.approval_engine import ProposalStateError
from app.core.orchestrator import ExecutionFailed, IdempotencyKeyConflict, Orchestrator
from app.models import domain as m
from app.models.engine import AuditLog, Proposal
from app.security.permissions import PermissionDenied, Principal, PrincipalKind
from tests.conftest import FIXED_NOW, MENTOR, build_container


async def run(c, agent, principal=MENTOR, **params):
    return await c.orchestrator.run(agent, {"mentor_ref": "MEN-001", **params}, principal)


async def test_duplicate_request_is_replayed_not_reexecuted(container):
    first = await run(container, "schedule_intelligence")
    second = await run(container, "schedule_intelligence")
    assert second.replayed and second.execution_id == first.execution_id
    async with container.db.session() as s:
        assert len((await s.execute(select(Proposal))).scalars().all()) == len(first.result["proposals"])


async def test_changed_records_produce_a_new_execution(container):
    first = await run(container, "task_intelligence")
    async with container.db.session() as s:
        (await s.get(m.Task, "TSK-007")).estimated_minutes = 45
        await s.commit()
    second = await run(container, "task_intelligence")
    assert not second.replayed and second.execution_id != first.execution_id


async def test_explicit_idempotency_key_reuse_with_different_input_conflicts(container):
    await container.orchestrator.run(
        "task_intelligence", {"mentor_ref": "MEN-001"}, MENTOR, idempotency_key="k1"
    )
    with pytest.raises(IdempotencyKeyConflict):
        await container.orchestrator.run(
            "task_intelligence",
            {"mentor_ref": "MEN-001", "include_closed": True},
            MENTOR,
            idempotency_key="k1",
        )


async def test_cross_mentor_access_denied_but_supervisor_allowed(container):
    with pytest.raises(PermissionDenied):
        await container.orchestrator.run("task_intelligence", {"mentor_ref": "MEN-002"}, MENTOR)
    sup = Principal("SUP-01", roles=frozenset({"dev_supervisor"}))
    v = await container.orchestrator.run("task_intelligence", {"mentor_ref": "MEN-002"}, sup)
    assert v.status.value == "completed"


class RogueAgent(BaseAgent[TaskPrioritisationInput]):
    """Tries to propose an action it is not allowed to propose."""

    agent_id = "rogue"
    description = "test"
    input_model = TaskPrioritisationInput
    allowed_actions = frozenset({"update_task_due_date"})

    def analyse(self, ctx: AgentContext, inp) -> Analysis:
        return Analysis(
            facts={},
            proposals=[
                ProposedAction(
                    action_type="send_teacher_message",
                    target_type="teacher",
                    target_ref="TCH-001",
                    payload={"body": "hi"},
                    rationale="not allowed",
                ),
                ProposedAction(
                    action_type="delete_everything",
                    target_type="db",
                    target_ref=None,
                    payload={},
                    rationale="x",
                ),
            ],
        )


async def test_policy_rejects_unauthorised_proposals(settings, db):
    c = build_container(settings, db)
    registry = AgentRegistry([*[default_registry().get(a) for a in ("task_intelligence",)], RogueAgent()])
    orch = Orchestrator(c.db, c.adapter, c.provider, settings, registry, clock=lambda: FIXED_NOW)
    v = await orch.run("rogue", {"mentor_ref": "MEN-001"}, MENTOR)
    assert v.result["proposals"] == []
    async with db.session() as s:
        violations = (
            (await s.execute(select(AuditLog).where(AuditLog.action == "policy_violation"))).scalars().all()
        )
    assert len(violations) == 2


async def test_failed_execution_recorded_and_retryable(container):
    with pytest.raises(ExecutionFailed) as info:
        await run(container, "teacher_communication", followup_ref="FU-404")
    view = await container.orchestrator.get_execution(info.value.execution_id, MENTOR)
    assert view.status.value == "failed" and view.error["code"] == "invalid_request"
    with pytest.raises(ExecutionFailed):
        await container.orchestrator.retry(info.value.execution_id, MENTOR)
    view = await container.orchestrator.get_execution(info.value.execution_id, MENTOR)
    assert view.attempts == 2


# ----------------------------------------------------------------------------- approvals
async def proposals_from_schedule(container):
    v = await run(container, "schedule_intelligence")
    assert v.result["proposals"], "demo data should yield a reschedule proposal"
    return v.result["proposals"]


async def test_approving_reschedule_executes_and_updates_record(container):
    p = (await proposals_from_schedule(container))[0]
    result = await container.approvals.approve(MENTOR, uuid.UUID(p["proposal_id"]), "OK")
    assert result["status"] == "executed"
    assert result["decisions"][0]["approver_ref"] == "MEN-001"
    async with container.db.session() as s:
        visit = await s.get(m.SchoolVisit, p["payload"]["visit_ref"])
    assert visit.scheduled_start == datetime.fromisoformat(p["payload"]["new_start"])


async def test_reject_and_double_decision(container):
    p = (await proposals_from_schedule(container))[0]
    pid = uuid.UUID(p["proposal_id"])
    assert (await container.approvals.reject(MENTOR, pid, "No"))["status"] == "rejected"
    with pytest.raises(ProposalStateError):
        await container.approvals.approve(MENTOR, pid)


async def test_only_owner_or_supervisor_humans_can_decide(container):
    pid = uuid.UUID((await proposals_from_schedule(container))[0]["proposal_id"])
    with pytest.raises(PermissionDenied):
        await container.approvals.approve(Principal("MEN-002"), pid)
    with pytest.raises(PermissionDenied):  # an automated/system principal cannot approve
        await container.approvals.approve(Principal("MEN-001", kind=PrincipalKind.system), pid)
    sup = Principal("SUP-01", roles=frozenset({"dev_supervisor"}))
    assert (await container.approvals.approve(sup, pid))["status"] == "executed"


async def test_tampered_payload_is_refused(container):
    pid = uuid.UUID((await proposals_from_schedule(container))[0]["proposal_id"])
    async with container.db.session() as s:
        row = await s.get(Proposal, pid)
        row.payload = row.payload | {"new_start": "2030-01-01T10:00:00+05:30"}
        await s.commit()
    with pytest.raises(ProposalStateError, match="integrity"):
        await container.approvals.approve(MENTOR, pid)


async def test_pending_proposals_expire(settings, db):
    c = build_container(settings, db)
    pid = uuid.UUID((await proposals_from_schedule(c))[0]["proposal_id"])
    later = build_container(settings, db, now=FIXED_NOW + timedelta(hours=settings.proposal_ttl_hours + 1))
    with pytest.raises(ProposalStateError):
        await later.approvals.approve(MENTOR, pid)
    assert (await later.approvals.get(MENTOR, pid))["status"] == "expired"


async def test_teacher_message_never_sent_by_engine(container):
    v = await run(container, "teacher_communication", followup_ref="FU-008")
    pid = uuid.UUID(v.result["proposals"][0]["proposal_id"])
    approved = await container.approvals.approve(MENTOR, pid)
    assert approved["status"] == "approved"  # awaiting delivery by the MARG application
    assert approved["execution_result"] is None
    done = await container.approvals.report_external_result(MENTOR, pid, True, "Delivered by MARG app")
    assert done["status"] == "executed"


async def test_schedule_visit_proposal_creates_planned_visit(container):
    v = await run(container, "school_visit_planning")
    proposals = [p for p in v.result["proposals"] if p["action_type"] == "schedule_visit"]
    assert proposals
    result = await container.approvals.approve(MENTOR, uuid.UUID(proposals[0]["proposal_id"]))
    assert result["status"] == "executed"
    async with container.db.session() as s:
        visit = await s.get(m.SchoolVisit, result["execution_result"]["visit_ref"])
    assert visit.status == "planned"

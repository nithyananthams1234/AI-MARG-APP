"""Approval engine: human decisions on agent proposals and controlled execution.

- Only a human principal (the owning mentor or a configured supervisor role) can decide.
- An approval is bound to the SHA-256 hash of the exact payload; tampered payloads are refused.
- Pending proposals expire after PROPOSAL_TTL_HOURS.
- Internal actions are executed through the data adapter only after approval, and marked
  ``executed`` only once the adapter confirms the change.
- External actions (sending teacher messages) are never executed by the engine: they stay
  ``approved`` until the MARG application reports the delivery result.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.config import Settings
from app.core.hashing import canonical_hash
from app.core.orchestrator import proposal_summary
from app.db.session import Database
from app.integrations.base_adapter import MentorDataAdapter
from app.models.engine import Approval, AuditLog, Proposal
from app.schemas.common import ProposalStatus
from app.security.permissions import Principal, PrincipalKind, ensure_can_approve, ensure_mentor_access
from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)


class ProposalStateError(Exception):
    code = "invalid_proposal_state"
    http_status = 409


class ApprovalEngine:
    def __init__(
        self,
        db: Database,
        adapter: MentorDataAdapter,
        settings: Settings,
        clock: Callable[[], datetime] = utcnow,
    ):
        self.db, self.adapter, self.settings, self.clock = db, adapter, settings, clock

    # ------------------------------------------------------------------ queries
    async def list(
        self, principal: Principal, mentor_ref: str, status: ProposalStatus | None = None
    ) -> list[dict]:
        ensure_mentor_access(principal, mentor_ref, self.settings.supervisor_roles)
        await self._expire_due(mentor_ref)
        async with self.db.session() as s:
            stmt = (
                select(Proposal).where(Proposal.mentor_ref == mentor_ref).order_by(Proposal.created_at.desc())
            )
            if status:
                stmt = stmt.where(Proposal.status == status.value)
            rows = (await s.execute(stmt)).scalars().all()
        return [
            proposal_summary(r) | {"created_at": r.created_at.isoformat(), "agent_id": r.agent_id}
            for r in rows
        ]

    async def get(self, principal: Principal, proposal_id: uuid.UUID) -> dict:
        async with self.db.session() as s:
            row = await self._load(s, proposal_id)
            ensure_mentor_access(principal, row.mentor_ref, self.settings.supervisor_roles)
            self._expire_if_due(row)
            await s.commit()
            approvals = (
                (await s.execute(select(Approval).where(Approval.proposal_id == proposal_id))).scalars().all()
            )
            return self._view(row) | {
                "decisions": [
                    {
                        "decision": a.decision,
                        "approver_ref": a.approver_ref,
                        "decided_at": a.decided_at.isoformat(),
                        "note": a.note,
                        "result_status": a.result_status,
                    }
                    for a in approvals
                ]
            }

    # ------------------------------------------------------------------ decisions
    async def approve(self, principal: Principal, proposal_id: uuid.UUID, note: str | None = None) -> dict:
        async with self.db.session() as s:
            row = await self._load(s, proposal_id, for_update=True)
            ensure_can_approve(principal, row.mentor_ref, self.settings.supervisor_roles)
            self._expire_if_due(row)
            if row.status != ProposalStatus.pending.value:
                await s.commit()
                raise ProposalStateError(f"Proposal is {row.status}; only pending proposals can be approved")
            if canonical_hash(row.payload) != row.payload_hash:
                self._audit(s, principal, "approval_refused", row, "integrity_failure")
                await s.commit()
                raise ProposalStateError("Proposal payload integrity check failed; approval refused")
            now = self.clock()
            row.status = ProposalStatus.approved.value
            row.updated_at = now
            approval = Approval(
                proposal_id=row.id,
                decision="approved",
                approver_ref=principal.actor_ref,
                approver_roles=sorted(principal.roles),
                payload_hash=row.payload_hash,
                original_proposal=proposal_summary(row),
                note=note,
                decided_at=now,
            )
            s.add(approval)
            self._audit(s, principal, "proposal_approved", row, "approved")
            await s.commit()
            approval_id = approval.id

        if not row.requires_external_execution:
            await self._execute(proposal_id, approval_id, principal)
        return await self.get(principal, proposal_id)

    async def reject(self, principal: Principal, proposal_id: uuid.UUID, note: str | None = None) -> dict:
        async with self.db.session() as s:
            row = await self._load(s, proposal_id, for_update=True)
            ensure_can_approve(principal, row.mentor_ref, self.settings.supervisor_roles)
            self._expire_if_due(row)
            if row.status != ProposalStatus.pending.value:
                await s.commit()
                raise ProposalStateError(f"Proposal is {row.status}; only pending proposals can be rejected")
            now = self.clock()
            row.status = ProposalStatus.rejected.value
            row.updated_at = now
            s.add(
                Approval(
                    proposal_id=row.id,
                    decision="rejected",
                    approver_ref=principal.actor_ref,
                    approver_roles=sorted(principal.roles),
                    payload_hash=row.payload_hash,
                    original_proposal=proposal_summary(row),
                    note=note,
                    decided_at=now,
                    result_status=ProposalStatus.rejected.value,
                )
            )
            self._audit(s, principal, "proposal_rejected", row, "rejected")
            await s.commit()
        return await self.get(principal, proposal_id)

    async def report_external_result(
        self, principal: Principal, proposal_id: uuid.UUID, success: bool, detail: str | None
    ) -> dict:
        """Called by the MARG application after it delivers (or fails to deliver) an approved external action."""
        async with self.db.session() as s:
            row = await self._load(s, proposal_id, for_update=True)
            ensure_mentor_access(principal, row.mentor_ref, self.settings.supervisor_roles)
            if not row.requires_external_execution:
                raise ProposalStateError("This proposal is executed by the engine, not externally")
            if row.status != ProposalStatus.approved.value:
                raise ProposalStateError(f"Proposal is {row.status}; only approved proposals can be reported")
            now = self.clock()
            row.status = (ProposalStatus.executed if success else ProposalStatus.execution_failed).value
            row.executed_at = now if success else None
            row.updated_at = now
            row.execution_result = {
                "reported_by": principal.actor_ref,
                "success": success,
                "detail": detail,
                "reported_at": now.isoformat(),
            }
            self._audit(s, principal, "external_result_reported", row, row.status)
            await s.commit()
        return await self.get(principal, proposal_id)

    # ------------------------------------------------------------------ execution
    async def _execute(self, proposal_id: uuid.UUID, approval_id: uuid.UUID, principal: Principal) -> None:
        async with self.db.session() as s:
            row = await self._load(s, proposal_id)
            action, payload, mentor_ref = row.action_type, dict(row.payload), row.mentor_ref
        try:
            result = await self._dispatch(action, mentor_ref, payload)
            status, executed_at = ProposalStatus.executed, self.clock()
        except Exception as exc:  # execution failure is recorded, never hidden
            logger.warning(
                "proposal_execution_failed", extra={"proposal_id": str(proposal_id), "action": action}
            )
            result, status, executed_at = {"error": str(exc)[:500]}, ProposalStatus.execution_failed, None
        async with self.db.session() as s:
            row = await self._load(s, proposal_id, for_update=True)
            row.status, row.execution_result, row.executed_at = status.value, result, executed_at
            row.updated_at = self.clock()
            approval = await s.get(Approval, approval_id)
            if approval is not None:
                approval.result_status = status.value
            self._audit(s, principal, "proposal_executed", row, status.value)
            await s.commit()

    async def _dispatch(self, action: str, mentor_ref: str, payload: dict[str, Any]) -> dict:
        if action == "reschedule_visit":
            return await self.adapter.reschedule_visit(
                mentor_ref,
                payload["visit_ref"],
                datetime.fromisoformat(payload["new_start"]),
                datetime.fromisoformat(payload["new_end"]),
            )
        if action == "schedule_visit":
            return await self.adapter.schedule_visit(
                mentor_ref,
                payload["school_ref"],
                datetime.fromisoformat(payload["start"]),
                datetime.fromisoformat(payload["end"]),
                payload["purpose"],
            )
        if action == "update_task_due_date":
            return await self.adapter.update_task_due_date(
                mentor_ref, payload["task_ref"], datetime.fromisoformat(payload["due_at"])
            )
        raise ValueError(f"No internal executor for action {action!r}")

    # ------------------------------------------------------------------ helpers
    @staticmethod
    async def _load(s: Any, proposal_id: uuid.UUID, for_update: bool = False) -> Proposal:
        stmt = select(Proposal).where(Proposal.id == proposal_id)
        if for_update:
            stmt = stmt.with_for_update()
        row = (await s.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise LookupError("Proposal not found")
        return row

    def _expire_if_due(self, row: Proposal) -> None:
        if row.status == ProposalStatus.pending.value and row.expires_at <= self.clock():
            row.status = ProposalStatus.expired.value
            row.updated_at = self.clock()

    async def _expire_due(self, mentor_ref: str) -> None:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(Proposal).where(
                        Proposal.mentor_ref == mentor_ref, Proposal.status == ProposalStatus.pending.value
                    )
                )
            ).scalars()
            for row in rows:
                self._expire_if_due(row)
            await s.commit()

    def _audit(self, s: Any, principal: Principal, action: str, row: Proposal, outcome: str) -> None:
        s.add(
            AuditLog(
                occurred_at=self.clock(),
                actor_ref=principal.actor_ref,
                action=action,
                target_type="proposal",
                target_ref=str(row.id),
                outcome=outcome,
                detail={
                    "action_type": row.action_type,
                    "actor_kind": principal.kind.value
                    if isinstance(principal.kind, PrincipalKind)
                    else str(principal.kind),
                },
            )
        )

    @staticmethod
    def _view(row: Proposal) -> dict:
        return proposal_summary(row) | {
            "agent_id": row.agent_id,
            "mentor_ref": row.mentor_ref,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "execution_id": str(row.execution_id) if row.execution_id else None,
            "execution_result": row.execution_result,
            "executed_at": row.executed_at.isoformat() if row.executed_at else None,
            "delivery_note": "Delivery is performed by the MARG application after approval; the engine never sends "
            "messages."
            if row.requires_external_execution
            else None,
        }

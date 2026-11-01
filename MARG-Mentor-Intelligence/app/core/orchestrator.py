"""Mentor Intelligence Orchestrator.

Pipeline for every request or event:
validate input -> permission check -> load context through the adapter -> idempotency check ->
agent (deterministic analysis + gated Claude reasoning + validation) -> policy check on proposals ->
persist drafts, proposals and plans -> record execution history.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.agents.base_agent import AgentContext, AgentOutcome
from app.config import Settings
from app.core.actions import ACTIONS
from app.core.agent_registry import AgentRegistry
from app.core.hashing import canonical_hash
from app.db.session import Database
from app.integrations.base_adapter import MentorDataAdapter
from app.models.engine import AuditLog, Execution, ExecutionStep, MessageDraft, Plan, Proposal
from app.monitoring.logging_config import execution_id_var
from app.providers.base import LLMProvider
from app.schemas.common import AIJobStatus, ProposalStatus
from app.security.permissions import Principal, ensure_mentor_access
from app.utils.datetime_utils import local_date, utcnow

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    code = "orchestrator_error"
    http_status = 400


class DuplicateExecutionInProgress(OrchestratorError):
    code = "duplicate_in_progress"
    http_status = 409


class IdempotencyKeyConflict(OrchestratorError):
    code = "idempotency_key_conflict"
    http_status = 409


class ExecutionFailed(OrchestratorError):
    code = "execution_failed"
    http_status = 422

    def __init__(self, message: str, execution_id: uuid.UUID, error_code: str):
        super().__init__(message)
        self.execution_id = execution_id
        self.error_code = error_code


class ExecutionView(BaseModel):
    execution_id: uuid.UUID
    agent_id: str
    mentor_ref: str
    status: AIJobStatus
    ai_status: str | None
    replayed: bool = False
    attempts: int
    trigger: str
    created_at: datetime
    finished_at: datetime | None
    error: dict[str, str] | None = None
    result: dict[str, Any] | None = None
    steps: list[dict[str, Any]] | None = None


def proposal_summary(p: Proposal) -> dict[str, Any]:
    return {
        "proposal_id": str(p.id),
        "action_type": p.action_type,
        "autonomy_level": p.autonomy_level,
        "target_type": p.target_type,
        "target_ref": p.target_ref,
        "payload": p.payload,
        "rationale": p.rationale,
        "status": p.status,
        "requires_external_execution": p.requires_external_execution,
        "expires_at": p.expires_at.isoformat(),
    }


class Orchestrator:
    def __init__(
        self,
        db: Database,
        adapter: MentorDataAdapter,
        provider: LLMProvider,
        settings: Settings,
        registry: AgentRegistry,
        clock: Callable[[], datetime] = utcnow,
    ):
        self.db, self.adapter, self.provider, self.settings, self.registry, self.clock = (
            db,
            adapter,
            provider,
            settings,
            registry,
            clock,
        )

    async def run(
        self,
        agent_id: str,
        params: dict[str, Any],
        principal: Principal,
        *,
        trigger: str = "api",
        trigger_ref: str | None = None,
        idempotency_key: str | None = None,
        is_retry: bool = False,
    ) -> ExecutionView:
        agent = self.registry.get(agent_id)
        inp = agent.input_model.model_validate(params)  # raises ValidationError -> 422
        ensure_mentor_access(principal, inp.mentor_ref, self.settings.supervisor_roles)
        now = self.clock()
        snapshot = await self.adapter.get_mentor_snapshot(inp.mentor_ref)
        request = inp.model_dump(mode="json")
        input_hash = canonical_hash(
            {
                "agent": agent_id,
                "version": agent.version,
                "request": request,
                "snapshot": snapshot.model_dump(mode="json"),
                "local_date": str(local_date(now, self.settings.tz)),
            }
        )
        key = idempotency_key or f"{agent_id}:{inp.mentor_ref}:{input_hash[:40]}"

        explicit_key = idempotency_key is not None and not is_retry
        execution = await self._claim(
            key,
            agent_id,
            agent.version,
            inp.mentor_ref,
            trigger,
            trigger_ref,
            principal,
            input_hash,
            request,
            now,
            explicit_key,
        )
        if isinstance(execution, ExecutionView):
            return execution  # replay of a completed execution
        token = execution_id_var.set(str(execution.id))
        try:
            await self._step(
                execution.id,
                "context_loaded",
                "completed",
                {"data_source": snapshot.data_source.value, "is_demo": snapshot.is_demo},
            )
            ctx = AgentContext(
                snapshot=snapshot,
                now=now,
                settings=self.settings,
                provider=self.provider,
                execution_id=str(execution.id),
            )
            try:
                outcome = await agent.run(ctx, inp)
            except (LookupError, ValueError, ValidationError) as exc:
                await self._fail(execution.id, "invalid_request", str(exc))
                raise ExecutionFailed(str(exc), execution.id, "invalid_request") from exc
            except Exception as exc:
                logger.exception("agent_failed", extra={"agent": agent_id})
                await self._fail(execution.id, "agent_error", "The agent failed; see server logs")
                raise ExecutionFailed("The agent failed unexpectedly", execution.id, "agent_error") from exc

            await self._step(execution.id, "deterministic_analysis", "completed", None)
            await self._step(execution.id, "ai_reasoning", outcome.ai_status.value, outcome.ai_meta or None)
            result = await self._persist_outcome(execution.id, agent.allowed_actions, outcome, principal, now)
            async with self.db.session() as s:
                row = await s.get(Execution, execution.id)
                assert row is not None
                row.status = AIJobStatus.completed.value
                row.result = result
                row.ai_status = outcome.ai_status.value
                row.data_source = outcome.data_source
                row.finished_at = self.clock()
                row.error_code = row.error_message = None
                await s.commit()
            await self._step(execution.id, "completed", "completed", None)
            return await self.get_execution(execution.id, principal)
        finally:
            execution_id_var.reset(token)

    # ------------------------------------------------------------------ internals
    async def _claim(
        self,
        key: str,
        agent_id: str,
        version: str,
        mentor_ref: str,
        trigger: str,
        trigger_ref: str | None,
        principal: Principal,
        input_hash: str,
        request: dict,
        now: datetime,
        explicit_key: bool,
    ) -> Execution | ExecutionView:
        async with self.db.session() as s:
            existing = (
                await s.execute(select(Execution).where(Execution.idempotency_key == key))
            ).scalar_one_or_none()
            if existing is not None:
                if explicit_key and (existing.agent_id != agent_id or existing.request != request):
                    raise IdempotencyKeyConflict("Idempotency key was already used for a different request")
                if existing.status == AIJobStatus.completed.value:
                    view = await self.get_execution(existing.id, principal)
                    view.replayed = True
                    return view
                if existing.status in (AIJobStatus.processing.value, AIJobStatus.queued.value):
                    raise DuplicateExecutionInProgress("An identical execution is already in progress")
                existing.status = AIJobStatus.processing.value  # failed/cancelled: safe retry
                existing.attempts += 1
                existing.started_at = now
                existing.input_hash, existing.request = input_hash, request
                await s.commit()
                return existing
            row = Execution(
                id=uuid.uuid4(),
                idempotency_key=key,
                agent_id=agent_id,
                agent_version=version,
                mentor_ref=mentor_ref,
                trigger=trigger,
                trigger_ref=trigger_ref,
                actor_ref=principal.actor_ref,
                status=AIJobStatus.processing.value,
                input_hash=input_hash,
                request=request,
                attempts=1,
                created_at=now,
                started_at=now,
            )
            s.add(row)
            try:
                await s.commit()
            except IntegrityError:
                raise DuplicateExecutionInProgress("An identical execution is already in progress") from None
            return row

    async def _persist_outcome(
        self,
        execution_id: uuid.UUID,
        allowed: frozenset[str],
        outcome: AgentOutcome,
        principal: Principal,
        now: datetime,
    ) -> dict[str, Any]:
        recorded: list[dict[str, Any]] = []
        rejected: list[str] = []
        async with self.db.session() as s:
            for draft in outcome.drafts:
                s.add(
                    MessageDraft(
                        id=draft.draft_id,
                        execution_id=execution_id,
                        mentor_ref=outcome.mentor_ref,
                        teacher_ref=draft.teacher_ref,
                        followup_ref=draft.followup_ref,
                        purpose=draft.purpose,
                        language=draft.language,
                        body=draft.body,
                        generated_by=draft.generated_by,
                        created_at=now,
                    )
                )
            for p in outcome.proposals:
                spec = ACTIONS.get(p.action_type)
                if spec is None or p.action_type not in allowed:
                    rejected.append(p.action_type)
                    s.add(
                        AuditLog(
                            occurred_at=now,
                            actor_ref=f"agent:{outcome.agent_id}",
                            action="policy_violation",
                            target_type="proposal",
                            target_ref=p.action_type,
                            outcome="rejected",
                            detail={"reason": "action not allowed for this agent"},
                        )
                    )
                    continue
                row = Proposal(
                    id=uuid.uuid4(),
                    execution_id=execution_id,
                    mentor_ref=outcome.mentor_ref,
                    agent_id=outcome.agent_id,
                    action_type=p.action_type,
                    autonomy_level=spec.level.value,
                    target_type=p.target_type,
                    target_ref=p.target_ref,
                    payload=p.payload,
                    payload_hash=canonical_hash(p.payload),
                    rationale=p.rationale,
                    status=ProposalStatus.pending.value,
                    requires_external_execution=spec.external,
                    created_at=now,
                    updated_at=now,
                    expires_at=now + timedelta(hours=self.settings.proposal_ttl_hours),
                )
                s.add(row)
                recorded.append(proposal_summary(row))
            if outcome.plan is not None:
                s.add(
                    Plan(
                        execution_id=execution_id,
                        mentor_ref=outcome.mentor_ref,
                        plan_type=outcome.plan.plan_type,
                        period_start=outcome.plan.period_start,
                        period_end=outcome.plan.period_end,
                        content={
                            "facts": outcome.facts,
                            "ai_insights": outcome.ai_insights,
                            "ai_status": outcome.ai_status.value,
                        },
                        created_at=now,
                    )
                )
            await s.commit()
        await self._step(
            execution_id,
            "policy_checked",
            "completed",
            {"proposals_recorded": len(recorded), "proposals_rejected": rejected},
        )
        result = outcome.model_dump(mode="json", exclude={"proposals", "plan", "drafts"})
        result["proposals"] = recorded
        result["drafts"] = [d.model_dump(mode="json") for d in outcome.drafts]
        return result

    async def _step(self, execution_id: uuid.UUID, step: str, status: str, detail: dict | None) -> None:
        async with self.db.session() as s:
            s.add(
                ExecutionStep(
                    execution_id=execution_id,
                    step=step,
                    status=status,
                    detail=detail,
                    created_at=self.clock(),
                )
            )
            await s.commit()

    async def _fail(self, execution_id: uuid.UUID, code: str, message: str) -> None:
        async with self.db.session() as s:
            row = await s.get(Execution, execution_id)
            if row is not None:
                row.status = AIJobStatus.failed.value
                row.error_code, row.error_message = code, message[:2000]
                row.finished_at = self.clock()
                await s.commit()
        await self._step(execution_id, "failed", "failed", {"error_code": code})

    # ------------------------------------------------------------------ queries
    async def get_execution(
        self, execution_id: uuid.UUID, principal: Principal, include_steps: bool = True
    ) -> ExecutionView:
        async with self.db.session() as s:
            row = await s.get(Execution, execution_id)
            if row is None:
                raise LookupError("Execution not found")
            ensure_mentor_access(principal, row.mentor_ref, self.settings.supervisor_roles)
            steps = None
            if include_steps:
                rows = (
                    (
                        await s.execute(
                            select(ExecutionStep)
                            .where(ExecutionStep.execution_id == execution_id)
                            .order_by(ExecutionStep.created_at)
                        )
                    )
                    .scalars()
                    .all()
                )
                steps = [
                    {"step": r.step, "status": r.status, "detail": r.detail, "at": r.created_at.isoformat()}
                    for r in rows
                ]
            result = row.result
            if result and result.get("proposals"):
                ids = [uuid.UUID(p["proposal_id"]) for p in result["proposals"]]
                current = {
                    str(p.id): p.status
                    for p in (await s.execute(select(Proposal).where(Proposal.id.in_(ids)))).scalars().all()
                }
                result = result | {
                    "proposals": [
                        p | {"status": current.get(p["proposal_id"], p["status"])}
                        for p in result["proposals"]
                    ]
                }
            return ExecutionView(
                execution_id=row.id,
                agent_id=row.agent_id,
                mentor_ref=row.mentor_ref,
                status=AIJobStatus(row.status),
                ai_status=row.ai_status,
                attempts=row.attempts,
                trigger=row.trigger,
                created_at=row.created_at,
                finished_at=row.finished_at,
                error={"code": row.error_code, "message": row.error_message or ""}
                if row.error_code
                else None,
                result=result,
                steps=steps,
            )

    async def list_executions(
        self, principal: Principal, mentor_ref: str, limit: int = 50
    ) -> list[ExecutionView]:
        ensure_mentor_access(principal, mentor_ref, self.settings.supervisor_roles)
        async with self.db.session() as s:
            rows = (
                (
                    await s.execute(
                        select(Execution)
                        .where(Execution.mentor_ref == mentor_ref)
                        .order_by(Execution.created_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [
            ExecutionView(
                execution_id=r.id,
                agent_id=r.agent_id,
                mentor_ref=r.mentor_ref,
                status=AIJobStatus(r.status),
                ai_status=r.ai_status,
                attempts=r.attempts,
                trigger=r.trigger,
                created_at=r.created_at,
                finished_at=r.finished_at,
                error={"code": r.error_code, "message": r.error_message or ""} if r.error_code else None,
            )
            for r in rows
        ]

    async def retry(self, execution_id: uuid.UUID, principal: Principal) -> ExecutionView:
        async with self.db.session() as s:
            row = await s.get(Execution, execution_id)
            if row is None:
                raise LookupError("Execution not found")
            ensure_mentor_access(principal, row.mentor_ref, self.settings.supervisor_roles)
            if row.status != AIJobStatus.failed.value:
                raise OrchestratorError("Only failed executions can be retried")
            agent_id, request, key, trigger = row.agent_id, row.request, row.idempotency_key, row.trigger
        return await self.run(
            agent_id, request, principal, trigger=trigger, idempotency_key=key, is_retry=True
        )

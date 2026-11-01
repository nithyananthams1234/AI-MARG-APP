"""
Apply offline (pushed) operations to the business tables.

Principles
----------
* Same rules as online: every operation is executed by the *existing* REST
  route handler for that entity/action, inside the mentor's access-scoped
  session. Status transitions, reference validation, school scoping and
  approval rules are therefore identical online and offline.
* Optimistic concurrency: updates/deletes carry ``client_version`` (the
  version the device last saw). If the server row has moved on, the
  operation is NOT applied and is reported as ``conflict`` with
  ``server_version`` so the device can re-pull and let the mentor decide.
  Newer server data is never silently overwritten.
* Client-generated UUIDs: creates use ``entity_id`` as the primary key so
  the device can reference the record in later operations before syncing.
  Re-sending a create for a record that already exists (same owner) is
  treated as already applied.
* Partial failure: each operation succeeds or fails on its own; the batch
  response reports a status per operation.

Operation contract (``payload``)
--------------------------------
create : the entity's Create schema fields.
update : optional ``"_action"`` selects the handler; remaining keys are the
         schema fields for that action. Actions per entity are listed in
         ``ENTITY_HANDLERS`` (``update`` is the default).
delete : empty payload.
"""

from __future__ import annotations

import contextvars
import inspect
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.action_plan_steps import router as steps_r
from app.action_plans import router as plans_r
from app.auth.access import BYPASS_SCOPE
from app.follow_ups import router as followups_r
from app.learning_gaps import router as gaps_r
from app.mentor_tasks import router as tasks_r
from app.models.action_plan import ActionPlan
from app.models.action_plan_step import ActionPlanStep
from app.models.follow_up import FollowUp
from app.models.identity import User
from app.models.learning_gap import LearningGap
from app.models.mentor_task import MentorTask
from app.models.observation import Observation
from app.models.observation_finding import ObservationFinding
from app.models.recommendation import Recommendation
from app.models.school_visits import SchoolVisit
from app.models.sync_operation import SyncOperation
from app.observation_findings import router as findings_r
from app.observations import router as observations_r
from app.recommendations import router as recs_r
from app.school_visits import router as visits_r


@dataclass(frozen=True)
class EntityHandlers:
    model: type
    create: Callable | None
    actions: dict[str, Callable]
    delete: Callable | None


# Entities a mentor works with in the field (offline-capable).
ENTITY_HANDLERS: dict[str, EntityHandlers] = {
    "school_visit": EntityHandlers(
        SchoolVisit,
        visits_r.create_school_visit,
        {"update": visits_r.update_school_visit, "status": visits_r.update_school_visit_status},
        None,
    ),
    "observation": EntityHandlers(
        Observation,
        observations_r.create_observation,
        {"update": observations_r.update_observation, "status": observations_r.update_observation_status},
        observations_r.delete_observation,
    ),
    "observation_finding": EntityHandlers(
        ObservationFinding,
        findings_r.create_finding,
        {"update": findings_r.update_finding, "decision": findings_r.decide_finding},
        findings_r.delete_finding,
    ),
    "learning_gap": EntityHandlers(
        LearningGap,
        gaps_r.create_learning_gap,
        {"update": gaps_r.update_learning_gap, "status": gaps_r.update_learning_gap_status},
        gaps_r.delete_learning_gap,
    ),
    "recommendation": EntityHandlers(
        Recommendation,
        recs_r.create_recommendation,
        {"update": recs_r.update_recommendation, "decision": recs_r.decide_recommendation},
        recs_r.delete_recommendation,
    ),
    "action_plan": EntityHandlers(
        ActionPlan,
        plans_r.create_action_plan,
        {"update": plans_r.update_action_plan, "status": plans_r.update_action_plan_status},
        plans_r.delete_action_plan,
    ),
    "action_plan_step": EntityHandlers(
        ActionPlanStep,
        steps_r.create_action_plan_step,
        {"update": steps_r.update_action_plan_step, "status": steps_r.update_action_plan_step_status},
        steps_r.delete_action_plan_step,
    ),
    "follow_up": EntityHandlers(
        FollowUp,
        followups_r.create_follow_up,
        {
            "teacher_response": followups_r.submit_teacher_response,
            "evidence": followups_r.submit_follow_up_evidence,
            "mentor_decision": followups_r.mentor_review_follow_up,
            "close": followups_r.close_follow_up,
        },
        followups_r.delete_follow_up,
    ),
    "mentor_task": EntityHandlers(
        MentorTask,
        tasks_r.create_mentor_task,
        {"update": tasks_r.update_mentor_task, "status": tasks_r.update_mentor_task_status},
        tasks_r.delete_mentor_task,
    ),
}


# --------------------------------------------------------------------------
# Client-generated primary keys for offline creates
# --------------------------------------------------------------------------
_client_id: contextvars.ContextVar[tuple[type, uuid.UUID] | None] = contextvars.ContextVar(
    "marg_sync_client_id", default=None
)


@event.listens_for(Session, "before_flush")
def _assign_client_id(session: Session, flush_context, instances) -> None:
    target = _client_id.get()
    if target is None:
        return
    model, entity_id = target
    new = [o for o in session.new if type(o) is model]
    if len(new) == 1:
        new[0].id = entity_id
        _client_id.set(None)


# --------------------------------------------------------------------------
# Handler invocation
# --------------------------------------------------------------------------
async def _call(handler: Callable, db: AsyncSession, user: User, entity_id: uuid.UUID | None, payload: dict | None):
    """Invoke a FastAPI route function directly with resolved arguments."""
    kwargs: dict[str, Any] = {}
    for name, param in inspect.signature(handler, eval_str=True).parameters.items():
        ann = param.annotation
        if name == "db":
            kwargs[name] = db
        elif name == "current_user":
            kwargs[name] = user
        elif ann is uuid.UUID or ann == "UUID":
            kwargs[name] = entity_id
        elif inspect.isclass(ann) and issubclass(ann, BaseModel):
            kwargs[name] = ann.model_validate(payload or {})
        elif param.default is not inspect.Parameter.empty:
            continue
        else:
            raise RuntimeError(f"Cannot resolve parameter {name} for {handler.__name__}")
    return await handler(**kwargs)


def _error_text(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, str):
        return detail
    return str(detail)[:500]


async def _load(db: AsyncSession, model: type, entity_id: uuid.UUID):
    # Scoped load (no bypass): out-of-scope rows behave as not found.
    return (
        await db.execute(select(model).where(model.id == entity_id))
    ).scalar_one_or_none()


async def _apply(db: AsyncSession, user: User, op: SyncOperation) -> tuple[str, int | None, str | None]:
    """Returns (status, server_version, error_message)."""
    spec = ENTITY_HANDLERS.get(op.entity_type)
    if spec is None:
        return "failed", None, f"Entity type '{op.entity_type}' cannot be changed offline"

    payload = dict(op.payload or {})
    existing = await _load(db, spec.model, op.entity_id)

    if op.operation_type == "create":
        if existing is not None:
            if existing.created_by == user.id:
                return "synced", existing.version, None  # already applied
            return "conflict", existing.version, "A record with this id already exists"
        if spec.create is None:
            return "failed", None, "Create is not supported for this entity offline"
        token = _client_id.set((spec.model, op.entity_id))
        try:
            await _call(spec.create, db, user, None, payload)
        finally:
            _client_id.reset(token)
        created = await _load(db, spec.model, op.entity_id)
        if created is None:
            return "failed", None, "Record was not created with the client id"
        return "synced", created.version, None

    # update / delete require the record and a matching version
    if existing is None or getattr(existing, "deleted_at", None) is not None:
        return "failed", None, "Record not found or not accessible"
    if existing.version != op.client_version:
        return (
            "conflict",
            existing.version,
            f"Record changed on the server (server version {existing.version}, "
            f"device version {op.client_version})",
        )

    if op.operation_type == "delete":
        if spec.delete is None:
            return "failed", existing.version, "Delete is not supported for this entity"
        await _call(spec.delete, db, user, op.entity_id, None)
        return "synced", existing.version, None

    action = payload.pop("_action", "update")
    handler = spec.actions.get(action)
    if handler is None:
        return "failed", existing.version, f"Unknown action '{action}' for {op.entity_type}"
    result = await _call(handler, db, user, op.entity_id, payload)
    version = getattr(result, "version", None)
    if version is None:
        refreshed = await _load(db, spec.model, op.entity_id)
        version = refreshed.version if refreshed is not None else None
    return "synced", version, None


async def apply_operation(db: AsyncSession, user: User, op: SyncOperation) -> SyncOperation:
    """Apply one stored operation and persist its outcome."""
    user_id = user.id
    op_id = op.id
    try:
        status_, server_version, error = await _apply(db, user, op)
    except HTTPException as exc:
        await db.rollback()
        await db.refresh(user)
        status_, server_version, error = (
            "conflict" if exc.status_code == 409 else "failed",
            None,
            _error_text(exc),
        )
    except ValidationError as exc:
        await db.rollback()
        await db.refresh(user)
        status_, server_version, error = "failed", None, f"Invalid payload: {exc.errors()[:3]}"

    # Rollback expires loaded objects; reload explicitly before recording.
    record = (
        await db.execute(select(SyncOperation).where(SyncOperation.id == op_id), execution_options=BYPASS_SCOPE)
    ).scalar_one()
    record.status = status_
    record.server_version = server_version
    record.error_message = error
    record.processed_at = datetime.now(timezone.utc)
    record.updated_by = user_id
    await db.commit()
    return record

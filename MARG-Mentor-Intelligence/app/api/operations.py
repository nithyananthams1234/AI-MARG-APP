"""Executions, proposals (approval workflow), events, plans, demo data and usage endpoints."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.agent_registry import EVENT_ROUTES
from app.core.orchestrator import ExecutionView
from app.dependencies import Container, get_container, get_principal
from app.models.engine import Plan
from app.schemas.common import ApiResponse, AwareDatetime, ProposalStatus
from app.security.permissions import Principal, ensure_mentor_access
from app.seed.demo_data import demo_anchor_date, seeded_anchor_date
from app.utils.datetime_utils import local_date

router = APIRouter(prefix="/api/v1")


# ----------------------------------------------------------------------------- executions
@router.get("/executions/{execution_id}", tags=["executions"], summary="Agent execution status and result")
async def get_execution(
    execution_id: uuid.UUID, c: Container = Depends(get_container), p: Principal = Depends(get_principal)
) -> ApiResponse[ExecutionView]:
    return ApiResponse(data=await c.orchestrator.get_execution(execution_id, p))


@router.get("/executions", tags=["executions"], summary="Recent executions for a mentor")
async def list_executions(
    mentor_ref: str,
    limit: int = Query(default=20, ge=1, le=200),
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
) -> ApiResponse[list[ExecutionView]]:
    return ApiResponse(data=await c.orchestrator.list_executions(p, mentor_ref, limit))


@router.post("/executions/{execution_id}/retry", tags=["executions"], summary="Retry a failed execution")
async def retry_execution(
    execution_id: uuid.UUID, c: Container = Depends(get_container), p: Principal = Depends(get_principal)
) -> ApiResponse[ExecutionView]:
    return ApiResponse(data=await c.orchestrator.retry(execution_id, p))


# ----------------------------------------------------------------------------- proposals
class DecisionIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ExternalResultIn(BaseModel):
    success: bool
    detail: str | None = Field(default=None, max_length=1000)


@router.get("/proposals", tags=["approvals"], summary="List proposals for a mentor")
async def list_proposals(
    mentor_ref: str,
    status: ProposalStatus | None = None,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
) -> ApiResponse[list]:
    return ApiResponse(data=await c.approvals.list(p, mentor_ref, status))


@router.get("/proposals/{proposal_id}", tags=["approvals"], summary="Proposal detail with decision history")
async def get_proposal(
    proposal_id: uuid.UUID, c: Container = Depends(get_container), p: Principal = Depends(get_principal)
) -> ApiResponse[dict]:
    return ApiResponse(data=await c.approvals.get(p, proposal_id))


@router.post(
    "/proposals/{proposal_id}/approve",
    tags=["approvals"],
    summary="Approve a pending proposal (human mentor or authorised supervisor only)",
)
async def approve_proposal(
    proposal_id: uuid.UUID,
    body: DecisionIn | None = None,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
) -> ApiResponse[dict]:
    return ApiResponse(data=await c.approvals.approve(p, proposal_id, body.note if body else None))


@router.post("/proposals/{proposal_id}/reject", tags=["approvals"], summary="Reject a pending proposal")
async def reject_proposal(
    proposal_id: uuid.UUID,
    body: DecisionIn | None = None,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
) -> ApiResponse[dict]:
    return ApiResponse(data=await c.approvals.reject(p, proposal_id, body.note if body else None))


@router.post(
    "/proposals/{proposal_id}/external-result",
    tags=["approvals"],
    summary="MARG application reports delivery result of an approved external action",
)
async def external_result(
    proposal_id: uuid.UUID,
    body: ExternalResultIn,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
) -> ApiResponse[dict]:
    return ApiResponse(
        data=await c.approvals.report_external_result(p, proposal_id, body.success, body.detail)
    )


# ----------------------------------------------------------------------------- events
class EventIn(BaseModel):
    event_id: uuid.UUID
    event_type: Literal[tuple(EVENT_ROUTES)]  # type: ignore[valid-type]
    mentor_ref: str = Field(min_length=1, max_length=64)
    occurred_at: AwareDatetime
    entity_type: str | None = Field(default=None, max_length=64)
    entity_ref: str | None = Field(default=None, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/events",
    tags=["events"],
    summary="Submit an event; routed to an agent and processed idempotently by event_id",
)
async def submit_event(
    event: EventIn, c: Container = Depends(get_container), p: Principal = Depends(get_principal)
) -> ApiResponse[ExecutionView]:
    agent_id, use_ai = EVENT_ROUTES[event.event_type]
    view = await c.orchestrator.run(
        agent_id,
        {"mentor_ref": event.mentor_ref, "use_ai": use_ai},
        p,
        trigger="event",
        trigger_ref=f"{event.event_type}:{event.entity_ref or '-'}",
        idempotency_key=f"event:{event.event_id}",
    )
    return ApiResponse(data=view, meta={"routed_to": agent_id, "replayed": view.replayed})


# ----------------------------------------------------------------------------- plans
@router.get("/plans", tags=["plans"], summary="Stored plans and reports for a mentor")
async def list_plans(
    mentor_ref: str,
    plan_type: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
) -> ApiResponse[list]:
    ensure_mentor_access(p, mentor_ref, c.settings.supervisor_roles)
    async with c.db.session() as s:
        stmt = select(Plan).where(Plan.mentor_ref == mentor_ref).order_by(Plan.created_at.desc()).limit(limit)
        if plan_type:
            stmt = stmt.where(Plan.plan_type == plan_type)
        rows = (await s.execute(stmt)).scalars().all()
    return ApiResponse(
        data=[
            {
                "plan_id": str(r.id),
                "plan_type": r.plan_type,
                "period_start": r.period_start,
                "period_end": r.period_end,
                "execution_id": str(r.execution_id),
                "created_at": r.created_at,
            }
            for r in rows
        ]
    )


@router.get("/plans/{plan_id}", tags=["plans"], summary="Stored plan or report content")
async def get_plan(
    plan_id: uuid.UUID, c: Container = Depends(get_container), p: Principal = Depends(get_principal)
) -> ApiResponse[dict]:
    async with c.db.session() as s:
        row = await s.get(Plan, plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    ensure_mentor_access(p, row.mentor_ref, c.settings.supervisor_roles)
    return ApiResponse(
        data={
            "plan_id": str(row.id),
            "plan_type": row.plan_type,
            "mentor_ref": row.mentor_ref,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "content": row.content,
        }
    )


# ----------------------------------------------------------------------------- demo data & usage
@router.get("/mentors", tags=["demo data"], summary="List mentors (DEMO DATA)")
async def list_mentors(
    c: Container = Depends(get_container), _: Principal = Depends(get_principal)
) -> ApiResponse[list]:
    return ApiResponse(
        data=await c.adapter.list_mentors(), meta={"data_source": "demo", "label": "DEMO DATA"}
    )


@router.get(
    "/mentors/{mentor_ref}/records", tags=["demo data"], summary="All records for a mentor (DEMO DATA)"
)
async def mentor_records(
    mentor_ref: str, c: Container = Depends(get_container), p: Principal = Depends(get_principal)
) -> ApiResponse[dict]:
    ensure_mentor_access(p, mentor_ref, c.settings.supervisor_roles)
    snap = await c.adapter.get_mentor_snapshot(mentor_ref)
    return ApiResponse(
        data=snap.model_dump(mode="json"), meta={"data_source": snap.data_source.value, "label": "DEMO DATA"}
    )


@router.get("/demo/info", tags=["demo data"], summary="Demo anchor date (seed data is relative to this date)")
async def demo_info(
    c: Container = Depends(get_container), _: Principal = Depends(get_principal)
) -> ApiResponse[dict]:
    from app.utils.datetime_utils import utcnow

    today = local_date(utcnow(), c.settings.tz)
    seeded = await seeded_anchor_date(c.db)
    return ApiResponse(
        data={
            "today": today.isoformat(),
            "anchor_date": (seeded or demo_anchor_date(today)).isoformat(),
            "anchor_source": "recorded at seeding" if seeded else "computed (no seeding record found)",
            "note": "DEMO DATA dates are relative to the anchor date. Re-seed on the demo day for current dates.",
        }
    )


@router.get("/usage", tags=["monitoring"], summary="Claude token usage and configured-cost summary")
async def usage(
    c: Container = Depends(get_container), _: Principal = Depends(get_principal)
) -> ApiResponse[dict]:
    return ApiResponse(data=await c.usage.summary())

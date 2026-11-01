"""Agent endpoints. Every call is executed by the orchestrator and recorded as an execution."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header

from app.agents.communication_agent import CommunicationInput
from app.agents.followup_agent import FollowupInput
from app.agents.planning_agents import DailyPlanInput, WeeklyPlanInput
from app.agents.reporting_agent import ReportInput
from app.agents.schedule_agent import ScheduleInput
from app.agents.school_visit_agent import VisitPlanningInput
from app.agents.task_agent import TaskPrioritisationInput
from app.agents.time_agent import TimeManagementInput
from app.agents.workload_agent import WorkloadInput
from app.core.orchestrator import ExecutionView
from app.dependencies import Container, get_container, get_principal
from app.schemas.common import ApiResponse
from app.security.permissions import Principal

router = APIRouter(prefix="/api/v1", tags=["agents"])

IdempotencyKey = Header(
    default=None,
    alias="Idempotency-Key",
    max_length=200,
    description="Optional client key; repeated requests with the same key return the same execution",
)


async def _run(
    c: Container, agent_id: str, body: Any, principal: Principal, key: str | None
) -> ApiResponse[ExecutionView]:
    view = await c.orchestrator.run(agent_id, body.model_dump(mode="json"), principal, idempotency_key=key)
    return ApiResponse(data=view, meta={"replayed": view.replayed})


@router.get("/agents", summary="List registered agents and their input schemas")
async def list_agents(
    c: Container = Depends(get_container), _: Principal = Depends(get_principal)
) -> ApiResponse[list]:
    return ApiResponse(data=c.registry.describe())


@router.post(
    "/tasks/prioritise", summary="Task Intelligence: deterministic prioritisation, dependencies, next actions"
)
async def prioritise_tasks(
    body: TaskPrioritisationInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "task_intelligence", body, p, key)


@router.post("/time/analysis", summary="Time Management: available hours, time requirements, allocation")
async def time_analysis(
    body: TimeManagementInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "time_management", body, p, key)


@router.post(
    "/schedule/analysis", summary="Schedule Intelligence: conflicts, free time, reschedule proposals"
)
async def schedule_analysis(
    body: ScheduleInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "schedule_intelligence", body, p, key)


@router.post("/workload/analysis", summary="Workload Intelligence: workload index and overloaded periods")
async def workload_analysis(
    body: WorkloadInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "workload_intelligence", body, p, key)


@router.post("/followups/analysis", summary="Follow-up analysis: responses, evidence, verification, overdue")
async def followup_analysis(
    body: FollowupInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "followup_management", body, p, key)


@router.post(
    "/school-visits/plan", summary="School Visit Planning: schools needing visits and slot proposals"
)
async def school_visit_plan(
    body: VisitPlanningInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "school_visit_planning", body, p, key)


@router.post("/plans/daily", summary="Daily Planning: realistic plan for one day with reasons")
async def daily_plan(
    body: DailyPlanInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "daily_planning", body, p, key)


@router.post("/plans/weekly", summary="Weekly Planning: priorities, deadlines, visit/follow-up distribution")
async def weekly_plan(
    body: WeeklyPlanInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "weekly_planning", body, p, key)


@router.post("/reports", summary="Reporting: daily or weekly mentor activity report")
async def report(
    body: ReportInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "reporting", body, p, key)


@router.post(
    "/communications/drafts", summary="Communication: draft a teacher message (never sent automatically)"
)
async def communication_draft(
    body: CommunicationInput,
    c: Container = Depends(get_container),
    p: Principal = Depends(get_principal),
    key: str | None = IdempotencyKey,
) -> ApiResponse[ExecutionView]:
    return await _run(c, "teacher_communication", body, p, key)

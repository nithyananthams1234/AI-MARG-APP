"""Deterministic task priority calculation.

Priority = 0.30 x Urgency + 0.25 x Impact + 0.20 x Risk + 0.15 x Deadline proximity
         + 0.10 x Workload/dependency factor

Rules (owner decisions): every factor must come from verified inputs; a missing factor is never
replaced by a default (no "50"); when any factor is missing no final score or priority is assigned.
Claude may explain these results but never changes them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import Priority, TaskStatus
from app.schemas.records import TaskRecord

WEIGHTS: dict[str, float] = {
    "urgency": 0.30,
    "impact": 0.25,
    "risk": 0.20,
    "deadline_proximity": 0.15,
    "workload_dependency": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

OPEN_STATUSES = {TaskStatus.pending, TaskStatus.in_progress}


class PriorityResult(BaseModel):
    task_ref: str
    status: Literal["complete", "incomplete"]
    score: float | None
    priority: Priority | None
    factors: dict[str, float | None]
    factor_sources: dict[str, str]
    missing_factors: list[str]
    score_bounds: tuple[float, float]
    calculation: str = "deterministic"


def classify(score: float) -> Priority:
    """0-24 low, 25-49 medium, 50-74 high, 75-100 critical (lower bounds inclusive)."""
    if not 0 <= score <= 100:
        raise ValueError("score must be between 0 and 100")
    if score < 25:
        return Priority.low
    if score < 50:
        return Priority.medium
    if score < 75:
        return Priority.high
    return Priority.critical


def deadline_proximity(due_at: datetime | None, now: datetime, horizon_days: int) -> float | None:
    """100 when due/overdue, linear decay to 0 at the horizon. None when no deadline is recorded."""
    if due_at is None:
        return None
    remaining_hours = (due_at - now).total_seconds() / 3600
    horizon_hours = horizon_days * 24
    if remaining_hours <= 0:
        return 100.0
    if remaining_hours >= horizon_hours:
        return 0.0
    return round(100.0 * (1 - remaining_hours / horizon_hours), 2)


def dependency_factor(task: TaskRecord, all_tasks: list[TaskRecord], points_per_blocked_task: int) -> float:
    """Based on verified dependency records: how many open tasks are waiting for this task."""
    blocked = sum(1 for t in all_tasks if t.status in OPEN_STATUSES and task.id in t.depends_on)
    return float(min(100, blocked * points_per_blocked_task))


def compute_priority(
    task: TaskRecord,
    now: datetime,
    all_tasks: list[TaskRecord],
    horizon_days: int,
    points_per_blocked_task: int,
) -> PriorityResult:
    factors: dict[str, float | None] = {
        "urgency": float(task.urgency) if task.urgency is not None else None,
        "impact": float(task.impact) if task.impact is not None else None,
        "risk": float(task.risk) if task.risk is not None else None,
        "deadline_proximity": deadline_proximity(task.due_at, now, horizon_days),
        "workload_dependency": dependency_factor(task, all_tasks, points_per_blocked_task),
    }
    for name, value in factors.items():
        if value is not None and not 0 <= value <= 100:
            raise ValueError(f"Factor {name} out of range for task {task.id}: {value}")
    sources = {
        "urgency": "task record" if task.urgency is not None else "not recorded",
        "impact": "task record" if task.impact is not None else "not recorded",
        "risk": "task record" if task.risk is not None else "not recorded",
        "deadline_proximity": "computed from due date" if task.due_at else "due date not recorded",
        "workload_dependency": "computed from dependency records",
    }
    missing = [name for name, value in factors.items() if value is None]
    known = sum(WEIGHTS[n] * v for n, v in factors.items() if v is not None)
    missing_weight = sum(WEIGHTS[n] for n in missing)
    bounds = (round(known, 2), round(known + 100 * missing_weight, 2))
    if missing:
        return PriorityResult(
            task_ref=task.id,
            status="incomplete",
            score=None,
            priority=None,
            factors=factors,
            factor_sources=sources,
            missing_factors=missing,
            score_bounds=bounds,
        )
    score = round(known, 2)
    return PriorityResult(
        task_ref=task.id,
        status="complete",
        score=score,
        priority=classify(score),
        factors=factors,
        factor_sources=sources,
        missing_factors=[],
        score_bounds=(score, score),
    )


class DependencyAnalysis(BaseModel):
    blocked_by_open: dict[str, list[str]]
    unknown_references: dict[str, list[str]]
    cycles: list[list[str]]


def analyse_dependencies(tasks: list[TaskRecord]) -> DependencyAnalysis:
    by_id = {t.id: t for t in tasks}
    blocked: dict[str, list[str]] = {}
    unknown: dict[str, list[str]] = {}
    for t in tasks:
        if t.status not in OPEN_STATUSES:
            continue
        open_deps = [d for d in t.depends_on if d in by_id and by_id[d].status in OPEN_STATUSES]
        missing = [d for d in t.depends_on if d not in by_id]
        if open_deps:
            blocked[t.id] = open_deps
        if missing:
            unknown[t.id] = missing

    cycles: list[list[str]] = []
    state: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> None:
        state[node] = 1
        for dep in by_id[node].depends_on:
            if dep not in by_id:
                continue
            if state.get(dep) == 1:
                cycle = path[path.index(dep) :] + [dep]
                if sorted(cycle) not in [sorted(c) for c in cycles]:
                    cycles.append(cycle)
            elif dep not in state:
                visit(dep, path + [dep])
        state[node] = 2

    for tid in by_id:
        if tid not in state:
            visit(tid, [tid])
    return DependencyAnalysis(blocked_by_open=blocked, unknown_references=unknown, cycles=cycles)


def rank_tasks(results: dict[str, PriorityResult], tasks: list[TaskRecord], now: datetime) -> list[dict]:
    """Complete scores first (score desc), then incomplete tasks ordered only by verified facts."""
    by_id = {t.id: t for t in tasks}
    complete = sorted((r for r in results.values() if r.status == "complete"), key=lambda r: -(r.score or 0))
    incomplete = sorted(
        (r for r in results.values() if r.status == "incomplete"),
        key=lambda r: (
            not (by_id[r.task_ref].due_at is not None and by_id[r.task_ref].due_at <= now),  # type: ignore[operator]
            by_id[r.task_ref].due_at or datetime.max.replace(tzinfo=now.tzinfo),
        ),
    )
    ranking = []
    for i, r in enumerate(complete + incomplete, start=1):
        ranking.append(
            {
                "rank": i,
                "task_ref": r.task_ref,
                "ordering_basis": "priority_score"
                if r.status == "complete"
                else "overdue_then_due_date (score incomplete)",
            }
        )
    return ranking

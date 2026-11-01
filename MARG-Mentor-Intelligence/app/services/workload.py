"""Deterministic workload calculation.

Workload Index = Estimated workload hours / Available working hours x 100

An administrative planning metric only - not a medical or psychological assessment. Missing
estimates are listed and make the index a lower bound; missing working hours make it unavailable.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.schemas.common import MissingData, TaskStatus
from app.schemas.records import MentorSnapshot
from app.services.schedule import calendar_entries, working_window
from app.utils.datetime_utils import local_day_bounds, minutes_between

OPEN = {TaskStatus.pending, TaskStatus.in_progress}


class DayLoad(BaseModel):
    date: date
    working_day: bool | None
    available_minutes: int | None
    scheduled_minutes: int
    activity_minutes: int
    activities_without_estimate: list[str]
    committed_minutes: int
    index: float | None
    status: str  # normal | high | overloaded | non_working_day | unknown


class WorkloadSummary(BaseModel):
    start_date: date
    days: int
    per_day: list[DayLoad]
    available_minutes: int | None
    scheduled_minutes: int
    activity_minutes: int
    task_minutes: int
    tasks_counted: list[str]
    tasks_without_estimate: list[str]
    overdue_tasks: list[str]
    estimated_workload_minutes: int
    workload_index: float | None
    index_is_lower_bound: bool
    status: str
    overloaded_days: list[date]
    thresholds: dict[str, float]
    metric_note: str = (
        "Administrative planning metric based on recorded estimates; not a wellbeing assessment."
    )
    missing_data: list[MissingData]


def classify(index: float | None, high: float, overload: float) -> str:
    if index is None:
        return "unknown"
    if index > overload:
        return "overloaded"
    if index >= high:
        return "high"
    return "normal"


def day_load(snapshot: MentorSnapshot, day: date, high: float, overload: float) -> DayLoad:
    tz = ZoneInfo(snapshot.mentor.timezone)
    start, end = local_day_bounds(day, tz)
    window = working_window(snapshot, day)
    hours_known = (
        snapshot.mentor.work_start is not None
        and snapshot.mentor.work_end is not None
        and snapshot.mentor.working_days is not None
    )
    available = minutes_between(*window) if window else (0 if hours_known else None)
    scheduled = sum(
        minutes_between(max(e.start, start), min(e.end, end)) for e in calendar_entries(snapshot, start, end)
    )
    acts = [a for a in snapshot.workload_activities if a.activity_date == day and a.status in OPEN]
    activity_minutes = sum(a.estimated_minutes for a in acts if a.estimated_minutes is not None)
    no_estimate = [a.id for a in acts if a.estimated_minutes is None]
    committed = scheduled + activity_minutes
    if not hours_known:
        index, status, working = None, "unknown", None
    elif window is None:
        index, status, working = None, "non_working_day", False
    else:
        index = round(committed / available * 100, 1) if available else None
        status, working = classify(index, high, overload), True
    return DayLoad(
        date=day,
        working_day=working,
        available_minutes=available,
        scheduled_minutes=scheduled,
        activity_minutes=activity_minutes,
        activities_without_estimate=no_estimate,
        committed_minutes=committed,
        index=index,
        status=status,
    )


def window_workload(
    snapshot: MentorSnapshot, start_day: date, days: int, now: datetime, high: float, overload: float
) -> WorkloadSummary:
    tz = ZoneInfo(snapshot.mentor.timezone)
    per_day = [day_load(snapshot, start_day + timedelta(days=i), high, overload) for i in range(days)]
    window_end = local_day_bounds(start_day + timedelta(days=days - 1), tz)[1]
    open_tasks = [t for t in snapshot.tasks if t.status in OPEN]
    # Tasks due inside the window, or already overdue, are counted as demand on this window.
    in_scope = [t for t in open_tasks if t.due_at is not None and t.due_at < window_end]
    counted = [t for t in in_scope if t.estimated_minutes is not None]
    no_estimate_tasks = [t.id for t in in_scope if t.estimated_minutes is None]
    overdue = [t.id for t in open_tasks if t.due_at is not None and t.due_at < now]
    task_minutes = sum(t.estimated_minutes or 0 for t in counted)

    missing: list[MissingData] = []
    hours_known = all(d.available_minutes is not None for d in per_day)
    available = sum(d.available_minutes or 0 for d in per_day) if hours_known else None
    if not hours_known:
        missing.append(
            MissingData(
                entity_type="mentor",
                entity_ref=snapshot.mentor.id,
                field="working_hours",
                impact="Workload index cannot be calculated without recorded working hours",
            )
        )
    for ref in no_estimate_tasks:
        missing.append(
            MissingData(
                entity_type="task",
                entity_ref=ref,
                field="estimated_minutes",
                impact="Task time not included; workload index is a lower bound",
            )
        )
    activity_no_est = [a for d in per_day for a in d.activities_without_estimate]
    for ref in activity_no_est:
        missing.append(
            MissingData(
                entity_type="workload_activity",
                entity_ref=ref,
                field="estimated_minutes",
                impact="Activity time not included; workload index is a lower bound",
            )
        )
    undated = [t.id for t in open_tasks if t.due_at is None]
    for ref in undated:
        missing.append(
            MissingData(
                entity_type="task",
                entity_ref=ref,
                field="due_at",
                impact="Task cannot be assigned to a planning window",
            )
        )

    scheduled = sum(d.scheduled_minutes for d in per_day)
    activities = sum(d.activity_minutes for d in per_day)
    total = scheduled + activities + task_minutes
    index = round(total / available * 100, 1) if available else None
    return WorkloadSummary(
        start_date=start_day,
        days=days,
        per_day=per_day,
        available_minutes=available,
        scheduled_minutes=scheduled,
        activity_minutes=activities,
        task_minutes=task_minutes,
        tasks_counted=[t.id for t in counted],
        tasks_without_estimate=no_estimate_tasks,
        overdue_tasks=overdue,
        estimated_workload_minutes=total,
        workload_index=index,
        index_is_lower_bound=bool(no_estimate_tasks or activity_no_est),
        status=classify(index, high, overload),
        overloaded_days=[d.date for d in per_day if d.status == "overloaded"],
        thresholds={"high": high, "overloaded": overload},
        missing_data=missing,
    )

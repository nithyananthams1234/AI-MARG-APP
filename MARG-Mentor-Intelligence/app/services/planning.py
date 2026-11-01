"""Deterministic daily plan construction.

Fixed calendar entries stay where they are. Open work items with a recorded time estimate are fitted
greedily, in priority order, into free working time. Items that cannot be placed are listed with
the reason (no estimate, blocked by a dependency, not enough time, no working hours).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.schemas.common import MissingData, TaskStatus
from app.schemas.records import MentorSnapshot, TaskRecord
from app.services.priority import (
    OPEN_STATUSES,
    PriorityResult,
    analyse_dependencies,
    compute_priority,
    rank_tasks,
)
from app.services.schedule import (
    Conflict,
    Slot,
    calendar_entries,
    find_conflicts,
    free_slots,
    working_hours_missing,
    working_window,
)
from app.utils.datetime_utils import local_day_bounds, minutes_between


class PlanItem(BaseModel):
    ref: str
    kind: str
    title: str
    start: datetime
    end: datetime
    source: str  # calendar | placed_by_engine
    priority: str | None = None
    score: float | None = None
    reason: str


class UnscheduledItem(BaseModel):
    ref: str
    kind: str
    title: str
    reason: str
    priority: str | None = None


class DayPlan(BaseModel):
    date: date
    working_window: dict[str, datetime] | None
    timeline: list[PlanItem]
    unscheduled: list[UnscheduledItem]
    conflicts: list[Conflict]
    capacity: dict[str, int | None]
    critical_items: list[str]
    missing_data: list[MissingData]
    note: str | None = None


def priorities_for(
    snapshot: MentorSnapshot, now: datetime, horizon: int, points: int
) -> dict[str, PriorityResult]:
    return {
        t.id: compute_priority(t, now, snapshot.tasks, horizon, points)
        for t in snapshot.tasks
        if t.status in OPEN_STATUSES
    }


def task_reason(task: TaskRecord, result: PriorityResult, now: datetime, tz: ZoneInfo) -> str:
    parts = []
    if result.status == "complete":
        parts.append(f"priority {result.priority.value if result.priority else '-'} (score {result.score})")
    else:
        parts.append(f"priority score incomplete (missing: {', '.join(result.missing_factors)})")
    if task.due_at:
        local_due = task.due_at.astimezone(tz)
        if task.due_at < now:
            parts.append(f"overdue since {local_due:%d %b %H:%M}")
        else:
            parts.append(f"due {local_due:%d %b %H:%M}")
    if (result.factors.get("workload_dependency") or 0) > 0:
        parts.append("other open tasks depend on it")
    return "; ".join(parts)


def _place(slots: list[Slot], minutes: int) -> tuple[datetime, datetime] | None:
    for i, slot in enumerate(slots):
        if slot.minutes >= minutes:
            start, end = slot.start, slot.start + timedelta(minutes=minutes)
            remaining = minutes_between(end, slot.end)
            if remaining >= 15:
                slots[i] = Slot(start=end, end=slot.end, minutes=remaining)
            else:
                slots.pop(i)
            return start, end
    return None


def build_day_plan(
    snapshot: MentorSnapshot, day: date, now: datetime, horizon: int, points: int
) -> tuple[DayPlan, dict[str, PriorityResult]]:
    tz = ZoneInfo(snapshot.mentor.timezone)
    day_start, day_end = local_day_bounds(day, tz)
    results = priorities_for(snapshot, now, horizon, points)
    missing = working_hours_missing(snapshot)
    window = working_window(snapshot, day)
    entries = calendar_entries(snapshot, day_start, day_end)
    conflicts = find_conflicts(snapshot, entries)

    timeline = [
        PlanItem(
            ref=e.ref,
            kind=e.kind,
            title=e.title,
            start=e.start,
            end=e.end,
            source="calendar",
            reason="Fixed calendar commitment",
        )
        for e in entries
    ]
    unscheduled: list[UnscheduledItem] = []
    tasks = {t.id: t for t in snapshot.tasks}

    if window is None:
        note = (
            "Working hours are not recorded; no time allocation was made."
            if missing
            else "Not a recorded working day; no time allocation was made."
        )
        for r in rank_tasks(results, snapshot.tasks, now):
            t = tasks[r["task_ref"]]
            unscheduled.append(
                UnscheduledItem(
                    ref=t.id,
                    kind="task",
                    title=t.title,
                    reason=note,
                    priority=results[t.id].priority.value if results[t.id].priority else None,
                )
            )
        return DayPlan(
            date=day,
            working_window=None,
            timeline=timeline,
            unscheduled=unscheduled,
            conflicts=conflicts,
            capacity={
                "available_minutes": None,
                "scheduled_minutes": None,
                "placed_minutes": None,
                "free_minutes_remaining": None,
            },
            critical_items=[],
            missing_data=missing,
            note=note,
        ), results

    slots = free_slots(snapshot, day, entries)
    placed_minutes = 0

    # 1. Workload activities assigned to this date.
    for act in sorted(
        (
            a
            for a in snapshot.workload_activities
            if a.activity_date == day and a.status in (TaskStatus.pending, TaskStatus.in_progress)
        ),
        key=lambda a: a.id,
    ):
        if act.estimated_minutes is None:
            unscheduled.append(
                UnscheduledItem(
                    ref=act.id,
                    kind="workload_activity",
                    title=act.description,
                    reason="Time estimate not recorded",
                )
            )
            missing.append(
                MissingData(
                    entity_type="workload_activity",
                    entity_ref=act.id,
                    field="estimated_minutes",
                    impact="Activity could not be placed in the plan",
                )
            )
            continue
        spot = _place(slots, act.estimated_minutes)
        if spot:
            placed_minutes += act.estimated_minutes
            timeline.append(
                PlanItem(
                    ref=act.id,
                    kind="workload_activity",
                    title=act.description,
                    start=spot[0],
                    end=spot[1],
                    source="placed_by_engine",
                    reason=f"Assigned for this date by {act.assigned_by or 'office'}",
                )
            )
        else:
            unscheduled.append(
                UnscheduledItem(
                    ref=act.id,
                    kind="workload_activity",
                    title=act.description,
                    reason="Not enough free working time today",
                )
            )

    # 2. Open tasks in priority order, respecting dependencies.
    deps = analyse_dependencies(snapshot.tasks)
    ranking = [r["task_ref"] for r in rank_tasks(results, snapshot.tasks, now)]
    placed: set[str] = set()
    pending = list(ranking)
    progress = True
    while pending and progress:
        progress = False
        for ref in list(pending):
            task = tasks[ref]
            blockers = [d for d in deps.blocked_by_open.get(ref, []) if d not in placed]
            if blockers:
                continue
            pending.remove(ref)
            progress = True
            res = results[ref]
            prio = res.priority.value if res.priority else None
            if task.estimated_minutes is None:
                unscheduled.append(
                    UnscheduledItem(
                        ref=ref,
                        kind="task",
                        title=task.title,
                        priority=prio,
                        reason="Time estimate not recorded",
                    )
                )
                missing.append(
                    MissingData(
                        entity_type="task",
                        entity_ref=ref,
                        field="estimated_minutes",
                        impact="Task could not be placed in the plan",
                    )
                )
                continue
            spot = _place(slots, task.estimated_minutes)
            if spot is None:
                unscheduled.append(
                    UnscheduledItem(
                        ref=ref,
                        kind="task",
                        title=task.title,
                        priority=prio,
                        reason="Not enough free working time today",
                    )
                )
                continue
            placed.add(ref)
            placed_minutes += task.estimated_minutes
            timeline.append(
                PlanItem(
                    ref=ref,
                    kind="task",
                    title=task.title,
                    start=spot[0],
                    end=spot[1],
                    source="placed_by_engine",
                    priority=prio,
                    score=res.score,
                    reason=task_reason(task, res, now, tz),
                )
            )
    for ref in pending:
        task = tasks[ref]
        unscheduled.append(
            UnscheduledItem(
                ref=ref,
                kind="task",
                title=task.title,
                priority=results[ref].priority.value if results[ref].priority else None,
                reason=f"Blocked by open dependency: {', '.join(deps.blocked_by_open.get(ref, []))}",
            )
        )

    timeline.sort(key=lambda i: i.start)
    available = minutes_between(*window)
    scheduled = sum(
        minutes_between(max(e.start, window[0]), min(e.end, window[1]))
        for e in entries
        if e.end > window[0] and e.start < window[1]
    )
    critical = [
        ref for ref, r in results.items() if r.priority is not None and r.priority.value == "critical"
    ]
    return DayPlan(
        date=day,
        working_window={"start": window[0], "end": window[1]},
        timeline=timeline,
        unscheduled=unscheduled,
        conflicts=conflicts,
        capacity={
            "available_minutes": available,
            "scheduled_minutes": scheduled,
            "placed_minutes": placed_minutes,
            "free_minutes_remaining": sum(s.minutes for s in slots),
        },
        critical_items=critical,
        missing_data=missing,
    ), results

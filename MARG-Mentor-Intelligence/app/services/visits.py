"""Deterministic school attention scoring for visit planning.

Score components (documented, configurable in code review): days since last completed visit
(up to 40), overdue follow-ups (15 each, up to 30), open action plans (5 each, up to 15), open
tasks for the school (5 each, up to 15). A school with no recorded completed visit has the first
component flagged as missing rather than assumed.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ActionPlanStatus, TaskStatus, VisitStatus
from app.schemas.records import MentorSnapshot
from app.services.followups import RESOLVED

OPEN_PLAN = {
    ActionPlanStatus.approved,
    ActionPlanStatus.in_progress,
    ActionPlanStatus.overdue,
    ActionPlanStatus.pending_approval,
}


class SchoolAttention(BaseModel):
    school_ref: str
    school_name: str
    last_completed_visit: datetime | None
    days_since_last_visit: int | None
    next_planned_visit: datetime | None
    overdue_followups: int
    open_action_plans: int
    open_tasks: int
    components: dict[str, float | None]
    attention_score: float
    score_complete: bool
    flags: list[str]


def school_attention(snapshot: MentorSnapshot, now: datetime) -> list[SchoolAttention]:
    results = []
    for school in snapshot.schools:
        completed = [
            v for v in snapshot.visits if v.school_ref == school.id and v.status == VisitStatus.completed
        ]
        last = max((v.completed_at or v.scheduled_end for v in completed), default=None)
        planned = [
            v.scheduled_start
            for v in snapshot.visits
            if v.school_ref == school.id and v.status == VisitStatus.planned and v.scheduled_start >= now
        ]
        overdue_f = sum(
            1
            for f in snapshot.followups
            if f.school_ref == school.id
            and f.status not in RESOLVED
            and f.due_at is not None
            and f.due_at < now
        )
        open_plans = sum(
            1 for p in snapshot.action_plans if p.school_ref == school.id and p.status in OPEN_PLAN
        )
        open_tasks = sum(
            1
            for t in snapshot.tasks
            if t.school_ref == school.id and t.status in (TaskStatus.pending, TaskStatus.in_progress)
        )
        days = (now - last).days if last else None
        components = {
            "days_since_last_visit": round(min(40.0, days * 40 / 60), 1) if days is not None else None,
            "overdue_followups": float(min(30, overdue_f * 15)),
            "open_action_plans": float(min(15, open_plans * 5)),
            "open_tasks": float(min(15, open_tasks * 5)),
        }
        flags = []
        if last is None:
            flags.append("no_completed_visit_in_records")
        if school.travel_minutes_from_base is None:
            flags.append("travel_time_not_recorded")
        if school.available_days is None:
            flags.append("availability_not_recorded")
        if planned:
            flags.append("visit_already_planned")
        results.append(
            SchoolAttention(
                school_ref=school.id,
                school_name=school.name,
                last_completed_visit=last,
                days_since_last_visit=days,
                next_planned_visit=min(planned) if planned else None,
                overdue_followups=overdue_f,
                open_action_plans=open_plans,
                open_tasks=open_tasks,
                components=components,
                attention_score=round(sum(v for v in components.values() if v is not None), 1),
                score_complete=all(v is not None for v in components.values()),
                flags=flags,
            )
        )
    return sorted(results, key=lambda r: (-r.attention_score, r.school_ref))

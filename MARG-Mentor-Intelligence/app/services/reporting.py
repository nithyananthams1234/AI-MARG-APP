"""Deterministic activity report facts. Every number comes from records in the window."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import FollowUpStatus, TaskStatus, VisitStatus
from app.schemas.records import MentorSnapshot

OPEN = {TaskStatus.pending, TaskStatus.in_progress}


class ReportFacts(BaseModel):
    period_start: datetime
    period_end: datetime
    tasks_completed: list[dict]
    tasks_open: int
    tasks_overdue: list[dict]
    visits_completed: list[dict]
    visits_planned_upcoming: list[dict]
    visits_cancelled: int
    followups_by_status: dict[str, int]
    followups_verified_in_period: int
    teacher_responses_in_period: int
    evidence_submissions_in_period: int
    observations_recorded: int
    workload_activities_completed: int
    data_gaps: list[str]

    def numbers(self) -> set[str]:
        """All numeric values that may legitimately appear in a narrative."""
        values: set[int] = {
            len(self.tasks_completed),
            self.tasks_open,
            len(self.tasks_overdue),
            len(self.visits_completed),
            len(self.visits_planned_upcoming),
            self.visits_cancelled,
            self.followups_verified_in_period,
            self.teacher_responses_in_period,
            self.evidence_submissions_in_period,
            self.observations_recorded,
            self.workload_activities_completed,
            sum(self.followups_by_status.values()),
            *self.followups_by_status.values(),
        }
        return {str(v) for v in values}


def activity_report(snapshot: MentorSnapshot, start: datetime, end: datetime, now: datetime) -> ReportFacts:
    def within(ts: datetime | None) -> bool:
        return ts is not None and start <= ts < end

    schools = {s.id: s.name for s in snapshot.schools}
    completed = [
        {"task_ref": t.id, "title": t.title}
        for t in snapshot.tasks
        if t.status == TaskStatus.completed and within(t.completed_at)
    ]
    overdue = [
        {"task_ref": t.id, "title": t.title, "due_at": t.due_at}
        for t in snapshot.tasks
        if t.status in OPEN and t.due_at is not None and t.due_at < now
    ]
    visits_done = [
        {"visit_ref": v.id, "school": schools.get(v.school_ref, v.school_ref)}
        for v in snapshot.visits
        if v.status == VisitStatus.completed and within(v.completed_at or v.scheduled_end)
    ]
    upcoming = [
        {"visit_ref": v.id, "school": schools.get(v.school_ref, v.school_ref), "start": v.scheduled_start}
        for v in snapshot.visits
        if v.status == VisitStatus.planned and v.scheduled_start >= now
    ]
    by_status: dict[str, int] = {s.value: 0 for s in FollowUpStatus}
    for f in snapshot.followups:
        by_status[f.status.value] += 1
    gaps = []
    if any(t.status == TaskStatus.completed and t.completed_at is None for t in snapshot.tasks):
        gaps.append("Some completed tasks have no completion timestamp and are not counted in the period")
    if any(v.status == VisitStatus.completed and v.completed_at is None for v in snapshot.visits):
        gaps.append("Some completed visits have no completion timestamp; scheduled end time used")
    return ReportFacts(
        period_start=start,
        period_end=end,
        tasks_completed=completed,
        tasks_open=sum(1 for t in snapshot.tasks if t.status in OPEN),
        tasks_overdue=overdue,
        visits_completed=visits_done,
        visits_planned_upcoming=upcoming,
        visits_cancelled=sum(
            1 for v in snapshot.visits if v.status == VisitStatus.cancelled and within(v.scheduled_start)
        ),
        followups_by_status=by_status,
        followups_verified_in_period=sum(1 for f in snapshot.followups if within(f.mentor_verified_at)),
        teacher_responses_in_period=sum(1 for f in snapshot.followups if within(f.teacher_reported_at)),
        evidence_submissions_in_period=sum(1 for f in snapshot.followups if within(f.evidence_submitted_at)),
        observations_recorded=sum(1 for o in snapshot.observations if within(o.observed_at)),
        workload_activities_completed=sum(
            1 for a in snapshot.workload_activities if a.status == TaskStatus.completed
        ),
        data_gaps=gaps,
    )

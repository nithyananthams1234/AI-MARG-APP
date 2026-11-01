"""Deterministic follow-up analysis.

Keeps three kinds of progress information strictly separate:
teacher-reported progress, evidence submitted by the teacher, and mentor-verified progress.
Nothing here ever marks progress as mentor-verified.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import FollowUpStatus
from app.schemas.records import MentorSnapshot

AWAITING_TEACHER = {FollowUpStatus.pending, FollowUpStatus.needs_revision}
AWAITING_VERIFICATION = {FollowUpStatus.teacher_responded, FollowUpStatus.evidence_submitted}
RESOLVED = {FollowUpStatus.mentor_verified, FollowUpStatus.closed}


class ProgressLayers(BaseModel):
    teacher_reported: dict | None
    evidence_submitted: dict | None
    mentor_verified: dict | None


class FollowUpItem(BaseModel):
    followup_ref: str
    action_plan_ref: str
    action_plan_title: str | None
    teacher_ref: str
    school_ref: str
    status: FollowUpStatus
    due_at: datetime | None
    overdue: bool
    days_overdue: int | None
    category: str
    progress: ProgressLayers
    flags: list[str]


class ActionPlanProgress(BaseModel):
    action_plan_ref: str
    title: str
    status: str
    due_date: str | None
    due_date_passed: bool
    followups_total: int
    followups_by_status: dict[str, int]
    mentor_verified: int


class FollowUpAnalysis(BaseModel):
    items: list[FollowUpItem]
    counts: dict[str, int]
    action_plans: list[ActionPlanProgress]


def analyse_followups(snapshot: MentorSnapshot, now: datetime) -> FollowUpAnalysis:
    plans = {p.id: p for p in snapshot.action_plans}
    items: list[FollowUpItem] = []
    for f in snapshot.followups:
        overdue = f.status not in RESOLVED and f.due_at is not None and f.due_at < now
        if f.status in RESOLVED:
            category = "resolved"
        elif f.status in AWAITING_VERIFICATION:
            category = "awaiting_mentor_verification"
        else:
            category = "awaiting_teacher_response"
        flags = []
        if overdue:
            flags.append("overdue")
        if f.status == FollowUpStatus.teacher_responded and not f.evidence_description:
            flags.append("evidence_missing")
        if f.status in AWAITING_VERIFICATION:
            flags.append("verification_required")
        if f.due_at is None and f.status not in RESOLVED:
            flags.append("due_date_not_recorded")
        if f.status == FollowUpStatus.needs_revision:
            flags.append("revision_requested")
        plan = plans.get(f.action_plan_ref)
        items.append(
            FollowUpItem(
                followup_ref=f.id,
                action_plan_ref=f.action_plan_ref,
                action_plan_title=plan.title if plan else None,
                teacher_ref=f.teacher_ref,
                school_ref=f.school_ref,
                status=f.status,
                due_at=f.due_at,
                overdue=overdue,
                days_overdue=(now - f.due_at).days if overdue and f.due_at else None,
                category=category,
                progress=ProgressLayers(
                    teacher_reported={
                        "text": f.teacher_reported_progress,
                        "at": f.teacher_reported_at,
                        "label": "teacher-reported (not verified)",
                    }
                    if f.teacher_reported_progress
                    else None,
                    evidence_submitted={
                        "description": f.evidence_description,
                        "at": f.evidence_submitted_at,
                        "label": "evidence submitted (awaiting mentor review)",
                    }
                    if f.evidence_description
                    else None,
                    mentor_verified={
                        "at": f.mentor_verified_at,
                        "by": f.mentor_verified_by,
                        "label": "mentor-verified",
                    }
                    if f.status == FollowUpStatus.mentor_verified and f.mentor_verified_at
                    else None,
                ),
                flags=flags,
            )
        )
    counts = {
        "total": len(items),
        "overdue": sum(i.overdue for i in items),
        "awaiting_teacher_response": sum(i.category == "awaiting_teacher_response" for i in items),
        "awaiting_mentor_verification": sum(i.category == "awaiting_mentor_verification" for i in items),
        "evidence_missing": sum("evidence_missing" in i.flags for i in items),
        "resolved": sum(i.category == "resolved" for i in items),
    }
    plan_progress = []
    today = now.date()
    for p in snapshot.action_plans:
        related = [f for f in snapshot.followups if f.action_plan_ref == p.id]
        by_status: dict[str, int] = {}
        for f in related:
            by_status[f.status.value] = by_status.get(f.status.value, 0) + 1
        plan_progress.append(
            ActionPlanProgress(
                action_plan_ref=p.id,
                title=p.title,
                status=p.status.value,
                due_date=p.due_date.isoformat() if p.due_date else None,
                due_date_passed=bool(
                    p.due_date and p.due_date < today and p.status.value not in {"completed", "cancelled"}
                ),
                followups_total=len(related),
                followups_by_status=by_status,
                mentor_verified=by_status.get("mentor_verified", 0),
            )
        )
    items.sort(key=lambda i: (not i.overdue, i.due_at or datetime.max.replace(tzinfo=now.tzinfo)))
    return FollowUpAnalysis(items=items, counts=counts, action_plans=plan_progress)

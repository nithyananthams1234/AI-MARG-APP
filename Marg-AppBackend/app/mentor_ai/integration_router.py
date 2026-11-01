"""
Service API consumed by the Mentor Intelligence Engine (MI).

* Authenticated with a dedicated service key (``X-Service-Key``), never a
  user token. Only MI holds this key; it is never sent to the frontend.
* Every call acts on behalf of exactly one mentor: the request session is
  scoped to that mentor's assigned schools / owned records, exactly as if
  the mentor were calling the API. MI cannot read across mentors.
* Writes are limited to the three actions MI may execute *after* a mentor
  approved the proposal in MI, and they reuse the regular route handlers
  (same validation and business rules).
* The backend remains the authoritative store; MI never touches PostgreSQL.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessScope, load_assigned_school_ids, set_scope
from app.auth.role_dependencies import MENTOR_ROLE, get_user_role_names
from app.core.config import settings
from app.database.session import get_db_session
from app.mentor_tasks import router as tasks_router
from app.models.action_plan import ActionPlan
from app.models.action_plan_step import ActionPlanStep
from app.models.follow_up import FollowUp
from app.models.identity import Role, User, UserRole
from app.models.learning_gap import LearningGap
from app.models.mentor_task import MentorTask
from app.models.observation import Observation
from app.models.recommendation import Recommendation
from app.models.schedule import Schedule
from app.models.school import School, SchoolTeacher, Teacher
from app.models.school_visits import SchoolVisit
from app.schemas.mentor_task import MentorTaskUpdate
from app.services.notifications import notify

logger = logging.getLogger("marg.mentor_intelligence")

IST = timezone(timedelta(hours=5, minutes=30))

router = APIRouter(
    prefix="/integrations/mentor-intelligence",
    tags=["Service integration: Mentor Intelligence"],
)


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
async def require_service_key(x_service_key: str | None = Header(default=None)) -> None:
    expected = settings.mentor_intelligence_service_key
    if not expected:
        raise HTTPException(status_code=503, detail="Mentor Intelligence integration is not configured")
    if not x_service_key or not secrets.compare_digest(
        x_service_key.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid service key")


async def mentor_context(
    mentor_id: uuid.UUID,
    _: None = Depends(require_service_key),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Resolve the mentor MI acts for and scope the session to that mentor."""
    user = (
        await db.execute(
            select(User).where(User.id == mentor_id, User.is_active.is_(True), User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None or MENTOR_ROLE not in await get_user_role_names(db, user.id):
        raise HTTPException(status_code=404, detail="Mentor not found")
    set_scope(db, AccessScope(user_id=user.id, school_ids=await load_assigned_school_ids(db, user.id)))
    return user


def _is_demo_database() -> bool:
    return (make_url(settings.database_url).database or "").endswith("_demo")


def _working_days() -> list[int]:
    return [int(x) for x in settings.mentor_default_working_days.split(",") if x.strip()]


def _hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


# --------------------------------------------------------------------------
# Read
# --------------------------------------------------------------------------
@router.get("/mentors", dependencies=[Depends(require_service_key)])
async def list_mentors(db: AsyncSession = Depends(get_db_session)):
    rows = (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == MENTOR_ROLE, User.is_active.is_(True), User.deleted_at.is_(None))
            .order_by(User.full_name)
        )
    ).scalars().all()
    return [
        {"mentor_ref": str(u.id), "name": u.full_name, "role_title": "Mentor", "data_source": "marg"}
        for u in rows
    ]


@router.get("/mentors/{mentor_id}/snapshot")
async def mentor_snapshot(
    mentor: User = Depends(mentor_context),
    db: AsyncSession = Depends(get_db_session),
):
    """All records MI may read for one mentor, in MI's MentorSnapshot shape."""

    async def all_(stmt):
        return (await db.execute(stmt)).scalars().all()

    schools = await all_(select(School).where(School.deleted_at.is_(None)).order_by(School.name))
    school_ids = {s.id for s in schools}

    # Teachers and their (first) school among the mentor's schools.
    links = (
        await db.execute(
            select(SchoolTeacher.teacher_id, SchoolTeacher.school_id).where(
                SchoolTeacher.is_active.is_(True), SchoolTeacher.deleted_at.is_(None)
            )
        )
    ).all()
    teacher_school: dict[uuid.UUID, uuid.UUID] = {}
    for teacher_id, school_id in links:
        if school_id in school_ids:
            teacher_school.setdefault(teacher_id, school_id)
    teachers = await all_(
        select(Teacher).where(Teacher.id.in_(list(teacher_school)), Teacher.deleted_at.is_(None))
    ) if teacher_school else []

    tasks = await all_(select(MentorTask).where(MentorTask.deleted_at.is_(None)))
    visits = await all_(select(SchoolVisit).where(SchoolVisit.deleted_at.is_(None)))
    accepted = await all_(
        select(Schedule).where(Schedule.deleted_at.is_(None), Schedule.status == "accepted")
    )
    visit_end = {s.school_visit_id: s.proposed_end_at for s in accepted}
    visit_school = {v.id: v.school_id for v in visits}

    observations = await all_(select(Observation).where(Observation.deleted_at.is_(None)))
    obs_by_id = {o.id: o for o in observations}
    gaps = await all_(select(LearningGap).where(LearningGap.deleted_at.is_(None)))
    gap_by_id = {g.id: g for g in gaps}
    support: dict[uuid.UUID, list[str]] = {}
    for g in gaps:
        support.setdefault(g.observation_id, []).append(g.title)
    recs = {r.id: r for r in await all_(select(Recommendation).where(Recommendation.deleted_at.is_(None)))}
    plans = await all_(select(ActionPlan).where(ActionPlan.deleted_at.is_(None)))
    steps = {s.id: s for s in await all_(select(ActionPlanStep).where(ActionPlanStep.deleted_at.is_(None)))}
    follow_ups = await all_(select(FollowUp).where(FollowUp.deleted_at.is_(None)))

    def plan_observation(plan: ActionPlan) -> Observation | None:
        rec = recs.get(plan.recommendation_id)
        gap = gap_by_id.get(rec.learning_gap_id) if rec else None
        return obs_by_id.get(gap.observation_id) if gap else None

    plan_info: dict[uuid.UUID, tuple[Observation | None, ActionPlan]] = {
        p.id: (plan_observation(p), p) for p in plans
    }

    blocks = [s.block for s in schools if s.block]
    tz = settings.mentor_default_timezone

    action_plans_out = []
    for p in plans:
        obs = plan_info[p.id][0]
        if obs is None:
            continue
        action_plans_out.append({
            "id": str(p.id),
            "school_ref": str(visit_school.get(obs.school_visit_id)),
            "teacher_ref": str(obs.teacher_id),
            "observation_ref": str(obs.id),
            "title": p.title,
            "status": p.status,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "due_date": p.due_date.isoformat() if p.due_date else None,
        })

    followups_out = []
    for f in follow_ups:
        step = steps.get(f.action_plan_step_id)
        if step is None or step.action_plan_id not in plan_info:
            continue
        obs = plan_info[step.action_plan_id][0]
        if obs is None:
            continue
        verified = f.status in ("mentor_verified", "closed")
        followups_out.append({
            "id": str(f.id),
            "action_plan_ref": str(step.action_plan_id),
            "teacher_ref": str(f.teacher_id),
            "school_ref": str(visit_school.get(obs.school_visit_id)),
            "status": f.status,
            # Follow-ups are due with their action-plan step (end of that day).
            "due_at": datetime.combine(step.due_date, time(23, 59), tzinfo=IST).isoformat() if step.due_date else None,
            "teacher_reported_progress": f.teacher_response,
            "teacher_reported_at": f.responded_at.isoformat() if f.responded_at else None,
            # The backend records evidence as a status transition; its time is the
            # last update while the follow-up is in evidence_submitted.
            "evidence_description": f.teacher_response if f.status == "evidence_submitted" else None,
            "evidence_submitted_at": f.updated_at.isoformat() if f.status == "evidence_submitted" else None,
            "mentor_verified_at": f.verified_at.isoformat() if verified and f.verified_at else None,
            "mentor_verified_by": str(f.updated_by) if verified and f.updated_by else None,
            "last_reminder_at": None,
        })

    school_name = {s.id: s.name for s in schools}
    return {
        "data_source": "marg",
        "is_demo": _is_demo_database(),
        "mentor": {
            "id": str(mentor.id),
            "tenant_ref": "marg",
            "name": mentor.full_name,
            "role_title": "Mentor",
            "block": max(set(blocks), key=blocks.count) if blocks else None,
            "work_start": _hhmm(settings.mentor_default_work_start).isoformat(),
            "work_end": _hhmm(settings.mentor_default_work_end).isoformat(),
            "working_days": _working_days(),
            "timezone": tz,
            "preferred_language": "en",
        },
        "schools": [
            {
                "id": str(s.id), "name": s.name, "village": None, "block": s.block, "school_type": None,
                "travel_minutes_from_base": s.travel_minutes_from_base, "available_days": None,
            }
            for s in schools
        ],
        "teachers": [
            {
                "id": str(t.id), "school_ref": str(teacher_school[t.id]), "name": t.full_name,
                "subject": None, "grades": None, "preferred_language": "en",
            }
            for t in teachers
        ],
        "tasks": [
            {
                "id": str(t.id), "title": t.title, "description": t.description,
                "category": t.category or "general", "status": t.status,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "estimated_minutes": t.estimated_minutes, "urgency": t.urgency, "impact": t.impact, "risk": t.risk,
                "depends_on": [], "school_ref": str(t.school_id) if t.school_id else None,
                "created_at": t.created_at.isoformat(), "updated_at": t.updated_at.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
        "visits": [
            {
                "id": str(v.id), "school_ref": str(v.school_id), "status": v.status,
                "scheduled_start": v.scheduled_at.isoformat(),
                "scheduled_end": (
                    visit_end.get(v.id)
                    or v.scheduled_at + timedelta(minutes=settings.visit_default_duration_minutes)
                ).isoformat(),
                "purpose": v.notes,
                "completed_at": v.completed_at.isoformat() if v.completed_at else None,
            }
            for v in visits
        ],
        "observations": [
            {
                "id": str(o.id), "visit_ref": str(o.school_visit_id),
                "school_ref": str(visit_school.get(o.school_visit_id)), "teacher_ref": str(o.teacher_id),
                "observed_at": o.created_at.isoformat(), "subject": o.subject,
                "mentor_note": o.notes or "", "support_areas": support.get(o.id, []),
            }
            for o in observations
            if o.school_visit_id in visit_school
        ],
        "action_plans": action_plans_out,
        "followups": followups_out,
        "schedule_items": [
            {
                "id": str(s.id), "kind": "school_visit",
                "title": f"Visit: {school_name.get(s.school_id, 'school')}",
                "start_at": s.proposed_start_at.isoformat(), "end_at": s.proposed_end_at.isoformat(),
                "location": school_name.get(s.school_id), "school_ref": str(s.school_id),
            }
            for s in accepted
        ],
        "workload_activities": [],
    }


# --------------------------------------------------------------------------
# Approved actions (executed by MI only after mentor approval)
# --------------------------------------------------------------------------
class ScheduleVisitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    school_ref: uuid.UUID
    start: datetime
    end: datetime
    purpose: str = Field(min_length=1, max_length=2000)
    proposal_ref: str | None = Field(default=None, max_length=64)


class RescheduleVisitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: datetime
    end: datetime
    proposal_ref: str | None = Field(default=None, max_length=64)


class TaskDueDateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    due_at: datetime
    proposal_ref: str | None = Field(default=None, max_length=64)


async def _record_action(db: AsyncSession, mentor: User, title: str, message: str, ref_type: str, ref_id) -> None:
    logger.info("MI approved action executed for mentor=%s: %s (%s %s)", mentor.id, title, ref_type, ref_id)
    await notify(
        db, user_id=mentor.id, title=title, message=message, notification_type="mentor_ai_action",
        reference_entity_type=ref_type, reference_entity_id=ref_id, once=False,
    )
    await db.commit()


async def _sync_accepted_visit_schedules(
    db: AsyncSession, mentor: User, visit: SchoolVisit, start: datetime, end: datetime
) -> None:
    schedules = (
        await db.execute(
            select(Schedule)
            .where(
                Schedule.school_visit_id == visit.id,
                Schedule.status == "accepted",
                Schedule.deleted_at.is_(None),
            )
            .with_for_update()
        )
    ).scalars().all()

    if not schedules:
        db.add(
            Schedule(
                school_visit_id=visit.id,
                school_id=visit.school_id,
                proposed_start_at=start,
                proposed_end_at=end,
                status="accepted",
                created_by=mentor.id,
                updated_by=mentor.id,
            )
        )
        return

    for schedule in schedules:
        schedule.proposed_start_at = start
        schedule.proposed_end_at = end
        schedule.updated_by = mentor.id
        schedule.version += 1


@router.post("/mentors/{mentor_id}/visits", status_code=status.HTTP_201_CREATED)
async def schedule_visit(
    data: ScheduleVisitRequest,
    mentor: User = Depends(mentor_context),
    db: AsyncSession = Depends(get_db_session),
):
    if data.start.tzinfo is None or data.end.tzinfo is None:
        raise HTTPException(status_code=422, detail="start and end must include a timezone")
    if data.end <= data.start:
        raise HTTPException(status_code=422, detail="end must be after start")
    school = (
        await db.execute(
            select(School).where(School.id == data.school_ref, School.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    visit = SchoolVisit(
        school_id=school.id,
        scheduled_at=data.start,
        notes=data.purpose,
        status="planned",
        mentor_id=mentor.id,
        created_by=mentor.id,
        updated_by=mentor.id,
    )
    try:
        db.add(visit)
        await db.flush()
        await _sync_accepted_visit_schedules(db, mentor, visit, data.start, data.end)
        await _record_action(
            db, mentor, "Visit scheduled (Mentor AI)",
            f"A visit you approved was scheduled for {data.start:%d %b %Y %H:%M}.", "school_visit", visit.id,
        )
    except Exception:
        await db.rollback()
        raise

    return {"visit_ref": str(visit.id), "school_ref": str(visit.school_id), "start": data.start.isoformat(),
            "end": data.end.isoformat(), "status": visit.status, "data_source": "marg"}


@router.patch("/mentors/{mentor_id}/visits/{visit_id}/reschedule")
async def reschedule_visit(
    visit_id: uuid.UUID,
    data: RescheduleVisitRequest,
    mentor: User = Depends(mentor_context),
    db: AsyncSession = Depends(get_db_session),
):
    if data.start.tzinfo is None or data.end.tzinfo is None:
        raise HTTPException(status_code=422, detail="start and end must include a timezone")
    if data.end <= data.start:
        raise HTTPException(status_code=422, detail="end must be after start")
    current = (
        await db.execute(
            select(SchoolVisit)
            .where(SchoolVisit.id == visit_id, SchoolVisit.deleted_at.is_(None))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if current is None:
        raise HTTPException(status_code=404, detail="School visit not found")
    if current.status != "planned":
        raise HTTPException(status_code=409, detail="Only planned visits can be updated")

    previous_start = current.scheduled_at
    try:
        current.scheduled_at = data.start
        current.updated_by = mentor.id
        current.version += 1
        await _sync_accepted_visit_schedules(db, mentor, current, data.start, data.end)
        await _record_action(
            db, mentor, "Visit rescheduled (Mentor AI)",
            f"A visit you approved was moved to {data.start:%d %b %Y %H:%M}.", "school_visit", current.id,
        )
    except Exception:
        await db.rollback()
        raise

    return {
        "visit_ref": str(current.id),
        "previous": {"start": previous_start.isoformat()},
        "new": {"start": data.start.isoformat(), "end": data.end.isoformat()},
        "data_source": "marg",
    }


@router.patch("/mentors/{mentor_id}/tasks/{task_id}/due-date")
async def update_task_due_date(
    task_id: uuid.UUID,
    data: TaskDueDateRequest,
    mentor: User = Depends(mentor_context),
    db: AsyncSession = Depends(get_db_session),
):
    current = (
        await db.execute(select(MentorTask).where(MentorTask.id == task_id, MentorTask.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if current is None:
        raise HTTPException(status_code=404, detail="Task not found")
    previous = current.due_at
    task = await tasks_router.update_mentor_task(
        task_id=task_id, payload=MentorTaskUpdate(due_at=data.due_at), db=db, current_user=mentor,
    )
    await _record_action(
        db, mentor, "Task due date changed (Mentor AI)",
        f"'{task.title}' is now due {data.due_at:%d %b %Y %H:%M}.", "mentor_task", task.id,
    )
    return {"task_ref": str(task.id), "previous_due_at": previous.isoformat() if previous else None,
            "new_due_at": data.due_at.isoformat(), "data_source": "marg"}

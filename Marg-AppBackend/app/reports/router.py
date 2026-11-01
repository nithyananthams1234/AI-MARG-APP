"""Mentor reports.

All queries run on a request session that is automatically restricted to
the mentor's assigned schools (app.auth.access), so every number here is
computed from the mentor's own, non-deleted database records.
"""

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.action_plan import ActionPlan
from app.models.action_plan_step import ActionPlanStep
from app.models.follow_up import FollowUp
from app.models.identity import User
from app.models.learning_gap import LearningGap
from app.models.mentor_task import MentorTask
from app.models.notifications import Notification
from app.models.observation import Observation
from app.models.recommendation import Recommendation
from app.models.school import School
from app.models.school_visits import SchoolVisit
from app.schemas.reports import (
    ActivityDay,
    ActivityReportResponse,
    LearningGapReportItem,
    MentorDashboardResponse,
    SchoolReportResponse,
)

router = APIRouter(
    prefix="/reports",
    tags=["Reports and Analytics"],
)

OPEN_FOLLOW_UP = ("pending", "teacher_responded", "evidence_submitted", "needs_revision")
ACTIVE_PLAN = ("approved", "in_progress", "overdue")


def _visits(school_id: UUID | None = None):
    q = select(SchoolVisit.id).where(SchoolVisit.deleted_at.is_(None))
    if school_id is not None:
        q = q.where(SchoolVisit.school_id == school_id)
    return q


def _observations(school_id: UUID | None = None):
    return select(Observation.id).where(
        Observation.deleted_at.is_(None),
        Observation.school_visit_id.in_(_visits(school_id)),
    )


def _gaps(school_id: UUID | None = None):
    return select(LearningGap.id).where(
        LearningGap.deleted_at.is_(None),
        LearningGap.observation_id.in_(_observations(school_id)),
    )


def _plans(school_id: UUID | None = None):
    recs = select(Recommendation.id).where(
        Recommendation.deleted_at.is_(None),
        Recommendation.learning_gap_id.in_(_gaps(school_id)),
    )
    return select(ActionPlan.id).where(
        ActionPlan.deleted_at.is_(None), ActionPlan.recommendation_id.in_(recs)
    )


def _follow_ups(school_id: UUID | None = None):
    steps = select(ActionPlanStep.id).where(
        ActionPlanStep.deleted_at.is_(None),
        ActionPlanStep.action_plan_id.in_(_plans(school_id)),
    )
    return select(FollowUp.id).where(
        FollowUp.deleted_at.is_(None), FollowUp.action_plan_step_id.in_(steps)
    )


async def _count(db: AsyncSession, model, *where) -> int:
    return (await db.execute(select(func.count(model.id)).where(*where))).scalar_one()


@router.get("/dashboard", response_model=MentorDashboardResponse)
async def mentor_dashboard(
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    now = datetime.now(timezone.utc)

    total_schools = await _count(db, School, School.deleted_at.is_(None))
    visit_live = SchoolVisit.deleted_at.is_(None)
    task_live = MentorTask.deleted_at.is_(None)

    return MentorDashboardResponse(
        total_schools=total_schools,
        total_visits=await _count(db, SchoolVisit, visit_live),
        completed_visits=await _count(db, SchoolVisit, visit_live, SchoolVisit.status == "completed"),
        upcoming_visits=await _count(
            db, SchoolVisit, visit_live, SchoolVisit.status == "planned", SchoolVisit.scheduled_at >= now
        ),
        pending_tasks=await _count(
            db, MentorTask, task_live, MentorTask.status.in_(["pending", "in_progress"])
        ),
        completed_tasks=await _count(db, MentorTask, task_live, MentorTask.status == "completed"),
        overdue_tasks=await _count(
            db,
            MentorTask,
            task_live,
            MentorTask.status.in_(["pending", "in_progress"]),
            MentorTask.due_at < now,
        ),
        total_observations=await _count(db, Observation, Observation.id.in_(_observations())),
        total_learning_gaps=await _count(db, LearningGap, LearningGap.id.in_(_gaps())),
        recommendations_awaiting_review=await _count(
            db,
            Recommendation,
            Recommendation.deleted_at.is_(None),
            Recommendation.status == "ai_suggested",
            Recommendation.learning_gap_id.in_(_gaps()),
        ),
        total_action_plans=await _count(db, ActionPlan, ActionPlan.id.in_(_plans())),
        active_action_plans=await _count(
            db, ActionPlan, ActionPlan.id.in_(_plans()), ActionPlan.status.in_(ACTIVE_PLAN)
        ),
        open_follow_ups=await _count(
            db, FollowUp, FollowUp.id.in_(_follow_ups()), FollowUp.status.in_(OPEN_FOLLOW_UP)
        ),
        follow_ups_awaiting_verification=await _count(
            db, FollowUp, FollowUp.id.in_(_follow_ups()), FollowUp.status == "evidence_submitted"
        ),
        unread_notifications=await _count(
            db, Notification, Notification.user_id == current_user.id, Notification.is_read.is_(False)
        ),
    )


@router.get(
    "/schools/{school_id}",
    response_model=SchoolReportResponse,
)
async def school_report(
    school_id: UUID,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    school = (
        await db.execute(
            select(School).where(School.id == school_id, School.deleted_at.is_(None))
        )
    ).scalar_one_or_none()

    # Unassigned schools are invisible to the scoped session -> 404.
    if school is None:
        raise HTTPException(status_code=404, detail="School not found.")

    return SchoolReportResponse(
        school_id=school.id,
        school_name=school.name,
        total_visits=await _count(db, SchoolVisit, SchoolVisit.id.in_(_visits(school_id))),
        completed_visits=await _count(
            db, SchoolVisit, SchoolVisit.id.in_(_visits(school_id)), SchoolVisit.status == "completed"
        ),
        total_observations=await _count(db, Observation, Observation.id.in_(_observations(school_id))),
        total_learning_gaps=await _count(db, LearningGap, LearningGap.id.in_(_gaps(school_id))),
        open_learning_gaps=await _count(
            db, LearningGap, LearningGap.id.in_(_gaps(school_id)), LearningGap.status != "resolved"
        ),
        total_action_plans=await _count(db, ActionPlan, ActionPlan.id.in_(_plans(school_id))),
        completed_action_plans=await _count(
            db, ActionPlan, ActionPlan.id.in_(_plans(school_id)), ActionPlan.status == "completed"
        ),
        open_follow_ups=await _count(
            db,
            FollowUp,
            FollowUp.id.in_(_follow_ups(school_id)),
            FollowUp.status.in_(OPEN_FOLLOW_UP),
        ),
    )


@router.get("/learning-gaps", response_model=list[LearningGapReportItem])
async def learning_gap_report(
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    sev = LearningGap.severity
    result = await db.execute(
        select(
            School.id,
            School.name,
            func.count(LearningGap.id),
            func.count(LearningGap.id).filter(sev == "critical"),
            func.count(LearningGap.id).filter(sev == "high"),
            func.count(LearningGap.id).filter(sev == "medium"),
            func.count(LearningGap.id).filter(sev == "low"),
            func.count(LearningGap.id).filter(LearningGap.status == "resolved"),
        )
        .join(SchoolVisit, SchoolVisit.school_id == School.id)
        .join(Observation, Observation.school_visit_id == SchoolVisit.id)
        .join(LearningGap, LearningGap.observation_id == Observation.id)
        .where(
            School.deleted_at.is_(None),
            SchoolVisit.deleted_at.is_(None),
            Observation.deleted_at.is_(None),
            LearningGap.deleted_at.is_(None),
        )
        .group_by(School.id, School.name)
        .order_by(School.name)
    )

    return [
        LearningGapReportItem(
            school_id=row[0],
            school_name=row[1],
            total_learning_gaps=row[2],
            critical_severity=row[3],
            high_severity=row[4],
            medium_severity=row[5],
            low_severity=row[6],
            resolved=row[7],
        )
        for row in result.all()
    ]


@router.get("/activity", response_model=ActivityReportResponse)
async def activity_report(
    days: int = Query(default=7, ge=1, le=90),
    end_date: date | None = None,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    """Per-day counts of completed visits, recorded observations and completed tasks."""
    end = end_date or datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    lo = datetime.combine(start, time.min, tzinfo=timezone.utc)
    hi = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)

    async def per_day(column, *where) -> dict[date, int]:
        day = cast(column, Date)
        rows = await db.execute(
            select(day, func.count()).where(column >= lo, column < hi, *where).group_by(day)
        )
        return {r[0]: r[1] for r in rows.all()}

    visits = await per_day(
        SchoolVisit.completed_at, SchoolVisit.deleted_at.is_(None), SchoolVisit.status == "completed"
    )
    observations = await per_day(Observation.created_at, Observation.deleted_at.is_(None))
    tasks = await per_day(
        MentorTask.completed_at, MentorTask.deleted_at.is_(None), MentorTask.status == "completed"
    )

    return ActivityReportResponse(
        start_date=start,
        end_date=end,
        days=[
            ActivityDay(
                day=d,
                visits_completed=visits.get(d, 0),
                observations_recorded=observations.get(d, 0),
                tasks_completed=tasks.get(d, 0),
            )
            for d in (start + timedelta(days=i) for i in range(days))
        ],
    )

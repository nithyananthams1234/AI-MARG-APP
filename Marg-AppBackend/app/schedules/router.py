
import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.schedule import Schedule
from app.models.school_visits import SchoolVisit
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleDecision,
    ScheduleResponse,
)
from app.services.scheduling import (
    calculate_daily_workload,
    calculate_visit_duration_minutes,
)


router = APIRouter(prefix="/schedules", tags=["Schedules"])


async def get_active_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession,
) -> Schedule:
    result = await db.execute(
        select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.deleted_at.is_(None),
        )
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        raise HTTPException(
            status_code=404,
            detail="Schedule not found.",
        )

    return schedule


@router.post(
    "/",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule_proposal(
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(SchoolVisit).where(
            SchoolVisit.id == payload.school_visit_id,
            SchoolVisit.deleted_at.is_(None),
        )
    )
    visit = result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=404,
            detail="School visit not found.",
        )

    if visit.status != "planned":
        raise HTTPException(
            status_code=409,
            detail="Only planned school visits can receive schedule proposals.",
        )

    if (
        visit.scheduled_at is not None
        and visit.scheduled_at.tzinfo is None
    ):
        raise HTTPException(
            status_code=409,
            detail="The existing visit schedule has an invalid timezone.",
        )

    schedule = Schedule(
        school_visit_id=visit.id,
        school_id=visit.school_id,
        proposed_start_at=payload.proposed_start_at,
        proposed_end_at=payload.proposed_end_at,
        notes=payload.notes,
        status="proposed",
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    return schedule


@router.get("/", response_model=list[ScheduleResponse])
async def list_schedules(
    school_id: uuid.UUID | None = None,
    schedule_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(proposed|accepted|rejected)$",
    ),
    school_visit_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(Schedule).where(
        Schedule.deleted_at.is_(None)
    )

    if school_id is not None:
        query = query.where(Schedule.school_id == school_id)

    if schedule_status is not None:
        query = query.where(Schedule.status == schedule_status)

    if school_visit_id is not None:
        query = query.where(
            Schedule.school_visit_id == school_visit_id
        )

    query = query.order_by(Schedule.proposed_start_at.asc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/workload/daily")
async def get_daily_workload(
    workload_date: date,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    day_start = datetime.combine(
        workload_date,
        time.min,
        tzinfo=timezone.utc,
    )
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(Schedule).where(
            Schedule.status == "accepted",
            Schedule.deleted_at.is_(None),
            # Workload is per mentor: only schedules this mentor created.
            Schedule.created_by == current_user.id,
            Schedule.proposed_start_at < day_end,
            Schedule.proposed_end_at > day_start,
        )
    )

    schedules = result.scalars().all()

    durations = [
        calculate_visit_duration_minutes(
            max(schedule.proposed_start_at, day_start),
            min(schedule.proposed_end_at, day_end),
        )
        for schedule in schedules
    ]

    workload = calculate_daily_workload(durations)

    return {
        "date": workload_date,
        **workload,
    }


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    return await get_active_schedule(schedule_id, db)


@router.patch(
    "/{schedule_id}/decision",
    response_model=ScheduleResponse,
)
async def decide_schedule(
    schedule_id: uuid.UUID,
    payload: ScheduleDecision,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    schedule = await get_active_schedule(schedule_id, db)

    if schedule.status != "proposed":
        raise HTTPException(
            status_code=409,
            detail="Only proposed schedules can be accepted or rejected.",
        )

    if payload.status == "rejected":
        schedule.status = "rejected"
        schedule.updated_by = current_user.id

        await db.commit()
        await db.refresh(schedule)

        return schedule

    result = await db.execute(
        select(SchoolVisit).where(
            SchoolVisit.id == schedule.school_visit_id,
            SchoolVisit.deleted_at.is_(None),
        )
    )
    visit = result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=404,
            detail="Associated school visit not found.",
        )

    if visit.status != "planned":
        raise HTTPException(
            status_code=409,
            detail="Only planned school visits can be rescheduled.",
        )

    # Check for overlap with other accepted schedule proposals.
    overlap_result = await db.execute(
        select(Schedule.id).where(
            Schedule.id != schedule.id,
            Schedule.school_id == schedule.school_id,
            Schedule.status == "accepted",
            Schedule.deleted_at.is_(None),
            Schedule.proposed_start_at < schedule.proposed_end_at,
            Schedule.proposed_end_at > schedule.proposed_start_at,
        )
    )

    if overlap_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="This proposal overlaps an accepted schedule.",
        )

    # Update the visit only after explicit acceptance.
    visit.scheduled_at = schedule.proposed_start_at

    schedule.status = "accepted"
    schedule.updated_by = current_user.id
    visit.updated_by = current_user.id

    await db.commit()
    await db.refresh(schedule)

    return schedule


from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.school import School
from app.models.school_visits import SchoolVisit
from app.schemas.school_visit import (
    SchoolVisitCreate,
    SchoolVisitUpdate,
    SchoolVisitStatusUpdate,
    SchoolVisitResponse,
)

router = APIRouter(
    prefix="/school-visits",
    tags=["School Visits"],
)


@router.post(
    "/",
    response_model=SchoolVisitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_school_visit(
    visit_data: SchoolVisitCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    school_result = await db.execute(
        select(School).where(
            School.id == visit_data.school_id,
            School.deleted_at.is_(None),
        )
    )

    if school_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    if visit_data.scheduled_at.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scheduled_at must include a timezone",
        )

    visit = SchoolVisit(
        **visit_data.model_dump(),
        status="planned",
        mentor_id=current_user.id,
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(visit)

    await db.commit()
    await db.refresh(visit)

    return visit


@router.get(
    "/",
    response_model=list[SchoolVisitResponse],
)
async def list_school_visits(
    school_id: UUID | None = None,
    visit_status: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(SchoolVisit).where(
        SchoolVisit.deleted_at.is_(None)
    )

    if school_id is not None:
        query = query.where(
            SchoolVisit.school_id == school_id
        )

    if visit_status is not None:
        allowed_statuses = {
            "planned",
            "in_progress",
            "completed",
            "cancelled",
        }

        if visit_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid visit status",
            )

        query = query.where(
            SchoolVisit.status == visit_status
        )

    result = await db.execute(
        query.order_by(SchoolVisit.scheduled_at.desc())
    )

    return result.scalars().all()


@router.get(
    "/{visit_id}",
    response_model=SchoolVisitResponse,
)
async def get_school_visit(
    visit_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(SchoolVisit).where(
            SchoolVisit.id == visit_id,
            SchoolVisit.deleted_at.is_(None),
        )
    )

    visit = result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School visit not found",
        )

    return visit


@router.put(
    "/{visit_id}",
    response_model=SchoolVisitResponse,
)
async def update_school_visit(
    visit_id: UUID,
    visit_data: SchoolVisitUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(SchoolVisit).where(
            SchoolVisit.id == visit_id,
            SchoolVisit.deleted_at.is_(None),
        )
    )

    visit = result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School visit not found",
        )

    if visit.status != "planned":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only planned visits can be updated",
        )

    update_data = visit_data.model_dump(exclude_unset=True)

    if "scheduled_at" in update_data:
        scheduled_at = update_data["scheduled_at"]

        if scheduled_at is not None and scheduled_at.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="scheduled_at must include a timezone",
            )

    for field, value in update_data.items():
        setattr(visit, field, value)

    visit.updated_by = current_user.id
    visit.version += 1

    await db.commit()
    await db.refresh(visit)

    return visit


@router.patch(
    "/{visit_id}/status",
    response_model=SchoolVisitResponse,
)
async def update_school_visit_status(
    visit_id: UUID,
    status_data: SchoolVisitStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(SchoolVisit).where(
            SchoolVisit.id == visit_id,
            SchoolVisit.deleted_at.is_(None),
        )
    )

    visit = result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School visit not found",
        )

    new_status = status_data.status

    allowed_transitions = {
        "planned": {"in_progress", "cancelled"},
        "in_progress": {"completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }

    if new_status not in allowed_transitions[visit.status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot change visit status from {visit.status} to {new_status}",
        )

    now = datetime.now(timezone.utc)

    if new_status == "in_progress":
        visit.started_at = now

    elif new_status == "completed":
        visit.completed_at = now

    visit.status = new_status
    visit.updated_by = current_user.id
    visit.version += 1

    await db.commit()
    await db.refresh(visit)

    return visit

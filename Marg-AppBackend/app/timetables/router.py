
from datetime import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.classroom import Classroom
from app.models.identity import User
from app.models.school import Teacher
from app.models.timetable import Timetable
from app.schemas.timetable import (
    TimetableCreate,
    TimetableUpdate,
    TimetableResponse,
)

router = APIRouter(
    prefix="/timetables",
    tags=["Timetables"],
)


async def validate_references(
    db: AsyncSession,
    classroom_id: UUID,
    teacher_id: UUID | None = None,
):
    classroom_result = await db.execute(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.deleted_at.is_(None),
        )
    )

    if classroom_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found",
        )

    if teacher_id is not None:
        teacher_result = await db.execute(
            select(Teacher).where(
                Teacher.id == teacher_id,
                Teacher.is_active.is_(True),
                Teacher.deleted_at.is_(None),
            )
        )

        if teacher_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active teacher not found",
            )


@router.post(
    "/",
    response_model=TimetableResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_timetable(
    timetable_data: TimetableCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    await validate_references(
        db,
        timetable_data.classroom_id,
        timetable_data.teacher_id,
    )

    timetable = Timetable(
        **timetable_data.model_dump(),
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(timetable)

    try:
        await db.commit()
        await db.refresh(timetable)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A timetable entry already exists for this classroom, day and period",
        )

    return timetable


@router.get(
    "/",
    response_model=list[TimetableResponse],
)
async def list_timetables(
    classroom_id: UUID | None = None,
    day_of_week: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(Timetable).where(
        Timetable.deleted_at.is_(None)
    )

    if classroom_id is not None:
        query = query.where(
            Timetable.classroom_id == classroom_id
        )

    if day_of_week is not None:
        query = query.where(
            Timetable.day_of_week == day_of_week
        )

    result = await db.execute(
        query.order_by(
            Timetable.day_of_week,
            Timetable.period_number,
        )
    )

    return result.scalars().all()


@router.get(
    "/{timetable_id}",
    response_model=TimetableResponse,
)
async def get_timetable(
    timetable_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Timetable).where(
            Timetable.id == timetable_id,
            Timetable.deleted_at.is_(None),
        )
    )

    timetable = result.scalar_one_or_none()

    if timetable is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable entry not found",
        )

    return timetable


@router.put(
    "/{timetable_id}",
    response_model=TimetableResponse,
)
async def update_timetable(
    timetable_id: UUID,
    timetable_data: TimetableUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Timetable).where(
            Timetable.id == timetable_id,
            Timetable.deleted_at.is_(None),
        )
    )

    timetable = result.scalar_one_or_none()

    if timetable is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable entry not found",
        )

    update_data = timetable_data.model_dump(exclude_unset=True)

    new_start = update_data.get("start_time", timetable.start_time)
    new_end = update_data.get("end_time", timetable.end_time)

    if new_start is not None and new_end is not None:
        if new_end <= new_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End time must be after start time",
            )

    new_teacher_id = update_data.get(
        "teacher_id",
        timetable.teacher_id,
    )

    await validate_references(
        db,
        timetable.classroom_id,
        new_teacher_id,
    )

    for field, value in update_data.items():
        setattr(timetable, field, value)

    timetable.updated_by = current_user.id
    timetable.version += 1

    try:
        await db.commit()
        await db.refresh(timetable)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A timetable entry already exists for this classroom, day and period",
        )

    return timetable


@router.delete(
    "/{timetable_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_timetable(
    timetable_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Timetable).where(
            Timetable.id == timetable_id,
            Timetable.deleted_at.is_(None),
        )
    )

    timetable = result.scalar_one_or_none()

    if timetable is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable entry not found",
        )

    from datetime import datetime, timezone

    timetable.deleted_at = datetime.now(timezone.utc)
    timetable.updated_by = current_user.id
    timetable.version += 1

    await db.commit()


from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.classroom import Classroom
from app.models.school import School
from app.models.identity import User
from app.schemas.classroom import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomResponse,
)

router = APIRouter(
    prefix="/classrooms",
    tags=["Classrooms"],
)


@router.post(
    "/",
    response_model=ClassroomResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_classroom(
    classroom_data: ClassroomCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    school_result = await db.execute(
        select(School).where(
            School.id == classroom_data.school_id,
            School.deleted_at.is_(None),
        )
    )
    school = school_result.scalar_one_or_none()

    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    classroom = Classroom(
        **classroom_data.model_dump(),
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(classroom)

    try:
        await db.commit()
        await db.refresh(classroom)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A classroom with this name already exists in this school",
        )

    return classroom


@router.get(
    "/",
    response_model=list[ClassroomResponse],
)
async def list_classrooms(
    school_id: UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(Classroom).where(
        Classroom.deleted_at.is_(None)
    )

    if school_id is not None:
        query = query.where(Classroom.school_id == school_id)

    result = await db.execute(
        query.order_by(Classroom.name)
    )

    return result.scalars().all()


@router.get(
    "/{classroom_id}",
    response_model=ClassroomResponse,
)
async def get_classroom(
    classroom_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.deleted_at.is_(None),
        )
    )

    classroom = result.scalar_one_or_none()

    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found",
        )

    return classroom


@router.put(
    "/{classroom_id}",
    response_model=ClassroomResponse,
)
async def update_classroom(
    classroom_id: UUID,
    classroom_data: ClassroomUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.deleted_at.is_(None),
        )
    )

    classroom = result.scalar_one_or_none()

    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found",
        )

    update_data = classroom_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(classroom, field, value)

    classroom.updated_by = current_user.id
    classroom.version += 1

    try:
        await db.commit()
        await db.refresh(classroom)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A classroom with this name already exists in this school",
        )

    return classroom

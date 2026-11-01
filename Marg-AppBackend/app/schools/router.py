
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_admin, get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.school import School
from app.schemas.school import (
    SchoolCreate,
    SchoolUpdate,
    SchoolResponse,
)

router = APIRouter(
    prefix="/schools",
    tags=["School Management"],
)


@router.post(
    "/",
    response_model=SchoolResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_school(
    school_data: SchoolCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_admin),
):
    school = School(
        **school_data.model_dump(),
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(school)

    try:
        await db.commit()
        await db.refresh(school)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A school with this code already exists.",
        )

    return school


@router.get("/", response_model=list[SchoolResponse])
async def get_schools(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(School)
        .where(School.deleted_at.is_(None))
        .order_by(School.name)
    )

    return result.scalars().all()


@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(School).where(
            School.id == school_id,
            School.deleted_at.is_(None),
        )
    )

    school = result.scalar_one_or_none()

    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found.",
        )

    return school


@router.put("/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: UUID,
    school_data: SchoolUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_admin),
):
    result = await db.execute(
        select(School).where(
            School.id == school_id,
            School.deleted_at.is_(None),
        )
    )

    school = result.scalar_one_or_none()

    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found.",
        )

    update_data = school_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is None and field in {"name", "code", "is_active"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null.",
            )
        setattr(school, field, value)

    school.updated_by = current_user.id
    school.version += 1

    try:
        await db.commit()
        await db.refresh(school)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A school with this code already exists.",
        )

    return school


from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.school import School, Teacher, SchoolTeacher
from app.schemas.teacher import (
    TeacherCreate,
    TeacherUpdate,
    TeacherResponse,
    TeacherSchoolAssign,
    TeacherSchoolResponse,
)

router = APIRouter(
    prefix="/teachers",
    tags=["Teacher Management"],
)


# Create Teacher
@router.post(
    "/",
    response_model=TeacherResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_teacher(
    teacher_data: TeacherCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    teacher = Teacher(
        **teacher_data.model_dump(),
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(teacher)

    try:
        await db.commit()
        await db.refresh(teacher)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee code already exists.",
        )

    return teacher


# Get All Teachers
@router.get("/", response_model=list[TeacherResponse])
async def get_teachers(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Teacher)
        .where(Teacher.deleted_at.is_(None))
        .order_by(Teacher.full_name)
    )

    return result.scalars().all()


# Get Teacher by ID
@router.get("/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(
    teacher_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Teacher).where(
            Teacher.id == teacher_id,
            Teacher.deleted_at.is_(None),
        )
    )

    teacher = result.scalar_one_or_none()

    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found.",
        )

    return teacher


# Update Teacher
@router.put("/{teacher_id}", response_model=TeacherResponse)
async def update_teacher(
    teacher_id: UUID,
    teacher_data: TeacherUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Teacher).where(
            Teacher.id == teacher_id,
            Teacher.deleted_at.is_(None),
        )
    )

    teacher = result.scalar_one_or_none()

    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found.",
        )

    update_data = teacher_data.model_dump(exclude_unset=True)

    if update_data.get("full_name") is None and "full_name" in update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Teacher name cannot be null.",
        )

    for field, value in update_data.items():
        setattr(teacher, field, value)

    teacher.updated_by = current_user.id
    teacher.version += 1

    try:
        await db.commit()
        await db.refresh(teacher)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee code already exists.",
        )

    return teacher


# Assign Teacher to School
@router.post(
    "/{teacher_id}/schools",
    response_model=TeacherSchoolResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_teacher_to_school(
    teacher_id: UUID,
    assignment_data: TeacherSchoolAssign,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    teacher_result = await db.execute(
        select(Teacher).where(
            Teacher.id == teacher_id,
            Teacher.deleted_at.is_(None),
        )
    )
    teacher = teacher_result.scalar_one_or_none()

    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found.",
        )

    school_result = await db.execute(
        select(School).where(
            School.id == assignment_data.school_id,
            School.deleted_at.is_(None),
        )
    )
    school = school_result.scalar_one_or_none()

    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found.",
        )

    existing_result = await db.execute(
        select(SchoolTeacher).where(
            SchoolTeacher.teacher_id == teacher_id,
            SchoolTeacher.school_id == assignment_data.school_id,
        )
    )
    existing_assignment = existing_result.scalar_one_or_none()

    if existing_assignment is not None:
        if existing_assignment.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Teacher is already assigned to this school.",
            )

        existing_assignment.is_active = True
        existing_assignment.assigned_from = assignment_data.assigned_from
        existing_assignment.assigned_until = assignment_data.assigned_until
        existing_assignment.updated_by = current_user.id
        existing_assignment.version += 1

        await db.commit()
        await db.refresh(existing_assignment)

        return existing_assignment

    assignment = SchoolTeacher(
        teacher_id=teacher_id,
        school_id=assignment_data.school_id,
        assigned_from=assignment_data.assigned_from,
        assigned_until=assignment_data.assigned_until,
        is_active=True,
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(assignment)

    try:
        await db.commit()
        await db.refresh(assignment)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Teacher assignment already exists.",
        )

    return assignment

school_teacher_router = APIRouter(
    prefix="/schools",
    tags=["School Management"],
)


@school_teacher_router.get(
    "/{school_id}/teachers",
    response_model=list[TeacherResponse],
)
async def get_school_teachers(
    school_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    school_result = await db.execute(
        select(School).where(
            School.id == school_id,
            School.deleted_at.is_(None),
        )
    )

    school = school_result.scalar_one_or_none()

    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found.",
        )

    result = await db.execute(
        select(Teacher)
        .join(
            SchoolTeacher,
            SchoolTeacher.teacher_id == Teacher.id,
        )
        .where(
            SchoolTeacher.school_id == school_id,
            SchoolTeacher.is_active.is_(True),
            Teacher.is_active.is_(True),
            Teacher.deleted_at.is_(None),
        )
        .order_by(Teacher.full_name)
    )

    return result.scalars().all()

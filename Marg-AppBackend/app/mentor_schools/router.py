from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_admin, get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User, UserRole, Role
from app.models.school import School
from app.models.mentor_school import MentorSchool
from app.schemas.mentor_school import (
    MentorSchoolCreate,
    MentorSchoolUpdate,
    MentorSchoolResponse,
)

# Assignment changes are system administration (Administrator role);
# mentors can only read their own assignments.
router = APIRouter(
    prefix="/mentor-schools",
    tags=["Mentor School Assignments"],
)


@router.post("/", response_model=MentorSchoolResponse, status_code=201)
async def create_assignment(
    data: MentorSchoolCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_admin),
):
    user_result = await db.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.id == data.user_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Role.name == "Mentor",
        )
    )
    mentor = user_result.scalar_one_or_none()

    if mentor is None:
        raise HTTPException(404, "Active Mentor account not found")

    school_result = await db.execute(
        select(School).where(
            School.id == data.school_id,
            School.is_active.is_(True),
            School.deleted_at.is_(None),
        )
    )
    if school_result.scalar_one_or_none() is None:
        raise HTTPException(404, "Active school not found")

    existing = await db.execute(
        select(MentorSchool).where(
            MentorSchool.user_id == data.user_id,
            MentorSchool.school_id == data.school_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "This Mentor–School assignment already exists")

    assignment = MentorSchool(
        **data.model_dump(),
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(assignment)

    try:
        await db.commit()
        await db.refresh(assignment)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Assignment conflicts with an existing record")

    return assignment


@router.get("/", response_model=list[MentorSchoolResponse])
async def list_assignments(
    user_id: UUID | None = None,
    school_id: UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(MentorSchool).where(
        MentorSchool.deleted_at.is_(None)
    )

    # Mentors can only view their own school assignments.
    query = query.where(MentorSchool.user_id == current_user.id)

    if user_id is not None and user_id != current_user.id:
        raise HTTPException(403, "You cannot view another Mentor's assignments")

    if school_id is not None:
        query = query.where(MentorSchool.school_id == school_id)

    result = await db.execute(
        query.order_by(MentorSchool.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{assignment_id}", response_model=MentorSchoolResponse)
async def get_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(MentorSchool).where(
            MentorSchool.id == assignment_id,
            MentorSchool.user_id == current_user.id,
            MentorSchool.deleted_at.is_(None),
        )
    )
    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise HTTPException(404, "Assignment not found")

    return assignment


@router.put("/{assignment_id}", response_model=MentorSchoolResponse)
async def update_assignment(
    assignment_id: UUID,
    data: MentorSchoolUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_admin),
):
    result = await db.execute(
        select(MentorSchool).where(
            MentorSchool.id == assignment_id,
            MentorSchool.deleted_at.is_(None),
        )
    )
    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise HTTPException(404, "Assignment not found")

    updates = data.model_dump(exclude_unset=True)

    new_start = updates.get("assigned_from", assignment.assigned_from)
    new_end = updates.get("assigned_until", assignment.assigned_until)

    if new_start and new_end and new_end < new_start:
        raise HTTPException(422, "Assignment end date cannot precede start date")

    for field, value in updates.items():
        setattr(assignment, field, value)

    assignment.updated_by = current_user.id
    assignment.version += 1

    await db.commit()
    await db.refresh(assignment)

    return assignment


@router.patch("/{assignment_id}/deactivate", response_model=MentorSchoolResponse)
async def deactivate_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_admin),
):
    result = await db.execute(
        select(MentorSchool).where(
            MentorSchool.id == assignment_id,
            MentorSchool.deleted_at.is_(None),
        )
    )
    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise HTTPException(404, "Assignment not found")

    assignment.is_active = False
    assignment.updated_by = current_user.id
    assignment.version += 1

    await db.commit()
    await db.refresh(assignment)

    return assignment
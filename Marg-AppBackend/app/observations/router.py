
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.observation import Observation
from app.models.school_visits import SchoolVisit
from app.models.classroom import Classroom
from app.models.identity import User
from app.models.school import SchoolTeacher
from app.models.school import Teacher

from app.schemas.observation import (
    ObservationCreate,
    ObservationUpdate,
    ObservationStatusUpdate,
    ObservationResponse,
)


router = APIRouter(prefix="/observations", tags=["Observations"])


async def get_observation_or_404(
    observation_id: UUID,
    db: AsyncSession,
) -> Observation:
    result = await db.execute(
        select(Observation).where(
            Observation.id == observation_id,
            Observation.deleted_at.is_(None),
        )
    )
    observation = result.scalar_one_or_none()

    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found",
        )

    return observation


async def validate_observation_references(
    data: ObservationCreate,
    db: AsyncSession,
) -> None:
    visit_result = await db.execute(
        select(SchoolVisit).where(
            SchoolVisit.id == data.school_visit_id,
            SchoolVisit.deleted_at.is_(None),
        )
    )
    visit = visit_result.scalar_one_or_none()

    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School visit not found",
        )

    classroom_result = await db.execute(
        select(Classroom).where(
            Classroom.id == data.classroom_id,
            Classroom.deleted_at.is_(None),
        )
    )
    classroom = classroom_result.scalar_one_or_none()

    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found",
        )

    teacher_result = await db.execute(
        select(Teacher).where(
            Teacher.id == data.teacher_id,
            Teacher.is_active.is_(True),
            Teacher.deleted_at.is_(None),
        )
    )
    teacher = teacher_result.scalar_one_or_none()

    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active teacher not found",
        )

    if classroom.school_id != visit.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Classroom does not belong to the school of this visit",
        )

    assignment_result = await db.execute(
        select(SchoolTeacher.id).where(
            SchoolTeacher.school_id == visit.school_id,
            SchoolTeacher.teacher_id == data.teacher_id,
            SchoolTeacher.is_active.is_(True),
            SchoolTeacher.deleted_at.is_(None),
        )
    )

    if assignment_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teacher is not assigned to the school of this visit",
        )


@router.post(
    "/",
    response_model=ObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_observation(
    data: ObservationCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    await validate_observation_references(data, db)

    observation = Observation(
        school_visit_id=data.school_visit_id,
        teacher_id=data.teacher_id,
        classroom_id=data.classroom_id,
        subject=data.subject,
        topic=data.topic,
        notes=data.notes,
        status="draft",
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(observation)
    await db.commit()
    await db.refresh(observation)

    return observation


@router.get("/", response_model=list[ObservationResponse])
async def list_observations(
    school_visit_id: UUID | None = None,
    teacher_id: UUID | None = None,
    classroom_id: UUID | None = None,
    observation_status: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(Observation).where(
        Observation.deleted_at.is_(None)
    )

    if school_visit_id:
        query = query.where(
            Observation.school_visit_id == school_visit_id
        )

    if teacher_id:
        query = query.where(Observation.teacher_id == teacher_id)

    if classroom_id:
        query = query.where(Observation.classroom_id == classroom_id)

    if observation_status:
        allowed_statuses = {
            "draft",
            "submitted",
            "processed",
            "reviewed",
        }

        if observation_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid observation status",
            )

        query = query.where(
            Observation.status == observation_status
        )

    query = query.order_by(Observation.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{observation_id}", response_model=ObservationResponse)
async def get_observation(
    observation_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    return await get_observation_or_404(observation_id, db)


@router.put("/{observation_id}", response_model=ObservationResponse)
async def update_observation(
    observation_id: UUID,
    data: ObservationUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    observation = await get_observation_or_404(observation_id, db)

    if observation.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft observations can be updated",
        )

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(observation, field, value)

    observation.updated_by = current_user.id
    observation.updated_at = datetime.now(timezone.utc)
    observation.version += 1

    await db.commit()
    await db.refresh(observation)

    return observation


@router.patch(
    "/{observation_id}/status",
    response_model=ObservationResponse,
)
async def update_observation_status(
    observation_id: UUID,
    data: ObservationStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    observation = await get_observation_or_404(observation_id, db)

    allowed_transitions = {
        "draft": ["submitted"],
        "submitted": ["processed"],
        "processed": ["reviewed"],
        "reviewed": [],
    }

    if data.status not in allowed_transitions[observation.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change observation status from {observation.status} to {data.status}",
        )

    observation.status = data.status
    observation.updated_by = current_user.id
    observation.updated_at = datetime.now(timezone.utc)
    observation.version += 1

    await db.commit()
    await db.refresh(observation)

    return observation


@router.delete(
    "/{observation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_observation(
    observation_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    observation = await get_observation_or_404(observation_id, db)

    if observation.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft observations can be deleted",
        )

    observation.deleted_at = datetime.now(timezone.utc)
    observation.updated_by = current_user.id
    observation.updated_at = datetime.now(timezone.utc)
    observation.version += 1

    await db.commit()

    return None

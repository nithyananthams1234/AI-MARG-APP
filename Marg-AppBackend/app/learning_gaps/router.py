
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.observation import Observation
from app.models.observation_finding import ObservationFinding
from app.models.learning_gap import LearningGap
from app.schemas.learning_gap import (
    LearningGapCreate,
    LearningGapUpdate,
    LearningGapStatusUpdate,
    LearningGapResponse,
)

router = APIRouter(
    prefix="/learning-gaps",
    tags=["Learning Gaps"],
)


async def get_active_gap(
    gap_id: UUID,
    db: AsyncSession,
) -> LearningGap:
    result = await db.execute(
        select(LearningGap).where(
            LearningGap.id == gap_id,
            LearningGap.deleted_at.is_(None),
        )
    )
    gap = result.scalar_one_or_none()

    if gap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning gap not found",
        )

    return gap


async def validate_observation(
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


async def validate_finding(
    finding_id: UUID,
    observation_id: UUID,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(ObservationFinding).where(
            ObservationFinding.id == finding_id,
            ObservationFinding.observation_id == observation_id,
            ObservationFinding.deleted_at.is_(None),
        )
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Finding does not belong to this observation or does not exist",
        )


@router.post(
    "/",
    response_model=LearningGapResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_learning_gap(
    payload: LearningGapCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    await validate_observation(payload.observation_id, db)

    if payload.observation_finding_id is not None:
        await validate_finding(
            payload.observation_finding_id,
            payload.observation_id,
            db,
        )

    gap = LearningGap(
        **payload.model_dump(),
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(gap)
    await db.commit()
    await db.refresh(gap)

    return gap


@router.get("/", response_model=list[LearningGapResponse])
async def list_learning_gaps(
    observation_id: UUID | None = None,
    severity: str | None = Query(
        default=None,
        pattern="^(low|medium|high|critical)$",
    ),
    gap_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(identified|addressed|resolved)$",
    ),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(LearningGap).where(
        LearningGap.deleted_at.is_(None)
    )

    if observation_id is not None:
        query = query.where(
            LearningGap.observation_id == observation_id
        )

    if severity is not None:
        query = query.where(LearningGap.severity == severity)

    if gap_status is not None:
        query = query.where(LearningGap.status == gap_status)

    query = query.order_by(LearningGap.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{gap_id}", response_model=LearningGapResponse)
async def get_learning_gap(
    gap_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    return await get_active_gap(gap_id, db)


@router.put("/{gap_id}", response_model=LearningGapResponse)
async def update_learning_gap(
    gap_id: UUID,
    payload: LearningGapUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    gap = await get_active_gap(gap_id, db)

    if gap.status != "identified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only identified learning gaps can be edited",
        )

    updates = payload.model_dump(exclude_unset=True)

    if (
        "observation_finding_id" in updates
        and updates["observation_finding_id"] is not None
    ):
        await validate_finding(
            updates["observation_finding_id"],
            gap.observation_id,
            db,
        )

    for field, value in updates.items():
        setattr(gap, field, value)

    gap.updated_by = current_user.id

    await db.commit()
    await db.refresh(gap)

    return gap


@router.patch(
    "/{gap_id}/status",
    response_model=LearningGapResponse,
)
async def update_learning_gap_status(
    gap_id: UUID,
    payload: LearningGapStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    gap = await get_active_gap(gap_id, db)

    allowed_transitions = {
        "identified": ["addressed"],
        "addressed": ["resolved"],
        "resolved": [],
    }

    if payload.status not in allowed_transitions[gap.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid learning gap status transition",
        )

    gap.status = payload.status
    gap.updated_by = current_user.id

    await db.commit()
    await db.refresh(gap)

    return gap


@router.delete("/{gap_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_learning_gap(
    gap_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    gap = await get_active_gap(gap_id, db)

    if gap.status != "identified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only identified learning gaps can be deleted",
        )

    from datetime import datetime, timezone

    gap.deleted_at = datetime.now(timezone.utc)
    gap.updated_by = current_user.id

    await db.commit()

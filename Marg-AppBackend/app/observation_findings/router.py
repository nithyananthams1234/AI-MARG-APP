
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.observation import Observation
from app.models.observation_finding import ObservationFinding
from app.schemas.observation_finding import (
    ObservationFindingCreate,
    ObservationFindingUpdate,
    ObservationFindingStatusUpdate,
    ObservationFindingResponse,
)

router = APIRouter(
    prefix="/observation-findings",
    tags=["Observation Findings"],
)


async def get_finding_or_404(
    finding_id: UUID,
    db: AsyncSession,
) -> ObservationFinding:
    result = await db.execute(
        select(ObservationFinding).where(
            ObservationFinding.id == finding_id,
            ObservationFinding.deleted_at.is_(None),
        )
    )
    finding = result.scalar_one_or_none()

    if finding is None:
        raise HTTPException(
            status_code=404,
            detail="Observation finding not found",
        )

    return finding


@router.post(
    "/",
    response_model=ObservationFindingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_finding(
    data: ObservationFindingCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Observation).where(
            Observation.id == data.observation_id,
            Observation.deleted_at.is_(None),
        )
    )
    observation = result.scalar_one_or_none()

    if observation is None:
        raise HTTPException(
            status_code=404,
            detail="Observation not found",
        )

    if observation.status == "draft":
        raise HTTPException(
            status_code=400,
            detail="Submit the observation before adding findings",
        )

    finding = ObservationFinding(
        observation_id=data.observation_id,
        title=data.title,
        description=data.description,
        category=data.category,
        status="ai_suggested",
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(finding)
    await db.commit()
    await db.refresh(finding)

    return finding


@router.get("/", response_model=list[ObservationFindingResponse])
async def list_findings(
    observation_id: UUID | None = None,
    finding_status: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(ObservationFinding).where(
        ObservationFinding.deleted_at.is_(None)
    )

    if observation_id:
        query = query.where(
            ObservationFinding.observation_id == observation_id
        )

    if finding_status:
        allowed_statuses = {
            "ai_suggested",
            "mentor_approved",
            "rejected",
        }

        if finding_status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail="Invalid finding status",
            )

        query = query.where(
            ObservationFinding.status == finding_status
        )

    result = await db.execute(
        query.order_by(ObservationFinding.created_at.desc())
    )

    return result.scalars().all()


@router.get("/{finding_id}", response_model=ObservationFindingResponse)
async def get_finding(
    finding_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    return await get_finding_or_404(finding_id, db)


@router.put("/{finding_id}", response_model=ObservationFindingResponse)
async def update_finding(
    finding_id: UUID,
    data: ObservationFindingUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    finding = await get_finding_or_404(finding_id, db)

    if finding.status != "ai_suggested":
        raise HTTPException(
            status_code=400,
            detail="Only suggested findings can be edited",
        )

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(finding, field, value)

    finding.updated_by = current_user.id
    finding.updated_at = datetime.now(timezone.utc)
    finding.version += 1

    await db.commit()
    await db.refresh(finding)

    return finding


@router.patch(
    "/{finding_id}/decision",
    response_model=ObservationFindingResponse,
)
async def decide_finding(
    finding_id: UUID,
    data: ObservationFindingStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    finding = await get_finding_or_404(finding_id, db)

    if finding.status != "ai_suggested":
        raise HTTPException(
            status_code=400,
            detail="Only suggested findings can be approved or rejected",
        )

    finding.status = data.status
    finding.mentor_comment = data.mentor_comment
    finding.updated_by = current_user.id
    finding.updated_at = datetime.now(timezone.utc)
    finding.version += 1

    await db.commit()
    await db.refresh(finding)

    return finding


@router.delete(
    "/{finding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_finding(
    finding_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    finding = await get_finding_or_404(finding_id, db)

    if finding.status != "ai_suggested":
        raise HTTPException(
            status_code=400,
            detail="Only suggested findings can be deleted",
        )

    now = datetime.now(timezone.utc)
    finding.deleted_at = now
    finding.updated_at = now
    finding.updated_by = current_user.id
    finding.version += 1

    await db.commit()
    return None

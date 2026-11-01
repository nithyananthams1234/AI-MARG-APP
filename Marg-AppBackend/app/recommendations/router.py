
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.learning_gap import LearningGap
from app.models.recommendation import Recommendation
from app.schemas.recommendation import (
    RecommendationCreate,
    RecommendationUpdate,
    RecommendationDecision,
    RecommendationResponse,
)

router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"],
)


async def get_active_recommendation(
    recommendation_id: UUID,
    db: AsyncSession,
) -> Recommendation:
    result = await db.execute(
        select(Recommendation).where(
            Recommendation.id == recommendation_id,
            Recommendation.deleted_at.is_(None),
        )
    )
    recommendation = result.scalar_one_or_none()

    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found",
        )

    return recommendation


@router.post(
    "/",
    response_model=RecommendationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recommendation(
    payload: RecommendationCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(LearningGap).where(
            LearningGap.id == payload.learning_gap_id,
            LearningGap.deleted_at.is_(None),
        )
    )
    learning_gap = result.scalar_one_or_none()

    if learning_gap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning gap not found",
        )

    recommendation = Recommendation(
        **payload.model_dump(),
        status="ai_suggested",
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(recommendation)
    await db.commit()
    await db.refresh(recommendation)

    return recommendation


@router.get("/", response_model=list[RecommendationResponse])
async def list_recommendations(
    learning_gap_id: UUID | None = None,
    recommendation_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(ai_suggested|mentor_approved|rejected)$",
    ),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(Recommendation).where(
        Recommendation.deleted_at.is_(None)
    )

    if learning_gap_id is not None:
        query = query.where(
            Recommendation.learning_gap_id == learning_gap_id
        )

    if recommendation_status is not None:
        query = query.where(
            Recommendation.status == recommendation_status
        )

    query = query.order_by(Recommendation.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get(
    "/{recommendation_id}",
    response_model=RecommendationResponse,
)
async def get_recommendation(
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    return await get_active_recommendation(recommendation_id, db)


@router.put(
    "/{recommendation_id}",
    response_model=RecommendationResponse,
)
async def update_recommendation(
    recommendation_id: UUID,
    payload: RecommendationUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    recommendation = await get_active_recommendation(
        recommendation_id,
        db,
    )

    if recommendation.status != "ai_suggested":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only AI-suggested recommendations can be edited",
        )

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(recommendation, field, value)

    recommendation.updated_by = current_user.id

    await db.commit()
    await db.refresh(recommendation)

    return recommendation


@router.patch(
    "/{recommendation_id}/decision",
    response_model=RecommendationResponse,
)
async def decide_recommendation(
    recommendation_id: UUID,
    payload: RecommendationDecision,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    recommendation = await get_active_recommendation(
        recommendation_id,
        db,
    )

    if recommendation.status != "ai_suggested":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only AI-suggested recommendations can be decided",
        )

    recommendation.status = payload.status
    recommendation.mentor_comment = payload.mentor_comment
    recommendation.updated_by = current_user.id

    await db.commit()
    await db.refresh(recommendation)

    return recommendation


@router.delete(
    "/{recommendation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_recommendation(
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    recommendation = await get_active_recommendation(
        recommendation_id,
        db,
    )

    if recommendation.status != "ai_suggested":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only AI-suggested recommendations can be deleted",
        )

    from datetime import datetime, timezone

    recommendation.deleted_at = datetime.now(timezone.utc)
    recommendation.updated_by = current_user.id

    await db.commit()

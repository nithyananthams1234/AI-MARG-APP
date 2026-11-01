
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.recommendation import Recommendation
from app.models.action_plan import ActionPlan
from app.schemas.action_plan import (
    ActionPlanCreate,
    ActionPlanUpdate,
    ActionPlanStatusUpdate,
    ActionPlanResponse,
)

router = APIRouter(
    prefix="/action-plans",
    tags=["Action Plans"],
)


async def get_active_action_plan(
    plan_id: UUID,
    db: AsyncSession,
) -> ActionPlan:
    result = await db.execute(
        select(ActionPlan).where(
            ActionPlan.id == plan_id,
            ActionPlan.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action plan not found",
        )

    return plan


@router.post(
    "/",
    response_model=ActionPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_action_plan(
    payload: ActionPlanCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Recommendation).where(
            Recommendation.id == payload.recommendation_id,
            Recommendation.deleted_at.is_(None),
        )
    )
    recommendation = result.scalar_one_or_none()

    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found",
        )

    if recommendation.status != "mentor_approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only mentor-approved recommendations can have action plans",
        )

    plan = ActionPlan(
        **payload.model_dump(),
        status="draft",
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    return plan


@router.get("/", response_model=list[ActionPlanResponse])
async def list_action_plans(
    recommendation_id: UUID | None = None,
    plan_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(draft|pending_approval|approved|in_progress|completed|overdue|cancelled)$",
    ),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(ActionPlan).where(
        ActionPlan.deleted_at.is_(None)
    )

    if recommendation_id is not None:
        query = query.where(
            ActionPlan.recommendation_id == recommendation_id
        )

    if plan_status is not None:
        query = query.where(ActionPlan.status == plan_status)

    query = query.order_by(ActionPlan.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{plan_id}", response_model=ActionPlanResponse)
async def get_action_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    return await get_active_action_plan(plan_id, db)


@router.put("/{plan_id}", response_model=ActionPlanResponse)
async def update_action_plan(
    plan_id: UUID,
    payload: ActionPlanUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    plan = await get_active_action_plan(plan_id, db)

    if plan.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft action plans can be edited",
        )

    updates = payload.model_dump(exclude_unset=True)

    new_start = updates.get("start_date", plan.start_date)
    new_due = updates.get("due_date", plan.due_date)

    if new_due < new_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Due date cannot be before start date",
        )

    for field, value in updates.items():
        setattr(plan, field, value)

    plan.updated_by = current_user.id

    await db.commit()
    await db.refresh(plan)

    return plan


@router.patch(
    "/{plan_id}/status",
    response_model=ActionPlanResponse,
)
async def update_action_plan_status(
    plan_id: UUID,
    payload: ActionPlanStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    plan = await get_active_action_plan(plan_id, db)

    allowed_transitions = {
        "draft": ["pending_approval", "cancelled"],
        "pending_approval": ["approved", "cancelled"],
        "approved": ["in_progress", "cancelled"],
        "in_progress": ["completed", "overdue", "cancelled"],
        "overdue": ["in_progress", "completed", "cancelled"],
        "completed": [],
        "cancelled": [],
    }

    if payload.status not in allowed_transitions[plan.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action plan status transition",
        )

    if payload.status == "approved":
        plan.mentor_comment = payload.mentor_comment
    elif payload.mentor_comment is not None:
        plan.mentor_comment = payload.mentor_comment

    plan.status = payload.status
    plan.updated_by = current_user.id

    await db.commit()
    await db.refresh(plan)

    return plan


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_action_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    plan = await get_active_action_plan(plan_id, db)

    if plan.status not in ["draft", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft or cancelled action plans can be deleted",
        )

    plan.deleted_at = datetime.now(timezone.utc)
    plan.updated_by = current_user.id

    await db.commit()


from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.action_plan import ActionPlan
from app.models.action_plan_step import ActionPlanStep
from app.schemas.action_plan_step import (
    ActionPlanStepCreate,
    ActionPlanStepUpdate,
    ActionPlanStepStatusUpdate,
    ActionPlanStepResponse,
)

router = APIRouter(
    prefix="/action-plan-steps",
    tags=["Action Plan Steps"],
)


async def get_active_step(
    step_id: UUID,
    db: AsyncSession,
) -> ActionPlanStep:
    result = await db.execute(
        select(ActionPlanStep).where(
            ActionPlanStep.id == step_id,
            ActionPlanStep.deleted_at.is_(None),
        )
    )
    step = result.scalar_one_or_none()

    if step is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action plan step not found",
        )

    return step


@router.post(
    "/",
    response_model=ActionPlanStepResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_action_plan_step(
    payload: ActionPlanStepCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(ActionPlan).where(
            ActionPlan.id == payload.action_plan_id,
            ActionPlan.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action plan not found",
        )

    if plan.status not in ["approved", "in_progress", "overdue"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Steps can only be added to approved or active action plans",
        )

    step = ActionPlanStep(
        **payload.model_dump(),
        status="pending",
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(step)
    await db.commit()
    await db.refresh(step)

    return step


@router.get("/", response_model=list[ActionPlanStepResponse])
async def list_action_plan_steps(
    action_plan_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(ActionPlanStep)
        .where(
            ActionPlanStep.action_plan_id == action_plan_id,
            ActionPlanStep.deleted_at.is_(None),
        )
        .order_by(ActionPlanStep.created_at.asc())
    )

    return result.scalars().all()


@router.get("/{step_id}", response_model=ActionPlanStepResponse)
async def get_action_plan_step(
    step_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    return await get_active_step(step_id, db)


@router.put("/{step_id}", response_model=ActionPlanStepResponse)
async def update_action_plan_step(
    step_id: UUID,
    payload: ActionPlanStepUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    step = await get_active_step(step_id, db)

    if step.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending steps can be edited",
        )

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(step, field, value)

    step.updated_by = current_user.id

    await db.commit()
    await db.refresh(step)

    return step


@router.patch(
    "/{step_id}/status",
    response_model=ActionPlanStepResponse,
)
async def update_action_plan_step_status(
    step_id: UUID,
    payload: ActionPlanStepStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    step = await get_active_step(step_id, db)

    allowed_transitions = {
        "pending": ["in_progress", "cancelled"],
        "in_progress": ["completed", "cancelled"],
        "completed": [],
        "cancelled": [],
    }

    if payload.status not in allowed_transitions[step.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action plan step status transition",
        )

    step.status = payload.status

    if payload.completion_notes is not None:
        step.completion_notes = payload.completion_notes

    step.updated_by = current_user.id

    await db.commit()
    await db.refresh(step)

    return step


@router.delete(
    "/{step_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_action_plan_step(
    step_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    step = await get_active_step(step_id, db)

    if step.status not in ["pending", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending or cancelled steps can be deleted",
        )

    step.deleted_at = datetime.now(timezone.utc)
    step.updated_by = current_user.id

    await db.commit()

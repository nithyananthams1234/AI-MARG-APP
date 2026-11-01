
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.action_plan_step import ActionPlanStep
from app.models.school import Teacher
from app.models.follow_up import FollowUp
from app.schemas.follow_up import (
    FollowUpCreate,
    TeacherFollowUpResponse,
    FollowUpEvidenceSubmission,
    FollowUpMentorDecision,
    FollowUpStatusUpdate,
    FollowUpResponse,
)

router = APIRouter(
    prefix="/follow-ups",
    tags=["Follow-ups"],
)


async def get_active_follow_up(
    follow_up_id: UUID,
    db: AsyncSession,
) -> FollowUp:
    result = await db.execute(
        select(FollowUp).where(
            FollowUp.id == follow_up_id,
            FollowUp.deleted_at.is_(None),
        )
    )
    follow_up = result.scalar_one_or_none()

    if follow_up is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up not found",
        )

    return follow_up


@router.post(
    "/",
    response_model=FollowUpResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_follow_up(
    payload: FollowUpCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    step_result = await db.execute(
        select(ActionPlanStep).where(
            ActionPlanStep.id == payload.action_plan_step_id,
            ActionPlanStep.deleted_at.is_(None),
        )
    )
    step = step_result.scalar_one_or_none()

    if step is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action plan step not found",
        )

    if step.status not in ["pending", "in_progress"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Follow-ups can only be created for pending or active steps",
        )

    teacher_result = await db.execute(
        select(Teacher).where(
            Teacher.id == payload.teacher_id,
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

    follow_up = FollowUp(
        **payload.model_dump(),
        status="pending",
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(follow_up)
    await db.commit()
    await db.refresh(follow_up)

    return follow_up


@router.get("/", response_model=list[FollowUpResponse])
async def list_follow_ups(
    action_plan_step_id: UUID | None = None,
    teacher_id: UUID | None = None,
    follow_up_status: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(FollowUp).where(
        FollowUp.deleted_at.is_(None)
    )

    if action_plan_step_id:
        query = query.where(
            FollowUp.action_plan_step_id == action_plan_step_id
        )

    if teacher_id:
        query = query.where(FollowUp.teacher_id == teacher_id)

    if follow_up_status:
        allowed_statuses = {
            "pending",
            "teacher_responded",
            "evidence_submitted",
            "mentor_verified",
            "needs_revision",
            "closed",
        }
        if follow_up_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid follow-up status",
            )
        query = query.where(FollowUp.status == follow_up_status)

    query = query.order_by(FollowUp.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{follow_up_id}", response_model=FollowUpResponse)
async def get_follow_up(
    follow_up_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    return await get_active_follow_up(follow_up_id, db)


@router.patch(
    "/{follow_up_id}/teacher-response",
    response_model=FollowUpResponse,
)
async def submit_teacher_response(
    follow_up_id: UUID,
    payload: TeacherFollowUpResponse,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    follow_up = await get_active_follow_up(follow_up_id, db)

    if follow_up.status not in ["pending", "needs_revision"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A response can only be submitted for pending or revision-requested follow-ups",
        )

    follow_up.teacher_response = payload.teacher_response
    follow_up.responded_at = datetime.now(timezone.utc)
    follow_up.status = "teacher_responded"
    follow_up.updated_by = current_user.id

    await db.commit()
    await db.refresh(follow_up)

    return follow_up


@router.patch(
    "/{follow_up_id}/evidence",
    response_model=FollowUpResponse,
)
async def submit_follow_up_evidence(
    follow_up_id: UUID,
    payload: FollowUpEvidenceSubmission,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    follow_up = await get_active_follow_up(follow_up_id, db)

    if follow_up.status != "teacher_responded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evidence can only be submitted after a teacher response",
        )

    follow_up.teacher_response = payload.teacher_response
    follow_up.status = "evidence_submitted"
    follow_up.updated_by = current_user.id

    await db.commit()
    await db.refresh(follow_up)

    return follow_up


@router.patch(
    "/{follow_up_id}/mentor-decision",
    response_model=FollowUpResponse,
)
async def mentor_review_follow_up(
    follow_up_id: UUID,
    payload: FollowUpMentorDecision,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    follow_up = await get_active_follow_up(follow_up_id, db)

    if follow_up.status != "evidence_submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only submitted evidence can be reviewed",
        )

    follow_up.status = payload.status
    follow_up.mentor_notes = payload.mentor_notes

    if payload.status == "mentor_verified":
        follow_up.verified_at = datetime.now(timezone.utc)

    follow_up.updated_by = current_user.id

    await db.commit()
    await db.refresh(follow_up)

    return follow_up


@router.patch(
    "/{follow_up_id}/close",
    response_model=FollowUpResponse,
)
async def close_follow_up(
    follow_up_id: UUID,
    payload: FollowUpStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    follow_up = await get_active_follow_up(follow_up_id, db)

    if follow_up.status != "mentor_verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only mentor-verified follow-ups can be closed",
        )

    follow_up.status = payload.status
    follow_up.updated_by = current_user.id

    await db.commit()
    await db.refresh(follow_up)

    return follow_up


@router.delete(
    "/{follow_up_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_follow_up(
    follow_up_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    follow_up = await get_active_follow_up(follow_up_id, db)

    if follow_up.status not in ["pending", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending or cancelled follow-ups can be deleted",
        )

    follow_up.deleted_at = datetime.now(timezone.utc)
    follow_up.updated_by = current_user.id

    await db.commit()

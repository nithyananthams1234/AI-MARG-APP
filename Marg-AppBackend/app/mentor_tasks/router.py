
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.school import School
from app.models.mentor_task import MentorTask
from app.schemas.mentor_task import (
    MentorTaskCreate,
    MentorTaskUpdate,
    MentorTaskStatusUpdate,
    MentorTaskResponse,
)
from app.services.priority import calculate_task_priority


router = APIRouter(prefix="/mentor-tasks", tags=["Mentor Tasks"])


async def get_active_task(
    task_id: uuid.UUID,
    db: AsyncSession,
) -> MentorTask:
    result = await db.execute(
        select(MentorTask).where(
            MentorTask.id == task_id,
            MentorTask.deleted_at.is_(None),
        )
    )
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Mentor task not found.",
        )

    return task


async def validate_school(
    school_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    if school_id is None:
        return

    result = await db.execute(
        select(School.id).where(
            School.id == school_id,
            School.deleted_at.is_(None),
            School.is_active.is_(True),
        )
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404,
            detail="Active school not found.",
        )


def apply_priority(task: MentorTask) -> None:
    priority_data = calculate_task_priority(
        urgency=task.urgency,
        impact=task.impact,
        risk=task.risk,
        deadline_proximity=task.deadline_proximity,
        workload_dependency=task.workload_dependency,
    )

    task.priority_score = priority_data["priority_score"]
    task.priority = priority_data["priority"]


@router.post(
    "/",
    response_model=MentorTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_mentor_task(
    payload: MentorTaskCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    if payload.due_at is not None and payload.due_at.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="due_at must include a timezone.",
        )

    await validate_school(payload.school_id, db)

    task = MentorTask(
        **payload.model_dump(),
        mentor_id=current_user.id,
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    apply_priority(task)

    try:
        db.add(task)
        await db.commit()
        await db.refresh(task)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not create mentor task.",
        )

    return task


@router.get("/", response_model=list[MentorTaskResponse])
async def list_mentor_tasks(
    school_id: uuid.UUID | None = None,
    task_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|in_progress|completed|cancelled)$",
    ),
    priority: str | None = Query(
        default=None,
        pattern="^(low|medium|high|critical)$",
    ),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(MentorTask).where(
        MentorTask.deleted_at.is_(None)
    )

    if school_id is not None:
        query = query.where(MentorTask.school_id == school_id)

    if task_status is not None:
        query = query.where(MentorTask.status == task_status)

    if priority is not None:
        query = query.where(MentorTask.priority == priority)

    query = query.order_by(
        MentorTask.priority_score.desc(),
        MentorTask.created_at.desc(),
    )

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{task_id}", response_model=MentorTaskResponse)
async def get_mentor_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    return await get_active_task(task_id, db)


@router.put("/{task_id}", response_model=MentorTaskResponse)
async def update_mentor_task(
    task_id: uuid.UUID,
    payload: MentorTaskUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    task = await get_active_task(task_id, db)

    if task.status not in ("pending", "in_progress"):
        raise HTTPException(
            status_code=409,
            detail="Only pending or in-progress tasks can be updated.",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if (
        "due_at" in update_data
        and update_data["due_at"] is not None
        and update_data["due_at"].tzinfo is None
    ):
        raise HTTPException(
            status_code=422,
            detail="due_at must include a timezone.",
        )

    if "school_id" in update_data:
        await validate_school(update_data["school_id"], db)

    for field, value in update_data.items():
        setattr(task, field, value)

    apply_priority(task)
    task.updated_by = current_user.id

    try:
        await db.commit()
        await db.refresh(task)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not update mentor task.",
        )

    return task


@router.patch(
    "/{task_id}/status",
    response_model=MentorTaskResponse,
)
async def update_mentor_task_status(
    task_id: uuid.UUID,
    payload: MentorTaskStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    task = await get_active_task(task_id, db)

    allowed_transitions = {
        "pending": {"in_progress", "cancelled"},
        "in_progress": {"completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }

    if payload.status not in allowed_transitions[task.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot change task status from {task.status} to {payload.status}.",
        )

    task.status = payload.status
    task.updated_by = current_user.id

    if payload.status == "completed":
        task.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(task)

    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mentor_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    task = await get_active_task(task_id, db)

    if task.status not in ("pending", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail="Only pending or cancelled tasks can be deleted.",
        )

    now = datetime.now(timezone.utc)
    task.deleted_at = now
    task.updated_at = now
    task.updated_by = current_user.id

    await db.commit()

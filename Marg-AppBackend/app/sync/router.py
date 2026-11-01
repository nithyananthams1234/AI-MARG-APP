
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.sync_operation import SyncOperation
from app.schemas.sync import (
    SyncBatchRequest,
    SyncBatchResponse,
    SyncChangeResponse,
    SyncOperationResponse,
    SyncPullRequest,
    SyncPullResponse,
)
from app.services.sync import receive_sync_operation
from app.services.sync_apply import apply_operation
from app.services.sync_pull import fetch_sync_changes


router = APIRouter(
    prefix="/sync",
    tags=["Offline Synchronization"],
)


@router.post(
    "/push",
    response_model=SyncBatchResponse,
    status_code=status.HTTP_200_OK,
)
async def push_sync_operations(
    request: SyncBatchRequest,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    """Receive offline operations and apply them in order.

    Each operation is stored idempotently, then applied through the same
    business rules as the online API. Re-sending a batch is safe: already
    processed operations are returned with their recorded outcome.
    """
    accepted = 0
    already_received = 0
    records = []

    for operation in request.operations:
        try:
            record, was_already_received = await receive_sync_operation(
                db=db,
                operation=operation,
                user_id=current_user.id,
            )
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A sync operation conflicts with an existing idempotency key.",
            )

        if was_already_received:
            already_received += 1
        else:
            accepted += 1

        if record.status in ("pending", "syncing"):
            record = await apply_operation(db, current_user, record)

        # Snapshot now: a rollback in a later operation expires ORM objects.
        records.append(SyncOperationResponse.model_validate(record))

    return SyncBatchResponse(
        accepted=accepted,
        already_received=already_received,
        synced=sum(r.status == "synced" for r in records),
        conflicts=sum(r.status == "conflict" for r in records),
        failed=sum(r.status == "failed" for r in records),
        operations=records,
    )


@router.get(
    "/operations/{operation_id}",
    response_model=SyncOperationResponse,
)
async def get_sync_operation_status(
    operation_id: UUID,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(SyncOperation).where(
            SyncOperation.id == operation_id,
            SyncOperation.created_by == current_user.id,
            SyncOperation.deleted_at.is_(None),
        )
    )

    operation = result.scalar_one_or_none()

    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync operation not found.",
        )

    return operation


@router.post(
    "/pull",
    response_model=SyncPullResponse,
)
async def pull_sync_changes(
    request: SyncPullRequest,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        changes, next_cursor, has_more = await fetch_sync_changes(
            db=db,
            user_id=current_user.id,
            cursor_updated_at=request.cursor_updated_at,
            cursor_entity_type=request.cursor_entity_type,
            cursor_entity_id=request.cursor_entity_id,
            limit=request.limit,
        )

        return SyncPullResponse(
            changes=[
                SyncChangeResponse.model_validate(change)
                for change in changes
            ],
            next_cursor_updated_at=next_cursor["updated_at"],
            next_cursor_entity_type=next_cursor["entity_type"],
            next_cursor_entity_id=next_cursor["entity_id"],
            has_more=has_more,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

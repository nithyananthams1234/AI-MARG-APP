
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import BYPASS_SCOPE
from app.models.sync_operation import SyncOperation
from app.schemas.sync import SyncOperationCreate


async def receive_sync_operation(
    db: AsyncSession,
    operation: SyncOperationCreate,
    user_id,
) -> tuple[SyncOperation, bool]:
    """
    Store one offline operation.

    Returns:
        (operation_record, was_already_received)
    """

    result = await db.execute(
        select(SyncOperation).where(
            SyncOperation.idempotency_key == operation.idempotency_key
        ),
        # Keys are globally unique; a key used by another user must be
        # detected here (and rejected below), not hit the unique index.
        execution_options=BYPASS_SCOPE,
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        same_request = (
            existing.device_id == operation.device_id
            and existing.created_by == user_id
            and existing.entity_type == operation.entity_type
            and existing.entity_id == operation.entity_id
            and existing.operation_type == operation.operation_type
            and existing.client_version == operation.client_version
            and existing.payload == operation.payload
        )

        if not same_request:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used for a different operation.",
            )

        return existing, True

    record = SyncOperation(
        idempotency_key=operation.idempotency_key,
        device_id=operation.device_id,
        entity_type=operation.entity_type,
        entity_id=operation.entity_id,
        operation_type=operation.operation_type,
        payload=operation.payload,
        client_version=operation.client_version,
        status="pending",
        created_by=user_id,
        updated_by=user_id,
    )

    db.add(record)
    await db.flush()

    return record, False

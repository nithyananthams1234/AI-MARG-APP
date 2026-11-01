
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import BYPASS_SCOPE
from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.models.identity import User
from app.models.whatsapp_message import WhatsAppMessage
from app.schemas.whatsapp import (
    WhatsAppMessageCreate,
    WhatsAppMessageResponse,
)


router = APIRouter(
    prefix="/whatsapp",
    tags=["WhatsApp Integration"],
)


@router.post(
    "/messages",
    response_model=WhatsAppMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def queue_message(
    data: WhatsAppMessageCreate,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    if data.message_type == "text" and not data.content:
        raise HTTPException(
            status_code=422,
            detail="Text messages require content.",
        )

    if data.message_type == "template" and not data.template_name:
        raise HTTPException(
            status_code=422,
            detail="Template messages require a template name.",
        )

    existing = await db.execute(
        select(WhatsAppMessage).where(
            WhatsAppMessage.idempotency_key == data.idempotency_key
        ),
        # Keys are globally unique; check across all owners.
        execution_options=BYPASS_SCOPE,
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="This idempotency key has already been used.",
        )

    message = WhatsAppMessage(
        direction="outbound",
        recipient=data.recipient,
        message_type=data.message_type,
        content=data.content,
        template_name=data.template_name,
        idempotency_key=data.idempotency_key,
        status="queued",
        created_by=current_user.id,
    )

    db.add(message)
    await db.commit()
    await db.refresh(message)

    return message


@router.get(
    "/messages",
    response_model=list[WhatsAppMessageResponse],
)
async def list_messages(
    limit: int = 50,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(WhatsAppMessage)
        .order_by(WhatsAppMessage.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )

    return result.scalars().all()

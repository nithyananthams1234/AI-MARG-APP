
import uuid

from sqlalchemy import ForeignKey, Index, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class WhatsAppMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_messages"

    __table_args__ = (
        Index("ix_whatsapp_messages_status", "status"),
        Index("ix_whatsapp_messages_recipient", "recipient"),
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    direction: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    recipient: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    message_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    content: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    template_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    provider_message_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="queued"
    )

    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    provider_payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )

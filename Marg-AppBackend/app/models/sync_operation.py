
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, AuditMixin


class SyncOperation(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "sync_operations"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'syncing', 'synced', 'conflict', 'failed')",
            name="ck_sync_operations_status",
        ),
        CheckConstraint(
            "operation_type IN ('create', 'update', 'delete')",
            name="ck_sync_operations_operation_type",
        ),
        CheckConstraint(
            "client_version >= 1",
            name="ck_sync_operations_client_version",
        ),
        Index(
            "ix_sync_operations_entity",
            "entity_type",
            "entity_id",
        ),
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    device_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    operation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    client_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    server_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

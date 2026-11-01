
import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, AuditMixin


class Evidence(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "evidence"

    __table_args__ = (
        CheckConstraint(
            """
            (observation_id IS NOT NULL AND follow_up_id IS NULL)
            OR
            (observation_id IS NULL AND follow_up_id IS NOT NULL)
            """,
            name="ck_evidence_single_parent",
        ),
    )

    observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("observations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    follow_up_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("follow_ups.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
 
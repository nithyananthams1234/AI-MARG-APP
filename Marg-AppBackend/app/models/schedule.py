
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, AuditMixin


class Schedule(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "schedules"

    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected')",
            name="ck_schedules_status",
        ),
        CheckConstraint(
            "estimated_travel_minutes IS NULL OR estimated_travel_minutes >= 0",
            name="ck_schedules_travel_minutes",
        ),
        CheckConstraint(
            "estimated_distance_km IS NULL OR estimated_distance_km >= 0",
            name="ck_schedules_distance",
        ),
        CheckConstraint(
            "proposed_end_at > proposed_start_at",
            name="ck_schedules_valid_time_range",
        ),
    )

    school_visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school_visits.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    proposed_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    proposed_end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    estimated_travel_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    estimated_distance_km: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="proposed",
        nullable=False,
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

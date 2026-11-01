
import uuid

from sqlalchemy import (
    ForeignKey,
    String,
    Time,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, AuditMixin


class Timetable(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "timetables"

    __table_args__ = (
        UniqueConstraint(
            "classroom_id",
            "day_of_week",
            "period_number",
            name="uq_timetable_classroom_day_period",
        ),
    )

    classroom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classrooms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    day_of_week: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
    )

    period_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    start_time: Mapped[object] = mapped_column(
        Time,
        nullable=False,
    )

    end_time: Mapped[object] = mapped_column(
        Time,
        nullable=False,
    )

    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teachers.id", ondelete="SET NULL"),
        nullable=True,
    )


import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, AuditMixin


class MentorTask(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "mentor_tasks"

    __table_args__ = (
        CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100",
            name="ck_mentor_tasks_priority_score",
        ),
        CheckConstraint(
            "urgency >= 0 AND urgency <= 100",
            name="ck_mentor_tasks_urgency",
        ),
        CheckConstraint(
            "impact >= 0 AND impact <= 100",
            name="ck_mentor_tasks_impact",
        ),
        CheckConstraint(
            "risk >= 0 AND risk <= 100",
            name="ck_mentor_tasks_risk",
        ),
        CheckConstraint(
            "deadline_proximity >= 0 AND deadline_proximity <= 100",
            name="ck_mentor_tasks_deadline_proximity",
        ),
        CheckConstraint(
            "workload_dependency >= 0 AND workload_dependency <= 100",
            name="ck_mentor_tasks_workload_dependency",
        ),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="ck_mentor_tasks_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="ck_mentor_tasks_priority",
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Mentor who owns the task (backfilled from created_by).
    mentor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Planning metadata used by workload / time intelligence.
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True,
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        nullable=False,
        index=True,
    )

    urgency: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    impact: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    risk: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    deadline_proximity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    workload_dependency: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    priority_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        index=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


import uuid

from sqlalchemy import ForeignKey, String, Text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, AuditMixin


class ActionPlanStep(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "action_plan_steps"

    action_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    responsible_person: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    due_date: Mapped[Date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    completion_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

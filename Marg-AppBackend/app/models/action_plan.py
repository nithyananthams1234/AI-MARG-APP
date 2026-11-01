
import uuid

from sqlalchemy import ForeignKey, String, Text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, AuditMixin


class ActionPlan(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "action_plans"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recommendations.id", ondelete="RESTRICT"),
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

    start_date: Mapped[Date] = mapped_column(
        Date,
        nullable=False,
    )

    due_date: Mapped[Date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
    )

    mentor_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


import uuid

from sqlalchemy import ForeignKey, String, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, AuditMixin


class Classroom(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "classrooms"

    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "name",
            name="uq_classroom_school_name",
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    grade: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    section: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    academic_year: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    capacity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

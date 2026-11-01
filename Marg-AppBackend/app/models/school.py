
import uuid

from datetime import date

from sqlalchemy import (
    Integer,
    Boolean,
    Date,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    UUIDPrimaryKeyMixin,
    AuditMixin,
)


class School(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    district: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Administrative block and travel time from the mentor base (visit planning).
    block: Mapped[str | None] = mapped_column(String(100), nullable=True)
    travel_minutes_from_base: Mapped[int | None] = mapped_column(Integer, nullable=True)

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    teachers: Mapped[list["SchoolTeacher"]] = relationship(
        back_populates="school",
    )


class Teacher(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "teachers"

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    employee_code: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    schools: Mapped[list["SchoolTeacher"]] = relationship(
        back_populates="teacher",
    )


class SchoolTeacher(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "school_teachers"

    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "teacher_id",
            name="uq_school_teacher",
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    assigned_from: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    assigned_until: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    school: Mapped["School"] = relationship(
        back_populates="teachers",
    )

    teacher: Mapped["Teacher"] = relationship(
        back_populates="schools",
    )

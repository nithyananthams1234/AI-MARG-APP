"""Operational records used by the engine during independent development.

These tables hold **DEMO DATA** (``is_demo`` is always true for seeded rows). In production, MARG
remains the system of record and these records will be read through the MARG backend adapter once
the OpenAPI compatibility audit is complete. Identifiers are opaque strings (``*_ref``) because
MARG identifier formats are not yet known.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, enum_check
from app.schemas.common import ActionPlanStatus, FollowUpStatus, TaskStatus, VisitStatus


class Mentor(Base):
    __tablename__ = "mentors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_ref: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200))
    role_title: Mapped[str] = mapped_column(String(100))
    block: Mapped[str | None] = mapped_column(String(100))
    work_start: Mapped[time | None] = mapped_column(Time)
    work_end: Mapped[time | None] = mapped_column(Time)
    working_days: Mapped[list[int] | None] = mapped_column(JSON)  # ISO weekdays, 1 = Monday
    timezone: Mapped[str] = mapped_column(String(64))
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class School(Base):
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_ref: Mapped[str] = mapped_column(String(64), index=True)
    mentor_ref: Mapped[str] = mapped_column(ForeignKey("mentors.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    village: Mapped[str | None] = mapped_column(String(100))
    block: Mapped[str | None] = mapped_column(String(100))
    school_type: Mapped[str | None] = mapped_column(String(50))
    # Travel time from the mentor's base office. None = not recorded (never estimated).
    travel_minutes_from_base: Mapped[int | None] = mapped_column(Integer)
    # ISO weekdays when visits are possible. None = availability not recorded.
    available_days: Mapped[list[int] | None] = mapped_column(JSON)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    school_ref: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(100))
    grades: Mapped[str | None] = mapped_column(String(50))
    preferred_language: Mapped[str] = mapped_column(String(8), default="ta")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (enum_check("status", TaskStatus, "status_valid"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mentor_ref: Mapped[str] = mapped_column(ForeignKey("mentors.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(32))
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    # Verified priority inputs (0-100). None = not provided; never defaulted.
    urgency: Mapped[int | None] = mapped_column(Integer)
    impact: Mapped[int | None] = mapped_column(Integer)
    risk: Mapped[int | None] = mapped_column(Integer)
    depends_on: Mapped[list[str]] = mapped_column(JSON, default=list)
    school_ref: Mapped[str | None] = mapped_column(ForeignKey("schools.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class SchoolVisit(Base):
    __tablename__ = "school_visits"
    __table_args__ = (enum_check("status", VisitStatus, "status_valid"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mentor_ref: Mapped[str] = mapped_column(ForeignKey("mentors.id"), index=True)
    school_ref: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    scheduled_start: Mapped[datetime] = mapped_column(UTCDateTime)
    scheduled_end: Mapped[datetime] = mapped_column(UTCDateTime)
    purpose: Mapped[str | None] = mapped_column(String(300))
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class Observation(Base):
    """Mentor's operational observation note (context only; no classroom analysis here)."""

    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    visit_ref: Mapped[str | None] = mapped_column(ForeignKey("school_visits.id"))
    school_ref: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    teacher_ref: Mapped[str] = mapped_column(ForeignKey("teachers.id"), index=True)
    mentor_ref: Mapped[str] = mapped_column(ForeignKey("mentors.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    subject: Mapped[str | None] = mapped_column(String(100))
    mentor_note: Mapped[str] = mapped_column(Text)  # preserved verbatim
    support_areas: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class ActionPlan(Base):
    __tablename__ = "action_plans"
    __table_args__ = (enum_check("status", ActionPlanStatus, "status_valid"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mentor_ref: Mapped[str] = mapped_column(ForeignKey("mentors.id"), index=True)
    school_ref: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    teacher_ref: Mapped[str] = mapped_column(ForeignKey("teachers.id"), index=True)
    observation_ref: Mapped[str | None] = mapped_column(ForeignKey("observations.id"))
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(32))
    start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class FollowUp(Base):
    __tablename__ = "followups"
    __table_args__ = (enum_check("status", FollowUpStatus, "status_valid"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mentor_ref: Mapped[str] = mapped_column(ForeignKey("mentors.id"), index=True)
    action_plan_ref: Mapped[str] = mapped_column(ForeignKey("action_plans.id"), index=True)
    teacher_ref: Mapped[str] = mapped_column(ForeignKey("teachers.id"), index=True)
    school_ref: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Three distinct kinds of progress information - never merged:
    teacher_reported_progress: Mapped[str | None] = mapped_column(Text)
    teacher_reported_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    evidence_description: Mapped[str | None] = mapped_column(Text)
    evidence_submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    mentor_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    mentor_verified_by: Mapped[str | None] = mapped_column(String(64))
    last_reminder_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class ScheduleItem(Base):
    """Meetings, trainings and other calendar commitments (school visits are stored separately)."""

    __tablename__ = "schedule_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mentor_ref: Mapped[str] = mapped_column(ForeignKey("mentors.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(300))
    start_at: Mapped[datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime)
    location: Mapped[str | None] = mapped_column(String(200))
    school_ref: Mapped[str | None] = mapped_column(ForeignKey("schools.id"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkloadActivity(Base):
    """Recurring or assigned administrative activities that consume mentor time."""

    __tablename__ = "workload_activities"
    __table_args__ = (enum_check("status", TaskStatus, "status_valid"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mentor_ref: Mapped[str] = mapped_column(ForeignKey("mentors.id"), index=True)
    activity_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(300))
    activity_date: Mapped[date] = mapped_column(Date)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    assigned_by: Mapped[str | None] = mapped_column(String(100))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


def row_to_dict(row: Any) -> dict[str, Any]:
    return {c.key: getattr(row, c.key) for c in row.__table__.columns}

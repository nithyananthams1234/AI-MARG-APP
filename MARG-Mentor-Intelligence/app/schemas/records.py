"""Engine-side views of operational records (provisional until the MARG OpenAPI audit)."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import (
    ActionPlanStatus,
    DataSource,
    FollowUpStatus,
    TaskStatus,
    VisitStatus,
)


class Record(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MentorRecord(Record):
    id: str
    tenant_ref: str
    name: str
    role_title: str
    block: str | None
    work_start: time | None
    work_end: time | None
    working_days: list[int] | None
    timezone: str
    preferred_language: str


class SchoolRecord(Record):
    id: str
    name: str
    village: str | None
    block: str | None
    school_type: str | None
    travel_minutes_from_base: int | None
    available_days: list[int] | None


class TeacherRecord(Record):
    id: str
    school_ref: str
    name: str
    subject: str | None
    grades: str | None
    preferred_language: str


class TaskRecord(Record):
    id: str
    title: str
    description: str | None
    category: str
    status: TaskStatus
    due_at: datetime | None
    estimated_minutes: int | None
    urgency: int | None = Field(default=None, ge=0, le=100)
    impact: int | None = Field(default=None, ge=0, le=100)
    risk: int | None = Field(default=None, ge=0, le=100)
    depends_on: list[str] = Field(default_factory=list)
    school_ref: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class VisitRecord(Record):
    id: str
    school_ref: str
    status: VisitStatus
    scheduled_start: datetime
    scheduled_end: datetime
    purpose: str | None
    completed_at: datetime | None


class ObservationRecord(Record):
    id: str
    visit_ref: str | None
    school_ref: str
    teacher_ref: str
    observed_at: datetime
    subject: str | None
    mentor_note: str
    support_areas: list[str]


class ActionPlanRecord(Record):
    id: str
    school_ref: str
    teacher_ref: str
    observation_ref: str | None
    title: str
    status: ActionPlanStatus
    start_date: date | None
    due_date: date | None


class FollowUpRecord(Record):
    id: str
    action_plan_ref: str
    teacher_ref: str
    school_ref: str
    status: FollowUpStatus
    due_at: datetime | None
    teacher_reported_progress: str | None
    teacher_reported_at: datetime | None
    evidence_description: str | None
    evidence_submitted_at: datetime | None
    mentor_verified_at: datetime | None
    mentor_verified_by: str | None
    last_reminder_at: datetime | None


class ScheduleItemRecord(Record):
    id: str
    kind: str
    title: str
    start_at: datetime
    end_at: datetime
    location: str | None
    school_ref: str | None


class WorkloadActivityRecord(Record):
    id: str
    activity_type: str
    description: str
    activity_date: date
    estimated_minutes: int | None
    status: TaskStatus
    assigned_by: str | None


class MentorSnapshot(BaseModel):
    """Everything an agent may read about one mentor. Built by the adapter, scoped to that mentor."""

    data_source: DataSource
    is_demo: bool
    mentor: MentorRecord
    schools: list[SchoolRecord]
    teachers: list[TeacherRecord]
    tasks: list[TaskRecord]
    visits: list[VisitRecord]
    observations: list[ObservationRecord]
    action_plans: list[ActionPlanRecord]
    followups: list[FollowUpRecord]
    schedule_items: list[ScheduleItemRecord]
    workload_activities: list[WorkloadActivityRecord]

    def school(self, ref: str | None) -> SchoolRecord | None:
        return next((s for s in self.schools if s.id == ref), None)

    def teacher(self, ref: str | None) -> TeacherRecord | None:
        return next((t for t in self.teachers if t.id == ref), None)

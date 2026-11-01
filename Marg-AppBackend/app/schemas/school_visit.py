
from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


VisitStatus = Literal[
    "planned",
    "in_progress",
    "completed",
    "cancelled",
]


class SchoolVisitCreate(BaseModel):
    school_id: UUID
    scheduled_at: datetime
    notes: str | None = None


class SchoolVisitUpdate(BaseModel):
    scheduled_at: datetime | None = None
    notes: str | None = None


class SchoolVisitStatusUpdate(BaseModel):
    status: VisitStatus


class SchoolVisitResponse(BaseModel):
    mentor_id: UUID | None = None
    id: UUID
    school_id: UUID
    scheduled_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    status: VisitStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)

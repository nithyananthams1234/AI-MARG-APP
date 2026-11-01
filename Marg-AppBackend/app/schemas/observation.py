
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ObservationCreate(BaseModel):
    school_visit_id: UUID
    teacher_id: UUID
    classroom_id: UUID
    subject: str = Field(min_length=1, max_length=100)
    topic: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class ObservationUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=100)
    topic: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class ObservationStatusUpdate(BaseModel):
    status: str


class ObservationResponse(BaseModel):
    id: UUID
    school_visit_id: UUID
    teacher_id: UUID
    classroom_id: UUID
    subject: str
    topic: str | None
    notes: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    version: int = 1

    model_config = ConfigDict(from_attributes=True)

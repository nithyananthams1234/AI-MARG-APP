
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClassroomCreate(BaseModel):
    school_id: UUID
    name: str = Field(min_length=1, max_length=100)
    grade: str = Field(min_length=1, max_length=30)
    section: str | None = Field(default=None, max_length=20)
    academic_year: str = Field(min_length=1, max_length=20)
    capacity: int | None = Field(default=None, ge=1)


class ClassroomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    grade: str | None = Field(default=None, min_length=1, max_length=30)
    section: str | None = Field(default=None, max_length=20)
    academic_year: str | None = Field(default=None, min_length=1, max_length=20)
    capacity: int | None = Field(default=None, ge=1)


class ClassroomResponse(BaseModel):
    id: UUID
    school_id: UUID
    name: str
    grade: str
    section: str | None
    academic_year: str
    capacity: int | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)

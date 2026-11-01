
from datetime import datetime, date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TeacherCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    employee_code: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)


class TeacherUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    employee_code: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class TeacherResponse(BaseModel):
    id: UUID
    full_name: str
    employee_code: str | None
    email: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)


class TeacherSchoolAssign(BaseModel):
    school_id: UUID
    assigned_from: date | None = None
    assigned_until: date | None = None


class TeacherSchoolResponse(BaseModel):
    id: UUID
    teacher_id: UUID
    school_id: UUID
    assigned_from: date | None
    assigned_until: date | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

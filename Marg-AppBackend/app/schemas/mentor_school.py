from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MentorSchoolCreate(BaseModel):
    user_id: UUID
    school_id: UUID
    assigned_from: date | None = None
    assigned_until: date | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.assigned_from
            and self.assigned_until
            and self.assigned_until < self.assigned_from
        ):
            raise ValueError("Assignment end date cannot precede start date")
        return self


class MentorSchoolUpdate(BaseModel):
    assigned_from: date | None = None
    assigned_until: date | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.assigned_from
            and self.assigned_until
            and self.assigned_until < self.assigned_from
        ):
            raise ValueError("Assignment end date cannot precede start date")
        return self


class MentorSchoolResponse(BaseModel):
    id: UUID
    user_id: UUID
    school_id: UUID
    assigned_from: date | None
    assigned_until: date | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
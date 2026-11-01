
from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TimetableCreate(BaseModel):
    classroom_id: UUID
    day_of_week: str = Field(
        min_length=3,
        max_length=15,
    )
    period_number: int = Field(ge=1)
    subject: str = Field(
        min_length=1,
        max_length=100,
    )
    start_time: time
    end_time: time
    teacher_id: UUID | None = None

    @model_validator(mode="after")
    def validate_timetable(self):
        valid_days = {
            "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday", "Sunday",
        }

        if self.day_of_week not in valid_days:
            raise ValueError("Invalid day of week")

        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")

        return self


class TimetableUpdate(BaseModel):
    day_of_week: str | None = Field(
        default=None,
        min_length=3,
        max_length=15,
    )
    period_number: int | None = Field(default=None, ge=1)
    subject: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    start_time: time | None = None
    end_time: time | None = None
    teacher_id: UUID | None = None

    @model_validator(mode="after")
    def validate_timetable(self):
        valid_days = {
            "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday", "Sunday",
        }

        if self.day_of_week is not None and self.day_of_week not in valid_days:
            raise ValueError("Invalid day of week")

        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("End time must be after start time")

        return self


class TimetableResponse(BaseModel):
    id: UUID
    classroom_id: UUID
    day_of_week: str
    period_number: int
    subject: str
    start_time: time
    end_time: time
    teacher_id: UUID | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)

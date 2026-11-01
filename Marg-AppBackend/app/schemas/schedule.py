
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ScheduleStatus = Literal["proposed", "accepted", "rejected"]


class ScheduleCreate(BaseModel):
    school_visit_id: uuid.UUID
    proposed_start_at: datetime
    proposed_end_at: datetime
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.proposed_start_at.tzinfo is None:
            raise ValueError("proposed_start_at must include a timezone.")

        if self.proposed_end_at.tzinfo is None:
            raise ValueError("proposed_end_at must include a timezone.")

        if self.proposed_end_at <= self.proposed_start_at:
            raise ValueError("proposed_end_at must be later than proposed_start_at.")

        return self


class ScheduleDecision(BaseModel):
    status: Literal["accepted", "rejected"]


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    school_visit_id: uuid.UUID
    school_id: uuid.UUID
    proposed_start_at: datetime
    proposed_end_at: datetime
    estimated_travel_minutes: int | None
    estimated_distance_km: Decimal | None
    status: ScheduleStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime

    version: int = 1

    model_config = ConfigDict(from_attributes=True)

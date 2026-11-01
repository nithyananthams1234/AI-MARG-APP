
from datetime import date, datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ActionPlanStepCreate(BaseModel):
    action_plan_id: UUID
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    responsible_person: str = Field(min_length=2, max_length=150)
    due_date: date


class ActionPlanStepUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=3)
    responsible_person: str | None = Field(default=None, min_length=2, max_length=150)
    due_date: date | None = None


class ActionPlanStepStatusUpdate(BaseModel):
    status: Literal["in_progress", "completed", "cancelled"]
    completion_notes: str | None = None


class ActionPlanStepResponse(BaseModel):
    id: UUID
    action_plan_id: UUID
    title: str
    description: str
    responsible_person: str
    due_date: date
    status: str
    completion_notes: str | None
    created_at: datetime
    updated_at: datetime

    version: int = 1

    model_config = ConfigDict(from_attributes=True)

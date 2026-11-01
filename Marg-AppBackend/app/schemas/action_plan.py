
from datetime import date, datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ActionPlanStatus = Literal[
    "draft",
    "pending_approval",
    "approved",
    "in_progress",
    "completed",
    "overdue",
    "cancelled",
]


class ActionPlanCreate(BaseModel):
    recommendation_id: UUID
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    responsible_person: str = Field(min_length=2, max_length=150)
    start_date: date
    due_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.due_date < self.start_date:
            raise ValueError("Due date cannot be before start date")
        return self


class ActionPlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=3)
    responsible_person: str | None = Field(default=None, min_length=2, max_length=150)
    start_date: date | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date is not None and self.due_date is not None:
            if self.due_date < self.start_date:
                raise ValueError("Due date cannot be before start date")
        return self


class ActionPlanStatusUpdate(BaseModel):
    status: Literal[
        "pending_approval",
        "approved",
        "in_progress",
        "completed",
        "overdue",
        "cancelled",
    ]
    mentor_comment: str | None = None


class ActionPlanResponse(BaseModel):
    id: UUID
    recommendation_id: UUID
    title: str
    description: str
    responsible_person: str
    start_date: date
    due_date: date
    status: str
    mentor_comment: str | None
    created_at: datetime
    updated_at: datetime

    version: int = 1

    model_config = ConfigDict(from_attributes=True)

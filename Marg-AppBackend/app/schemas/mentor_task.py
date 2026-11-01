
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


TaskStatus = Literal[
    "pending",
    "in_progress",
    "completed",
    "cancelled",
]

TaskPriority = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


class MentorTaskCreate(BaseModel):
    school_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None

    urgency: int = Field(default=0, ge=0, le=100)
    impact: int = Field(default=0, ge=0, le=100)
    risk: int = Field(default=0, ge=0, le=100)
    deadline_proximity: int = Field(default=0, ge=0, le=100)
    workload_dependency: int = Field(default=0, ge=0, le=100)
    category: str | None = Field(default=None, max_length=50)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)


class MentorTaskUpdate(BaseModel):
    school_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None

    urgency: int | None = Field(default=None, ge=0, le=100)
    impact: int | None = Field(default=None, ge=0, le=100)
    risk: int | None = Field(default=None, ge=0, le=100)
    deadline_proximity: int | None = Field(default=None, ge=0, le=100)
    workload_dependency: int | None = Field(default=None, ge=0, le=100)
    category: str | None = Field(default=None, max_length=50)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)


class MentorTaskStatusUpdate(BaseModel):
    status: TaskStatus


class MentorTaskResponse(BaseModel):
    mentor_id: uuid.UUID | None = None
    id: uuid.UUID
    school_id: uuid.UUID | None
    title: str
    description: str | None
    due_at: datetime | None

    status: TaskStatus
    priority: TaskPriority

    urgency: int
    impact: int
    risk: int
    deadline_proximity: int
    workload_dependency: int
    category: str | None = None
    estimated_minutes: int | None = None

    priority_score: int
    completed_at: datetime | None

    created_at: datetime
    updated_at: datetime

    version: int = 1

    model_config = ConfigDict(from_attributes=True)

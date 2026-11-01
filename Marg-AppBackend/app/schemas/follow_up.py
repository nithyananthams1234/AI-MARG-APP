
from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FollowUpCreate(BaseModel):
    action_plan_step_id: UUID
    teacher_id: UUID
    description: str = Field(min_length=3)


class TeacherFollowUpResponse(BaseModel):
    teacher_response: str = Field(min_length=3)


class FollowUpEvidenceSubmission(BaseModel):
    teacher_response: str = Field(min_length=3)


class FollowUpMentorDecision(BaseModel):
    status: Literal["mentor_verified", "needs_revision"]
    mentor_notes: str | None = None


class FollowUpStatusUpdate(BaseModel):
    status: Literal["closed"]


class FollowUpResponse(BaseModel):
    id: UUID
    action_plan_step_id: UUID
    teacher_id: UUID
    description: str
    status: str
    teacher_response: str | None
    mentor_notes: str | None
    responded_at: datetime | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime

    version: int = 1

    model_config = ConfigDict(from_attributes=True)

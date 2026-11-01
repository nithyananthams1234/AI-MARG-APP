
from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FindingStatus = Literal[
    "ai_suggested",
    "mentor_approved",
    "rejected",
]


class ObservationFindingCreate(BaseModel):
    observation_id: UUID
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=1)
    category: str | None = Field(default=None, max_length=100)


class ObservationFindingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=100)
    mentor_comment: str | None = None


class ObservationFindingStatusUpdate(BaseModel):
    status: Literal["mentor_approved", "rejected"]
    mentor_comment: str | None = None


class ObservationFindingResponse(BaseModel):
    id: UUID
    observation_id: UUID
    title: str
    description: str
    category: str | None
    status: FindingStatus
    mentor_comment: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)

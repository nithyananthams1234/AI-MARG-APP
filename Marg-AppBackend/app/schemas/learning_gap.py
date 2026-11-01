
from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


GapSeverity = Literal["low", "medium", "high", "critical"]
GapStatus = Literal["identified", "addressed", "resolved"]


class LearningGapCreate(BaseModel):
    observation_id: UUID
    observation_finding_id: UUID | None = None
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    subject: str = Field(min_length=2, max_length=100)
    grade: str | None = Field(default=None, max_length=30)
    severity: GapSeverity = "medium"


class LearningGapUpdate(BaseModel):
    observation_finding_id: UUID | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=3)
    subject: str | None = Field(default=None, min_length=2, max_length=100)
    grade: str | None = Field(default=None, max_length=30)
    severity: GapSeverity | None = None


class LearningGapStatusUpdate(BaseModel):
    status: Literal["addressed", "resolved"]


class LearningGapResponse(BaseModel):
    id: UUID
    observation_id: UUID
    observation_finding_id: UUID | None
    title: str
    description: str
    subject: str
    grade: str | None
    severity: str
    status: str
    created_at: datetime
    updated_at: datetime

    version: int = 1

    model_config = ConfigDict(from_attributes=True)

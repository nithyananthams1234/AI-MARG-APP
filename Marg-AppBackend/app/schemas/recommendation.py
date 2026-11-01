
from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RecommendationStatus = Literal[
    "ai_suggested",
    "mentor_approved",
    "rejected",
]


class RecommendationCreate(BaseModel):
    learning_gap_id: UUID
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    category: str = Field(min_length=2, max_length=100)


class RecommendationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=3)
    rationale: str | None = Field(default=None, min_length=3)
    category: str | None = Field(default=None, min_length=2, max_length=100)


class RecommendationDecision(BaseModel):
    status: Literal["mentor_approved", "rejected"]
    mentor_comment: str | None = None


class RecommendationResponse(BaseModel):
    id: UUID
    learning_gap_id: UUID
    title: str
    description: str
    rationale: str
    category: str
    status: str
    mentor_comment: str | None
    created_at: datetime
    updated_at: datetime

    version: int = 1

    model_config = ConfigDict(from_attributes=True)

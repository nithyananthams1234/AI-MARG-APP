"""Canonical status contracts and shared schema types.

The status values below are fixed by the project brief. Do not rename or extend them silently.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

SCHEMA_VERSION = "v1"


class VisitStatus(StrEnum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class TaskStatus(StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class FollowUpStatus(StrEnum):
    pending = "pending"
    teacher_responded = "teacher_responded"
    evidence_submitted = "evidence_submitted"
    mentor_verified = "mentor_verified"
    needs_revision = "needs_revision"
    closed = "closed"


class ActionPlanStatus(StrEnum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    in_progress = "in_progress"
    completed = "completed"
    overdue = "overdue"
    cancelled = "cancelled"


class Priority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AIJobStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ProposalStatus(StrEnum):
    """Engine-internal proposal lifecycle (approved by the owner, separate from business statuses)."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    executed = "executed"
    execution_failed = "execution_failed"


class AutonomyLevel(StrEnum):
    automatic = "L1_automatic"
    proposed = "L2_proposed"
    explicit = "L3_explicit_approval"


class DataSource(StrEnum):
    demo = "demo"  # DEMO DATA hosted by the engine (development only)
    marg = "marg"  # real MARG backend (not yet integrated)


class AIStatus(StrEnum):
    generated = "generated"  # Claude produced validated insights
    not_needed = "not_needed"  # deterministic result was sufficient
    disabled = "disabled"  # AI_ENABLED=false
    unavailable = "unavailable"  # provider error (timeouts, rate limits, outages)
    invalid_output = "invalid_output"  # Claude output failed validation and was discarded
    refused = "refused"  # Claude declined the request
    budget_exceeded = "budget_exceeded"  # daily token budget reached


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware (ISO 8601 with offset)")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(_require_aware)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MissingData(BaseModel):
    """An input that was required but not available in the records. Never filled with assumptions."""

    entity_type: str
    entity_ref: str | None = None
    field: str
    impact: str


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Consistent envelope for every /api/v1 response."""

    schema_version: str = SCHEMA_VERSION
    success: bool = True
    data: T | None = None
    error: dict[str, Any] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

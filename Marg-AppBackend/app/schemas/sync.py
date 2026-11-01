
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


SyncEntityType = Literal[
    "school",
    "teacher",
    "school_teacher",
    "classroom",
    "timetable",
    "school_visit",
    "observation",
    "observation_finding",
    "learning_gap",
    "recommendation",
    "action_plan",
    "action_plan_step",
    "follow_up",
    "mentor_task",
    "schedule",
]

SyncOperationType = Literal["create", "update", "delete"]

SyncStatus = Literal[
    "pending",
    "syncing",
    "synced",
    "conflict",
    "failed",
]


class SyncOperationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=255)
    device_id: str = Field(min_length=1, max_length=255)
    entity_type: SyncEntityType
    entity_id: UUID
    operation_type: SyncOperationType
    payload: dict[str, Any]
    client_version: int = Field(ge=1)


class SyncBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: list[SyncOperationCreate] = Field(
        min_length=1,
        max_length=100,
    )


class SyncOperationResponse(BaseModel):
    id: UUID
    idempotency_key: str
    device_id: str
    entity_type: str
    entity_id: UUID
    operation_type: str
    client_version: int
    server_version: int | None
    status: SyncStatus
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class SyncBatchResponse(BaseModel):
    accepted: int
    already_received: int
    # Outcome counts across the batch (operations are applied in order).
    synced: int = 0
    conflicts: int = 0
    failed: int = 0
    operations: list[SyncOperationResponse]


class SyncPullRequest(BaseModel):
    cursor_updated_at: datetime | None = None
    cursor_entity_type: str | None = None
    cursor_entity_id: UUID | None = None
    limit: int = Field(default=100, ge=1, le=500)


class SyncChangeResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    operation_type: Literal["create", "update", "delete"]
    payload: dict[str, Any]
    version: int
    updated_at: datetime


class SyncPullResponse(BaseModel):
    changes: list[SyncChangeResponse]
    next_cursor_updated_at: datetime | None
    next_cursor_entity_type: str | None
    next_cursor_entity_id: UUID | None
    has_more: bool

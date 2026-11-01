"""Engine-owned records: executions, proposals, approvals, plans, drafts, LLM usage, audit."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, enum_check
from app.schemas.common import AIJobStatus, ProposalStatus


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (enum_check("status", AIJobStatus, "status_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    agent_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_version: Mapped[str] = mapped_column(String(32))
    mentor_ref: Mapped[str] = mapped_column(String(64), index=True)
    trigger: Mapped[str] = mapped_column(String(32))  # api | event
    trigger_ref: Mapped[str | None] = mapped_column(String(200))
    actor_ref: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    input_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ai_status: Mapped[str | None] = mapped_column(String(32))
    data_source: Mapped[str | None] = mapped_column(String(16))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class ExecutionStep(Base):
    __tablename__ = "execution_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    step: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (enum_check("status", ProposalStatus, "status_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("executions.id"), index=True)
    mentor_ref: Mapped[str] = mapped_column(String(64), index=True)
    agent_id: Mapped[str] = mapped_column(String(64))
    action_type: Mapped[str] = mapped_column(String(64))
    autonomy_level: Mapped[str] = mapped_column(String(32))
    target_type: Mapped[str] = mapped_column(String(64))
    target_ref: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    requires_external_execution: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    execution_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    executed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Approval(Base):
    """Decision record. Bound to the exact proposal payload through ``payload_hash``."""

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposals.id"), index=True)
    decision: Mapped[str] = mapped_column(String(16))  # approved | rejected
    approver_ref: Mapped[str] = mapped_column(String(64))
    approver_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    payload_hash: Mapped[str] = mapped_column(String(64))
    original_proposal: Mapped[dict[str, Any]] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(UTCDateTime)
    result_status: Mapped[str | None] = mapped_column(String(32))


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    mentor_ref: Mapped[str] = mapped_column(String(64), index=True)
    plan_type: Mapped[str] = mapped_column(String(32))  # daily_plan | weekly_plan | daily_report | ...
    period_start: Mapped[datetime] = mapped_column(UTCDateTime)
    period_end: Mapped[datetime] = mapped_column(UTCDateTime)
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class MessageDraft(Base):
    """AI- or template-generated teacher message. Never sent by the engine."""

    __tablename__ = "message_drafts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    mentor_ref: Mapped[str] = mapped_column(String(64), index=True)
    teacher_ref: Mapped[str] = mapped_column(String(64))
    followup_ref: Mapped[str | None] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8))
    body: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(16))  # ai | template
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    mentor_ref: Mapped[str | None] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    model_requested: Mapped[str] = mapped_column(String(100))
    model_served: Mapped[str | None] = mapped_column(String(100))
    prompt_id: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(16))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    stop_reason: Mapped[str | None] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(32))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    provider_request_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class AuditLog(Base):
    """Append-only security and decision trail."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    actor_ref: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(64))
    target_ref: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(32))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)

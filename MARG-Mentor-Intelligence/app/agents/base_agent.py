"""Shared agent framework.

Every agent follows the same template:
1. ``analyse``  - deterministic Python over the mentor snapshot (always runs)
2. ``needs_llm`` - cost gate: Claude is called only when it adds value
3. Claude call through the vendor-neutral provider, output validated against a Pydantic schema
4. ``validate_insights`` - agent-specific checks (e.g. referenced IDs must exist)
5. ``finalise`` - optional post-processing (e.g. render a message draft)

Agents never write to storage or call external systems. They return proposals, which the
orchestrator records and the approval engine executes only after human approval.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, ClassVar, Generic, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.config import Settings
from app.providers.base import (
    ComplexityHint,
    LLMBudgetExceededError,
    LLMDisabledError,
    LLMOutputInvalidError,
    LLMPermanentError,
    LLMProvider,
    LLMRefusalError,
    LLMRequest,
    LLMTransientError,
    LLMTruncatedError,
)
from app.schemas.common import AIStatus, MissingData, StrictModel
from app.schemas.records import MentorSnapshot
from app.utils.datetime_utils import local_date

logger = logging.getLogger(__name__)

AI_LABEL = "AI-generated suggestions based on the records below. Not records, not decisions."


class AgentInput(StrictModel):
    mentor_ref: str = Field(min_length=1, max_length=64)
    use_ai: bool = Field(default=True, description="Allow a Claude call for explanations and suggestions")


class ProposedAction(BaseModel):
    action_type: str
    target_type: str
    target_ref: str | None
    payload: dict[str, Any]
    rationale: str


class DraftSpec(BaseModel):
    draft_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    teacher_ref: str
    followup_ref: str | None
    purpose: str
    language: str
    body: str
    generated_by: str  # ai | template


class PlanSpec(BaseModel):
    plan_type: str
    period_start: datetime
    period_end: datetime


@dataclass
class Analysis:
    facts: dict[str, Any]
    known_refs: set[str] = field(default_factory=set)
    missing_data: list[MissingData] = field(default_factory=list)
    proposals: list[ProposedAction] = field(default_factory=list)
    drafts: list[DraftSpec] = field(default_factory=list)
    plan: PlanSpec | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # private working data (not returned)


@dataclass
class AgentContext:
    snapshot: MentorSnapshot
    now: datetime
    settings: Settings
    provider: LLMProvider
    execution_id: str | None = None

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.snapshot.mentor.timezone)

    @property
    def today(self) -> date:
        return local_date(self.now, self.tz)


class AgentOutcome(BaseModel):
    agent_id: str
    agent_version: str
    mentor_ref: str
    generated_at: datetime
    data_source: str
    is_demo_data: bool
    facts: dict[str, Any]
    ai_status: AIStatus
    ai_insights: dict[str, Any] | None
    ai_meta: dict[str, Any] = Field(default_factory=dict)
    missing_data: list[MissingData]
    proposals: list[ProposedAction]
    drafts: list[DraftSpec]
    plan: PlanSpec | None = None


class InsightValidationError(ValueError):
    pass


InputT = TypeVar("InputT", bound=AgentInput)


class BaseAgent(ABC, Generic[InputT]):
    agent_id: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    description: ClassVar[str]
    input_model: ClassVar[type[AgentInput]]
    prompt_id: ClassVar[str | None] = None
    insight_model: ClassVar[type[BaseModel] | None] = None
    complexity: ClassVar[ComplexityHint] = ComplexityHint.standard
    allowed_actions: ClassVar[frozenset[str]] = frozenset()

    # ------------------------------------------------------------------ hooks
    @abstractmethod
    def analyse(self, ctx: AgentContext, inp: InputT) -> Analysis: ...

    def needs_llm(self, ctx: AgentContext, inp: InputT, analysis: Analysis) -> bool:
        return self.insight_model is not None and self.prompt_id is not None

    def llm_request(self, ctx: AgentContext, inp: InputT, analysis: Analysis) -> LLMRequest:
        raise NotImplementedError

    def validate_insights(self, insights: BaseModel, analysis: Analysis) -> BaseModel:
        return insights

    def finalise(
        self, ctx: AgentContext, inp: InputT, analysis: Analysis, insights: BaseModel | None
    ) -> Analysis:
        return analysis

    # ------------------------------------------------------------------ template
    async def run(self, ctx: AgentContext, inp: InputT) -> AgentOutcome:
        analysis = self.analyse(ctx, inp)
        ai_status, insights, meta = AIStatus.not_needed, None, {}
        if inp.use_ai and self.needs_llm(ctx, inp, analysis):
            ai_status, insights, meta = await self._reason(ctx, inp, analysis)
        analysis = self.finalise(ctx, inp, analysis, insights)
        return AgentOutcome(
            agent_id=self.agent_id,
            agent_version=self.version,
            mentor_ref=ctx.snapshot.mentor.id,
            generated_at=ctx.now,
            data_source=ctx.snapshot.data_source.value,
            is_demo_data=ctx.snapshot.is_demo,
            facts=analysis.facts,
            ai_status=ai_status,
            ai_insights={"label": AI_LABEL, "content": insights.model_dump(mode="json")}
            if insights
            else None,
            ai_meta=meta,
            missing_data=analysis.missing_data,
            proposals=analysis.proposals,
            drafts=analysis.drafts,
            plan=analysis.plan,
        )

    async def _reason(
        self, ctx: AgentContext, inp: InputT, analysis: Analysis
    ) -> tuple[AIStatus, BaseModel | None, dict[str, Any]]:
        assert self.insight_model is not None
        request = self.llm_request(ctx, inp, analysis)
        request.mentor_ref = ctx.snapshot.mentor.id
        request.execution_id = ctx.execution_id
        request.complexity = self.complexity
        last_error = ""
        for attempt in (1, 2):  # one repair attempt for invalid output only
            try:
                result = await ctx.provider.generate_structured(request, self.insight_model)
                insights = self.validate_insights(result.output, analysis)
                return (
                    AIStatus.generated,
                    insights,
                    {
                        "model": result.model_served or result.model_requested,
                        "prompt": f"{request.prompt_id}/{result.prompt_version}",
                        "input_tokens": result.usage.input_tokens,
                        "output_tokens": result.usage.output_tokens,
                        "cache_read_tokens": result.usage.cache_read_tokens,
                        "attempts": attempt,
                    },
                )
            except (LLMOutputInvalidError, LLMTruncatedError, InsightValidationError) as exc:
                last_error = type(exc).__name__
                logger.warning("llm_output_rejected", extra={"agent": self.agent_id, "attempt": attempt})
                continue
            except LLMDisabledError:
                return AIStatus.disabled, None, {}
            except LLMBudgetExceededError:
                return AIStatus.budget_exceeded, None, {}
            except LLMRefusalError as exc:
                return AIStatus.refused, None, {"category": exc.category}
            except (LLMTransientError, LLMPermanentError) as exc:
                logger.warning("llm_unavailable", extra={"agent": self.agent_id, "error": exc.code})
                return AIStatus.unavailable, None, {"error": exc.code}
        return (
            AIStatus.invalid_output,
            None,
            {"error": last_error, "note": "AI output discarded after validation"},
        )


def keep_known(items: list[Any], attr: str, known: set[str]) -> list[Any]:
    """Drop model output items that reference IDs not present in the records."""
    return [i for i in items if getattr(i, attr) in known]

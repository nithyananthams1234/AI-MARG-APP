"""Token usage recording, cost calculation (from configured prices only) and daily budgets."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.config import Settings
from app.db.session import Database
from app.models.engine import LLMUsage
from app.providers.base import LLMBudgetExceededError, LLMUsageInfo


def compute_cost(model: str, usage: LLMUsageInfo, pricing: dict[str, tuple[float, float]]) -> Decimal | None:
    """Cost in USD from configured per-million-token prices. ``None`` if pricing is not configured.

    Cache reads/writes are approximated at the input rate (reported separately in token counts);
    configure exact cache pricing before relying on these figures for billing.
    """
    if model not in pricing:
        return None
    input_price, output_price = pricing[model]
    input_total = usage.input_tokens + usage.cache_read_tokens + usage.cache_creation_tokens
    cost = (
        Decimal(input_total) * Decimal(str(input_price))
        + Decimal(usage.output_tokens) * Decimal(str(output_price))
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))


class UsageTracker:
    def __init__(self, db: Database, settings: Settings):
        self._db = db
        self._settings = settings

    async def tokens_used_today(self, mentor_ref: str | None = None) -> int:
        since = datetime.now(UTC) - timedelta(days=1)
        stmt = select(func.coalesce(func.sum(LLMUsage.input_tokens + LLMUsage.output_tokens), 0)).where(
            LLMUsage.created_at >= since
        )
        if mentor_ref is not None:
            stmt = stmt.where(LLMUsage.mentor_ref == mentor_ref)
        async with self._db.session() as session:
            return int((await session.execute(stmt)).scalar_one())

    async def check_budget(self, mentor_ref: str | None) -> None:
        if self._settings.llm_daily_token_budget_global == 0:
            raise LLMBudgetExceededError("Global LLM budget is zero")
        if await self.tokens_used_today() >= self._settings.llm_daily_token_budget_global:
            raise LLMBudgetExceededError("Global daily LLM token budget reached")
        if mentor_ref is not None:
            budget = self._settings.llm_daily_token_budget_per_mentor
            if budget == 0 or await self.tokens_used_today(mentor_ref) >= budget:
                raise LLMBudgetExceededError("Mentor daily LLM token budget reached")

    async def record(
        self,
        *,
        provider: str,
        model_requested: str,
        model_served: str | None,
        prompt_id: str,
        prompt_version: str,
        usage: LLMUsageInfo,
        stop_reason: str | None,
        outcome: str,
        latency_ms: int,
        provider_request_id: str | None,
        mentor_ref: str | None,
        execution_id: str | None,
    ) -> None:
        cost = compute_cost(model_served or model_requested, usage, self._settings.pricing)
        row = LLMUsage(
            execution_id=uuid.UUID(execution_id) if execution_id else None,
            mentor_ref=mentor_ref,
            provider=provider,
            model_requested=model_requested,
            model_served=model_served,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            cost_usd=cost,
            stop_reason=stop_reason,
            outcome=outcome,
            latency_ms=latency_ms,
            provider_request_id=provider_request_id,
            created_at=datetime.now(UTC),
        )
        async with self._db.session() as session:
            session.add(row)
            await session.commit()

    async def summary(self) -> dict[str, object]:
        async with self._db.session() as session:
            rows = (
                await session.execute(
                    select(
                        LLMUsage.model_requested,
                        LLMUsage.outcome,
                        func.count(),
                        func.sum(LLMUsage.input_tokens),
                        func.sum(LLMUsage.output_tokens),
                        func.sum(LLMUsage.cache_read_tokens),
                        func.sum(LLMUsage.cost_usd),
                    ).group_by(LLMUsage.model_requested, LLMUsage.outcome)
                )
            ).all()
        return {
            "by_model_and_outcome": [
                {
                    "model": r[0],
                    "outcome": r[1],
                    "calls": r[2],
                    "input_tokens": int(r[3] or 0),
                    "output_tokens": int(r[4] or 0),
                    "cache_read_tokens": int(r[5] or 0),
                    "cost_usd": float(r[6]) if r[6] is not None else None,
                }
                for r in rows
            ],
            "cost_note": "cost_usd is null when LLM_PRICING has no entry for the model",
        }

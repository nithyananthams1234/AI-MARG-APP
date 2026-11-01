"""Reporting Agent: daily/weekly activity summaries from actual records, with AI narrative kept separate."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.base_agent import (
    AgentContext,
    AgentInput,
    Analysis,
    BaseAgent,
    InsightValidationError,
    PlanSpec,
)
from app.providers.base import ComplexityHint, DataSection, LLMRequest
from app.services.reporting import activity_report
from app.utils.datetime_utils import local_day_bounds


class ReportInput(AgentInput):
    period: Literal["daily", "weekly"] = "daily"
    end_date: date | None = Field(default=None, description="Last local date covered; defaults to today")


class ReportNarrative(BaseModel):
    narrative: str = Field(max_length=1500)
    highlights: list[str] = Field(max_length=6)


_NUMBER = re.compile(r"\b\d+\b")


class ReportingAgent(BaseAgent[ReportInput]):
    agent_id = "reporting"
    description = (
        "Generates daily/weekly activity reports from records; AI narrative is labelled and number-checked"
    )
    input_model = ReportInput
    prompt_id = "reporting"
    insight_model = ReportNarrative
    complexity = ComplexityHint.standard

    def analyse(self, ctx: AgentContext, inp: ReportInput) -> Analysis:
        end_day = inp.end_date or ctx.today
        start_day = end_day if inp.period == "daily" else end_day - timedelta(days=6)
        lo, hi = local_day_bounds(start_day, ctx.tz)[0], local_day_bounds(end_day, ctx.tz)[1]
        facts_model = activity_report(ctx.snapshot, lo, hi, ctx.now)
        facts = {
            "period": inp.period,
            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(),
            "records": facts_model.model_dump(mode="json"),
            "label": "Actual records from the data source (DEMO DATA in this prototype)",
        }
        return Analysis(
            facts=facts,
            extra={"allowed_numbers": facts_model.numbers()},
            plan=PlanSpec(plan_type=f"{inp.period}_report", period_start=lo, period_end=hi),
        )

    def llm_request(self, ctx: AgentContext, inp: ReportInput, analysis: Analysis) -> LLMRequest:
        r = analysis.facts["records"]
        counts = {
            "tasks_completed": len(r["tasks_completed"]),
            "tasks_open": r["tasks_open"],
            "tasks_overdue": len(r["tasks_overdue"]),
            "visits_completed": len(r["visits_completed"]),
            "visits_planned_upcoming": len(r["visits_planned_upcoming"]),
            "followups_by_status": r["followups_by_status"],
            "followups_verified_in_period": r["followups_verified_in_period"],
            "teacher_responses_in_period": r["teacher_responses_in_period"],
            "evidence_submissions_in_period": r["evidence_submissions_in_period"],
            "overdue_task_titles": [t["title"] for t in r["tasks_overdue"]],
            "data_gaps": r["data_gaps"],
        }
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=[DataSection("report_counts", counts)],
            instruction=(
                f"Write a short {inp.period} activity narrative and up to five highlights. Use "
                "only the counts provided; do not write dates or any other numbers."
            ),
        )

    def validate_insights(self, insights: ReportNarrative, analysis: Analysis) -> ReportNarrative:  # type: ignore[override]
        allowed = analysis.extra["allowed_numbers"]
        text = " ".join([insights.narrative, *insights.highlights])
        unknown = {n for n in _NUMBER.findall(text) if n not in allowed}
        if unknown:
            raise InsightValidationError(
                f"Narrative contains numbers not present in records: {sorted(unknown)}"
            )
        return insights

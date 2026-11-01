"""Workload Intelligence Agent: workload index from verified inputs, overloaded periods, adjustments."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field

from app.agents.base_agent import AgentContext, AgentInput, Analysis, BaseAgent
from app.providers.base import ComplexityHint, DataSection, LLMRequest
from app.schemas.common import TaskStatus, VisitStatus
from app.services.workload import window_workload
from app.utils.datetime_utils import local_day_bounds


class WorkloadInput(AgentInput):
    start_date: date | None = None
    days: int = Field(default=7, ge=1, le=31)


class WorkloadInsights(BaseModel):
    summary: str = Field(max_length=1000)
    recommendations: list[str] = Field(max_length=6)


class WorkloadAgent(BaseAgent[WorkloadInput]):
    agent_id = "workload_intelligence"
    description = "Calculates the workload index, identifies overloaded days, unassigned and overdue work"
    input_model = WorkloadInput
    prompt_id = "workload_intelligence"
    insight_model = WorkloadInsights
    complexity = ComplexityHint.standard

    def analyse(self, ctx: AgentContext, inp: WorkloadInput) -> Analysis:
        s, st = ctx.snapshot, ctx.settings
        start = inp.start_date or ctx.today
        summary = window_workload(
            s, start, inp.days, ctx.now, st.workload_high_threshold, st.workload_overload_threshold
        )
        adjustments = []
        for day in summary.overloaded_days:
            lo, hi = local_day_bounds(day, ctx.tz)
            movable = [
                {"ref": v.id, "type": "planned_school_visit"}
                for v in s.visits
                if v.status == VisitStatus.planned and lo <= v.scheduled_start < hi
            ]
            movable += [
                {"ref": a.id, "type": "workload_activity"}
                for a in s.workload_activities
                if a.activity_date == day and a.status in (TaskStatus.pending, TaskStatus.in_progress)
            ]
            adjustments.append(
                {
                    "date": day.isoformat(),
                    "candidates_to_move": movable,
                    "note": "Fixed meetings/trainings are not proposed for moving",
                }
            )
        unassigned = [
            {"task_ref": t.id, "title": t.title, "reason": "no due date recorded"}
            for t in s.tasks
            if t.status in (TaskStatus.pending, TaskStatus.in_progress) and t.due_at is None
        ]
        window_end = local_day_bounds(start + timedelta(days=inp.days - 1), ctx.tz)[1]
        later = [
            t.id
            for t in s.tasks
            if t.status in (TaskStatus.pending, TaskStatus.in_progress)
            and t.due_at is not None
            and t.due_at >= window_end
        ]
        facts = {
            "workload": summary.model_dump(mode="json", exclude={"missing_data"}),
            "unassigned_work": unassigned,
            "tasks_due_after_window": later,
            "adjustment_candidates": adjustments,
        }
        return Analysis(facts=facts, missing_data=summary.missing_data)

    def needs_llm(self, ctx: AgentContext, inp: WorkloadInput, analysis: Analysis) -> bool:
        w = analysis.facts["workload"]
        return w["workload_index"] is not None and (w["status"] != "normal" or bool(w["overloaded_days"]))

    def llm_request(self, ctx: AgentContext, inp: WorkloadInput, analysis: Analysis) -> LLMRequest:
        w = analysis.facts["workload"]
        data = {
            k: w[k]
            for k in (
                "workload_index",
                "index_is_lower_bound",
                "status",
                "overloaded_days",
                "per_day",
                "overdue_tasks",
                "tasks_without_estimate",
                "thresholds",
            )
        }
        data["adjustment_candidates"] = analysis.facts["adjustment_candidates"]
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=[DataSection("workload", data)],
            instruction="Summarise the workload position and recommend up to five practical adjustments.",
        )

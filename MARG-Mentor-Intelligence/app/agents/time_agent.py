"""Time Management Agent: available hours, time requirements, conflicts, allocation suggestions."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field

from app.agents.base_agent import AgentContext, AgentInput, Analysis, BaseAgent
from app.providers.base import ComplexityHint, DataSection, LLMRequest
from app.schemas.common import MissingData
from app.services.planning import priorities_for
from app.services.priority import OPEN_STATUSES, rank_tasks
from app.services.schedule import calendar_entries, find_conflicts, free_slots, working_hours_missing
from app.services.workload import day_load
from app.utils.datetime_utils import local_day_bounds


class TimeManagementInput(AgentInput):
    start_date: date | None = None
    days: int = Field(default=5, ge=1, le=14)


class TimeInsights(BaseModel):
    summary: str = Field(max_length=1000)
    suggestions: list[str] = Field(max_length=6)


class TimeManagementAgent(BaseAgent[TimeManagementInput]):
    agent_id = "time_management"
    description = "Analyses available working time, task time requirements and conflicts; suggests allocation"
    input_model = TimeManagementInput
    prompt_id = "time_management"
    insight_model = TimeInsights
    complexity = ComplexityHint.light

    def analyse(self, ctx: AgentContext, inp: TimeManagementInput) -> Analysis:
        s, st = ctx.snapshot, ctx.settings
        start = inp.start_date or ctx.today
        missing: list[MissingData] = working_hours_missing(s)
        days = []
        free_by_day: dict[date, int] = {}
        for i in range(inp.days):
            day = start + timedelta(days=i)
            lo, hi = local_day_bounds(day, ctx.tz)
            entries = calendar_entries(s, lo, hi)
            load = day_load(s, day, st.workload_high_threshold, st.workload_overload_threshold)
            free = sum(x.minutes for x in free_slots(s, day, entries))
            free_after_activities = (
                max(0, free - load.activity_minutes) if load.available_minutes is not None else None
            )
            free_by_day[day] = free_after_activities or 0
            days.append(
                {
                    "date": day.isoformat(),
                    "working_day": load.working_day,
                    "available_minutes": load.available_minutes,
                    "scheduled_minutes": load.scheduled_minutes,
                    "activity_minutes": load.activity_minutes,
                    "free_minutes": free_after_activities,
                    "conflicts": len(find_conflicts(s, entries)),
                    "status": load.status,
                }
            )
        window_end = local_day_bounds(start + timedelta(days=inp.days - 1), ctx.tz)[1]
        results = priorities_for(s, ctx.now, st.deadline_horizon_days, st.dependency_points_per_blocked_task)
        allocations, unallocated = [], []
        tasks = {t.id: t for t in s.tasks if t.status in OPEN_STATUSES}
        for r in rank_tasks(results, s.tasks, ctx.now):
            t = tasks[r["task_ref"]]
            if t.due_at is None or t.due_at >= window_end:
                continue
            if t.estimated_minutes is None:
                unallocated.append({"task_ref": t.id, "reason": "time estimate not recorded"})
                missing.append(
                    MissingData(
                        entity_type="task",
                        entity_ref=t.id,
                        field="estimated_minutes",
                        impact="Time requirement unknown",
                    )
                )
                continue
            due_day = t.due_at.astimezone(ctx.tz).date()
            target = next(
                (
                    d
                    for d in sorted(free_by_day)
                    if free_by_day[d] >= t.estimated_minutes and d <= max(due_day, start)
                ),
                None,
            )
            if target is None:
                unallocated.append({"task_ref": t.id, "reason": "not enough free time before the due date"})
                continue
            free_by_day[target] -= t.estimated_minutes
            allocations.append(
                {
                    "task_ref": t.id,
                    "title": t.title,
                    "suggested_date": target.isoformat(),
                    "minutes": t.estimated_minutes,
                    "due_date": due_day.isoformat(),
                }
            )
        demand = sum(tasks[a["task_ref"]].estimated_minutes or 0 for a in allocations) + sum(
            tasks[u["task_ref"]].estimated_minutes or 0 for u in unallocated
        )
        total_free = sum(d["free_minutes"] or 0 for d in days)
        facts = {
            "window": {"start_date": start.isoformat(), "days": inp.days},
            "days": days,
            "task_time_demand_minutes": demand,
            "free_minutes_in_window": total_free if not working_hours_missing(s) else None,
            "capacity_gap_minutes": max(0, demand - total_free) if not working_hours_missing(s) else None,
            "suggested_allocation": allocations,
            "unallocated": unallocated,
        }
        return Analysis(facts=facts, missing_data=missing)

    def needs_llm(self, ctx: AgentContext, inp: TimeManagementInput, analysis: Analysis) -> bool:
        return analysis.facts["free_minutes_in_window"] is not None

    def llm_request(self, ctx: AgentContext, inp: TimeManagementInput, analysis: Analysis) -> LLMRequest:
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=[DataSection("time_analysis", analysis.facts)],
            instruction="Summarise the time situation and give up to five practical allocation suggestions.",
        )

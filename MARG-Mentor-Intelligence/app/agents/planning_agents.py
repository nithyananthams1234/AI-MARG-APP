"""Daily and Weekly Planning Agents. They reuse the deterministic services of the other agents."""

from __future__ import annotations

import datetime as dt
from datetime import date, timedelta

from pydantic import BaseModel, Field

from app.agents.base_agent import AgentContext, AgentInput, Analysis, BaseAgent, PlanSpec, keep_known
from app.providers.base import ComplexityHint, DataSection, LLMRequest
from app.schemas.common import TaskStatus
from app.services.followups import analyse_followups
from app.services.planning import build_day_plan
from app.services.reporting import activity_report
from app.services.schedule import calendar_entries, find_conflicts
from app.services.visits import school_attention
from app.services.workload import window_workload
from app.utils.datetime_utils import fmt_local, local_day_bounds


# ----------------------------------------------------------------------------- daily
class DailyPlanInput(AgentInput):
    date: dt.date | None = Field(
        default=None, description="Local date; defaults to today in the mentor's timezone"
    )


class ItemExplanation(BaseModel):
    ref: str
    explanation: str = Field(max_length=400)


class DailyPlanNarrative(BaseModel):
    overview: str = Field(max_length=1200)
    item_explanations: list[ItemExplanation] = Field(max_length=20)
    advice: list[str] = Field(default_factory=list, max_length=5)


class DailyPlanningAgent(BaseAgent[DailyPlanInput]):
    agent_id = "daily_planning"
    description = "Combines tasks, schedule, deadlines, follow-ups and workload into a realistic daily plan"
    input_model = DailyPlanInput
    prompt_id = "daily_planning"
    insight_model = DailyPlanNarrative
    complexity = ComplexityHint.standard

    def analyse(self, ctx: AgentContext, inp: DailyPlanInput) -> Analysis:
        s, st, tz = ctx.snapshot, ctx.settings, ctx.tz
        day = inp.date or ctx.today
        plan, _ = build_day_plan(
            s, day, ctx.now, st.deadline_horizon_days, st.dependency_points_per_blocked_task
        )
        fu = analyse_followups(s, ctx.now)
        day_end = local_day_bounds(day, tz)[1]
        attention = [
            {"followup_ref": i.followup_ref, "action_plan_title": i.action_plan_title, "flags": i.flags}
            for i in fu.items
            if i.overdue
            or "verification_required" in i.flags
            or (i.due_at and i.due_at < day_end and i.category != "resolved")
        ]
        facts = {
            "date": day.isoformat(),
            "timezone": s.mentor.timezone,
            "working_window": {k: fmt_local(v, tz) for k, v in plan.working_window.items()}
            if plan.working_window
            else None,
            "timeline": [
                i.model_dump(mode="json") | {"start": fmt_local(i.start, tz), "end": fmt_local(i.end, tz)}
                for i in plan.timeline
            ],
            "cannot_fit_or_not_schedulable": [u.model_dump() for u in plan.unscheduled],
            "conflicts": [c.model_dump() for c in plan.conflicts],
            "capacity_minutes": plan.capacity,
            "critical_tasks": plan.critical_items,
            "followups_needing_attention": attention,
            "note": plan.note,
        }
        refs = {i.ref for i in plan.timeline} | {u.ref for u in plan.unscheduled}
        lo, hi = local_day_bounds(day, tz)
        return Analysis(
            facts=facts,
            known_refs=refs,
            missing_data=plan.missing_data,
            plan=PlanSpec(plan_type="daily_plan", period_start=lo, period_end=hi),
        )

    def needs_llm(self, ctx: AgentContext, inp: DailyPlanInput, analysis: Analysis) -> bool:
        return bool(analysis.facts["timeline"] or analysis.facts["cannot_fit_or_not_schedulable"])

    def llm_request(self, ctx: AgentContext, inp: DailyPlanInput, analysis: Analysis) -> LLMRequest:
        f = analysis.facts
        data = {
            k: f[k]
            for k in (
                "date",
                "timeline",
                "cannot_fit_or_not_schedulable",
                "conflicts",
                "capacity_minutes",
                "critical_tasks",
                "followups_needing_attention",
                "note",
            )
        }
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=[DataSection("daily_plan", data)],
            instruction=(
                "Write a short overview of the day, explain why each placed item is "
                "prioritised (refer to items by ref), and give up to three pieces of advice "
                "about items that could not fit and about conflicts."
            ),
        )

    def validate_insights(self, insights: DailyPlanNarrative, analysis: Analysis) -> DailyPlanNarrative:  # type: ignore[override]
        insights.item_explanations = keep_known(insights.item_explanations, "ref", analysis.known_refs)
        return insights


# ----------------------------------------------------------------------------- weekly
class WeeklyPlanInput(AgentInput):
    week_start: date | None = Field(
        default=None, description="First day of the 7-day plan; defaults to today"
    )


class WeeklyNarrative(BaseModel):
    overview: str = Field(max_length=1500)
    weekly_priorities: list[str] = Field(max_length=7)
    risks: list[str] = Field(default_factory=list, max_length=6)
    visit_and_followup_distribution: list[str] = Field(default_factory=list, max_length=6)


class WeeklyPlanningAgent(BaseAgent[WeeklyPlanInput]):
    agent_id = "weekly_planning"
    description = "Prepares weekly priorities, deadlines, visit/follow-up distribution and workload conflicts"
    input_model = WeeklyPlanInput
    prompt_id = "weekly_planning"
    insight_model = WeeklyNarrative
    complexity = ComplexityHint.complex

    def analyse(self, ctx: AgentContext, inp: WeeklyPlanInput) -> Analysis:
        s, st, tz = ctx.snapshot, ctx.settings, ctx.tz
        start = inp.week_start or ctx.today
        lo = local_day_bounds(start, tz)[0]
        hi = local_day_bounds(start + timedelta(days=6), tz)[1]
        workload = window_workload(
            s, start, 7, ctx.now, st.workload_high_threshold, st.workload_overload_threshold
        )
        entries = calendar_entries(s, lo, hi)
        conflicts = find_conflicts(s, entries)
        open_status = (TaskStatus.pending, TaskStatus.in_progress)
        deadlines = sorted(
            (
                {"task_ref": t.id, "title": t.title, "due_at": fmt_local(t.due_at, tz)}
                for t in s.tasks
                if t.status in open_status and t.due_at and lo <= t.due_at < hi
            ),
            key=lambda d: d["due_at"] or "",
        )
        overdue = [
            {"task_ref": t.id, "title": t.title}
            for t in s.tasks
            if t.status in open_status and t.due_at and t.due_at < ctx.now
        ]
        visits_by_day: dict[str, list] = {}
        for e in entries:
            if e.kind == "school_visit":
                visits_by_day.setdefault(e.start.astimezone(tz).date().isoformat(), []).append(
                    {"visit_ref": e.ref, "school_ref": e.school_ref, "start": fmt_local(e.start, tz)}
                )
        fu = analyse_followups(s, ctx.now)
        followups_due = [
            {"followup_ref": i.followup_ref, "due_at": fmt_local(i.due_at, tz), "status": i.status.value}
            for i in fu.items
            if i.category != "resolved" and i.due_at and i.due_at < hi
        ]
        attention = [a for a in school_attention(s, ctx.now) if a.next_planned_visit is None][:3]
        last_week = activity_report(s, lo - timedelta(days=7), lo, ctx.now)
        facts = {
            "week": {"start_date": start.isoformat(), "end_date": (start + timedelta(days=6)).isoformat()},
            "workload": {k: v for k, v in workload.model_dump(mode="json").items() if k != "missing_data"},
            "deadlines_this_week": deadlines,
            "already_overdue": overdue,
            "visits_by_day": visits_by_day,
            "followups_due_or_overdue": followups_due,
            "schools_needing_visit_unplanned": [
                {
                    "school_ref": a.school_ref,
                    "school_name": a.school_name,
                    "attention_score": a.attention_score,
                    "flags": a.flags,
                }
                for a in attention
            ],
            "conflicts": [c.model_dump() for c in conflicts],
            "previous_week": {
                "tasks_completed": len(last_week.tasks_completed),
                "visits_completed": len(last_week.visits_completed),
                "followups_verified": last_week.followups_verified_in_period,
            },
        }
        return Analysis(
            facts=facts,
            missing_data=workload.missing_data,
            plan=PlanSpec(plan_type="weekly_plan", period_start=lo, period_end=hi),
        )

    def llm_request(self, ctx: AgentContext, inp: WeeklyPlanInput, analysis: Analysis) -> LLMRequest:
        f = analysis.facts
        data = {k: f[k] for k in f if k != "workload"} | {
            "workload": {
                k: f["workload"][k]
                for k in ("workload_index", "index_is_lower_bound", "status", "overloaded_days", "per_day")
            }
        }
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=[DataSection("week", data)],
            instruction=(
                "Prepare the weekly plan: an overview, up to seven priorities, risks, and how "
                "to distribute school visits and follow-ups across the week."
            ),
        )

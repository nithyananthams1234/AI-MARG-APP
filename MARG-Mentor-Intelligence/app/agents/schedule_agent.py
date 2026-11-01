"""Schedule Intelligence Agent: conflicts, free time and reschedule proposals (never invented availability)."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field

from app.agents.base_agent import AgentContext, AgentInput, Analysis, BaseAgent, ProposedAction
from app.providers.base import ComplexityHint, DataSection, LLMRequest
from app.schemas.common import MissingData
from app.services.schedule import (
    calendar_entries,
    find_conflicts,
    find_visit_slot,
    free_slots,
    working_hours_missing,
)
from app.utils.datetime_utils import fmt_local, local_day_bounds, minutes_between


class ScheduleInput(AgentInput):
    start_date: date | None = None
    days: int = Field(default=7, ge=1, le=21)


class ScheduleInsights(BaseModel):
    summary: str = Field(max_length=1000)
    suggestions: list[str] = Field(max_length=6)


class ScheduleAgent(BaseAgent[ScheduleInput]):
    agent_id = "schedule_intelligence"
    description = "Reviews visits, meetings and activities; detects conflicts; proposes reschedules when a verified slot exists"
    input_model = ScheduleInput
    prompt_id = "schedule_intelligence"
    insight_model = ScheduleInsights
    complexity = ComplexityHint.standard
    allowed_actions = frozenset({"reschedule_visit"})

    def analyse(self, ctx: AgentContext, inp: ScheduleInput) -> Analysis:
        s, tz = ctx.snapshot, ctx.tz
        start = inp.start_date or ctx.today
        lo = local_day_bounds(start, tz)[0]
        hi = local_day_bounds(start + timedelta(days=inp.days - 1), tz)[1]
        entries = calendar_entries(s, lo, hi)
        conflicts = find_conflicts(s, entries)
        missing: list[MissingData] = working_hours_missing(s)
        free = []
        for i in range(inp.days):
            day = start + timedelta(days=i)
            d_lo, d_hi = local_day_bounds(day, tz)
            slots = free_slots(s, day, [e for e in entries if e.end > d_lo and e.start < d_hi])
            free.append(
                {
                    "date": day.isoformat(),
                    "free_minutes": sum(x.minutes for x in slots),
                    "slots": [{"start": fmt_local(x.start, tz), "end": fmt_local(x.end, tz)} for x in slots],
                }
            )

        proposals: list[ProposedAction] = []
        not_resolved = []
        by_ref = {e.ref: e for e in entries}
        handled: set[str] = set()
        for c in conflicts:
            if c.type not in {"overlap", "school_unavailable"}:
                continue
            visit = next(
                (by_ref[r] for r in c.entries if by_ref[r].kind == "school_visit" and by_ref[r].movable), None
            )
            if visit is None or visit.ref in handled:
                if visit is None:
                    not_resolved.append({"conflict": c.entries, "reason": "no movable school visit involved"})
                continue
            handled.add(visit.ref)
            duration = minutes_between(visit.start, visit.end)
            others = [e for e in entries if e.ref != visit.ref]
            slot = find_visit_slot(
                s,
                visit.school_ref or "",
                duration,
                visit.start.astimezone(tz).date() + timedelta(days=1),
                10,
                others,
                not_before=ctx.now,
            )
            school = s.school(visit.school_ref)
            if slot is None:
                reason = (
                    "travel time to the school is not recorded"
                    if school and school.travel_minutes_from_base is None
                    else "no free slot that fits recorded availability in the next 10 days"
                )
                not_resolved.append({"conflict": c.entries, "visit_ref": visit.ref, "reason": reason})
                if school and school.travel_minutes_from_base is None:
                    missing.append(
                        MissingData(
                            entity_type="school",
                            entity_ref=school.id,
                            field="travel_minutes_from_base",
                            impact="Cannot verify a feasible alternative visit time",
                        )
                    )
                continue
            proposals.append(
                ProposedAction(
                    action_type="reschedule_visit",
                    target_type="school_visit",
                    target_ref=visit.ref,
                    payload={
                        "visit_ref": visit.ref,
                        "new_start": slot[0].astimezone(tz).isoformat(),
                        "new_end": slot[1].astimezone(tz).isoformat(),
                        "previous_start": visit.start.astimezone(tz).isoformat(),
                        "previous_end": visit.end.astimezone(tz).isoformat(),
                    },
                    rationale=(
                        f"{c.detail}. Proposed slot is free in the recorded calendar, within working hours, on a day "
                        f"{school.name if school else 'the school'} is recorded as available, with recorded travel time."
                    ),
                )
            )
        facts = {
            "window": {"start_date": start.isoformat(), "days": inp.days},
            "entries": [
                {
                    "ref": e.ref,
                    "kind": e.kind,
                    "title": e.title,
                    "start": fmt_local(e.start, tz),
                    "end": fmt_local(e.end, tz),
                    "school_ref": e.school_ref,
                }
                for e in entries
            ],
            "conflicts": [c.model_dump() for c in conflicts],
            "free_time": free,
            "conflicts_without_proposal": not_resolved,
        }
        return Analysis(facts=facts, missing_data=missing, proposals=proposals)

    def needs_llm(self, ctx: AgentContext, inp: ScheduleInput, analysis: Analysis) -> bool:
        return bool(analysis.facts["conflicts"])

    def llm_request(self, ctx: AgentContext, inp: ScheduleInput, analysis: Analysis) -> LLMRequest:
        data = {k: analysis.facts[k] for k in ("conflicts", "conflicts_without_proposal")}
        data["proposed_reschedules"] = [p.payload for p in analysis.proposals]
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=[DataSection("schedule_analysis", data)],
            instruction="Summarise the schedule conflicts and suggest up to five ways to resolve them.",
        )

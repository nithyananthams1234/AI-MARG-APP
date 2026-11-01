"""School Visit Planning Agent: schools needing attention, visit priorities, slot proposals, pre-visit briefs."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field

from app.agents.base_agent import AgentContext, AgentInput, Analysis, BaseAgent, ProposedAction, keep_known
from app.providers.base import ComplexityHint, DataSection, LLMRequest
from app.schemas.common import MissingData
from app.services.followups import RESOLVED
from app.services.schedule import CalendarEntry, calendar_entries, find_visit_slot
from app.services.visits import OPEN_PLAN, school_attention
from app.utils.datetime_utils import fmt_local, local_day_bounds


class VisitPlanningInput(AgentInput):
    start_date: date | None = None
    days: int = Field(default=7, ge=1, le=21)
    max_schools: int = Field(default=3, ge=1, le=10)


class SchoolFocus(BaseModel):
    school_ref: str
    focus_points: list[str] = Field(max_length=5)
    checklist: list[str] = Field(max_length=8)


class VisitInsights(BaseModel):
    summary: str = Field(max_length=1000)
    schools: list[SchoolFocus] = Field(max_length=10)


class SchoolVisitPlanningAgent(BaseAgent[VisitPlanningInput]):
    agent_id = "school_visit_planning"
    description = "Ranks schools needing visits from recorded history and pending work; proposes visit slots"
    input_model = VisitPlanningInput
    prompt_id = "school_visit_planning"
    insight_model = VisitInsights
    complexity = ComplexityHint.standard
    allowed_actions = frozenset({"schedule_visit"})

    def analyse(self, ctx: AgentContext, inp: VisitPlanningInput) -> Analysis:
        s, tz = ctx.snapshot, ctx.tz
        start = inp.start_date or ctx.today
        ranking = school_attention(s, ctx.now)
        duration = ctx.settings.visit_duration_minutes
        missing: list[MissingData] = []
        if duration is None:
            missing.append(
                MissingData(
                    entity_type="configuration",
                    field="VISIT_DURATION_MINUTES",
                    impact="Visit slots cannot be suggested without a configured visit duration",
                )
            )
        lo = local_day_bounds(start, tz)[0]
        hi = local_day_bounds(start + timedelta(days=inp.days + 10), tz)[1]
        entries = calendar_entries(s, lo, hi)
        proposals: list[ProposedAction] = []
        recommended = []
        for att in ranking[: inp.max_schools]:
            school = s.school(att.school_ref)
            assert school is not None
            brief = self._brief(ctx, att.school_ref)
            item = {
                "school_ref": att.school_ref,
                "school_name": att.school_name,
                "attention": att.model_dump(mode="json"),
                "pre_visit_brief": brief,
                "suggested_slot": None,
                "slot_note": None,
            }
            if att.next_planned_visit is not None:
                item["slot_note"] = f"Visit already planned for {fmt_local(att.next_planned_visit, tz)}"
            elif duration is None:
                item["slot_note"] = "Visit duration not configured"
            elif school.travel_minutes_from_base is None:
                item["slot_note"] = "Travel time not recorded - slot not suggested"
                missing.append(
                    MissingData(
                        entity_type="school",
                        entity_ref=school.id,
                        field="travel_minutes_from_base",
                        impact="Cannot suggest a feasible visit slot",
                    )
                )
            else:
                slot = find_visit_slot(s, school.id, duration, start, inp.days, entries, not_before=ctx.now)
                if slot is None:
                    item["slot_note"] = "No free slot matching recorded availability in the window"
                else:
                    item["suggested_slot"] = {"start": fmt_local(slot[0], tz), "end": fmt_local(slot[1], tz)}
                    # Reserve the slot so the next suggested visit does not overlap it.
                    entries = sorted(
                        [
                            *entries,
                            CalendarEntry(
                                ref=f"proposed-{school.id}",
                                kind="school_visit",
                                title="proposed visit",
                                start=slot[0],
                                end=slot[1],
                                school_ref=school.id,
                            ),
                        ],
                        key=lambda e: e.start,
                    )
                    proposals.append(
                        ProposedAction(
                            action_type="schedule_visit",
                            target_type="school",
                            target_ref=school.id,
                            payload={
                                "school_ref": school.id,
                                "start": slot[0].astimezone(tz).isoformat(),
                                "end": slot[1].astimezone(tz).isoformat(),
                                "purpose": "Follow-up visit (proposed by School Visit Planning Agent)",
                            },
                            rationale=f"Attention score {att.attention_score}: "
                            + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in att.components.items() if v),
                        )
                    )
            if "no_completed_visit_in_records" in att.flags:
                missing.append(
                    MissingData(
                        entity_type="school",
                        entity_ref=school.id,
                        field="last_completed_visit",
                        impact="Days-since-visit component excluded from the attention score",
                    )
                )
            recommended.append(item)
        facts = {
            "window": {"start_date": start.isoformat(), "days": inp.days},
            "score_method": "days since last visit (max 40) + overdue follow-ups (15 each, max 30) + open action "
            "plans (5 each, max 15) + open tasks (5 each, max 15)",
            "recommended_visits": recommended,
            "all_schools_ranked": [
                {
                    "school_ref": a.school_ref,
                    "school_name": a.school_name,
                    "attention_score": a.attention_score,
                    "score_complete": a.score_complete,
                    "flags": a.flags,
                }
                for a in ranking
            ],
        }
        return Analysis(
            facts=facts,
            known_refs={r["school_ref"] for r in recommended},
            missing_data=missing,
            proposals=proposals,
        )

    @staticmethod
    def _brief(ctx: AgentContext, school_ref: str) -> dict:
        s = ctx.snapshot
        plans = [
            {
                "action_plan_ref": p.id,
                "title": p.title,
                "status": p.status.value,
                "due_date": p.due_date.isoformat() if p.due_date else None,
            }
            for p in s.action_plans
            if p.school_ref == school_ref and p.status in OPEN_PLAN
        ]
        overdue = [
            {"followup_ref": f.id, "status": f.status.value}
            for f in s.followups
            if f.school_ref == school_ref and f.status not in RESOLVED and f.due_at and f.due_at < ctx.now
        ]
        last_obs = sorted(
            (o for o in s.observations if o.school_ref == school_ref), key=lambda o: o.observed_at
        )
        return {
            "open_action_plans": plans,
            "overdue_followups": overdue,
            "latest_observation_support_areas": last_obs[-1].support_areas if last_obs else [],
            "teachers": len([t for t in s.teachers if t.school_ref == school_ref]),
        }

    def llm_request(self, ctx: AgentContext, inp: VisitPlanningInput, analysis: Analysis) -> LLMRequest:
        data = [
            {
                "school_ref": r["school_ref"],
                "attention": {
                    k: r["attention"][k]
                    for k in (
                        "days_since_last_visit",
                        "overdue_followups",
                        "open_action_plans",
                        "open_tasks",
                        "flags",
                    )
                },
                "pre_visit_brief": r["pre_visit_brief"],
            }
            for r in analysis.facts["recommended_visits"]
        ]
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=[DataSection("schools_needing_visits", data)],
            instruction="For each school give up to five focus points and a short pre-visit checklist, "
            "based only on the records provided.",
        )

    def validate_insights(self, insights: VisitInsights, analysis: Analysis) -> VisitInsights:  # type: ignore[override]
        insights.schools = keep_known(insights.schools, "school_ref", analysis.known_refs)
        return insights

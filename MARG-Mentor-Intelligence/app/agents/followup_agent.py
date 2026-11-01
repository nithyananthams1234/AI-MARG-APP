"""Follow-up Agent: pending teacher responses, action-plan progress, overdue items, verification reminders.

Teacher-reported progress, submitted evidence and mentor verification are kept separate. This agent
never marks anything as mentor-verified; it only reminds the mentor that verification is required.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base_agent import AgentContext, AgentInput, Analysis, BaseAgent, keep_known
from app.providers.base import ComplexityHint, DataSection, LLMRequest
from app.schemas.common import MissingData
from app.services.followups import analyse_followups


class FollowupInput(AgentInput):
    pass


class FollowupStep(BaseModel):
    followup_ref: str
    step: str = Field(max_length=400)


class FollowupInsights(BaseModel):
    summary: str = Field(max_length=1000)
    next_steps: list[FollowupStep] = Field(max_length=10)


class FollowupAgent(BaseAgent[FollowupInput]):
    agent_id = "followup_management"
    description = "Tracks teacher responses, evidence and mentor verification; highlights overdue follow-ups"
    input_model = FollowupInput
    prompt_id = "followup_management"
    insight_model = FollowupInsights
    complexity = ComplexityHint.light

    def analyse(self, ctx: AgentContext, inp: FollowupInput) -> Analysis:
        result = analyse_followups(ctx.snapshot, ctx.now)
        missing = [
            MissingData(
                entity_type="followup",
                entity_ref=i.followup_ref,
                field="due_at",
                impact="Overdue status cannot be determined",
            )
            for i in result.items
            if "due_date_not_recorded" in i.flags
        ]
        reminders = [
            {
                "followup_ref": i.followup_ref,
                "reminder": "Mentor verification required",
                "basis": "teacher response/evidence received; not yet verified by the mentor",
            }
            for i in result.items
            if "verification_required" in i.flags
        ]
        facts = result.model_dump(mode="json") | {
            "verification_reminders": reminders,
            "rule": "The engine never marks progress as mentor-verified.",
        }
        return Analysis(facts=facts, known_refs={i.followup_ref for i in result.items}, missing_data=missing)

    def needs_llm(self, ctx: AgentContext, inp: FollowupInput, analysis: Analysis) -> bool:
        return any(i["category"] != "resolved" for i in analysis.facts["items"])

    def llm_request(self, ctx: AgentContext, inp: FollowupInput, analysis: Analysis) -> LLMRequest:
        open_items = [
            {
                k: i[k]
                for k in (
                    "followup_ref",
                    "action_plan_title",
                    "status",
                    "overdue",
                    "days_overdue",
                    "category",
                    "flags",
                    "progress",
                )
            }
            for i in analysis.facts["items"]
            if i["category"] != "resolved"
        ][:15]
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=[DataSection("open_followups", open_items), DataSection("counts", analysis.facts["counts"])],
            instruction=(
                "Summarise follow-up status and suggest a next step for the most urgent items. Keep "
                "teacher-reported progress, submitted evidence and mentor verification distinct."
            ),
        )

    def validate_insights(self, insights: FollowupInsights, analysis: Analysis) -> FollowupInsights:  # type: ignore[override]
        insights.next_steps = keep_known(insights.next_steps, "followup_ref", analysis.known_refs)
        return insights

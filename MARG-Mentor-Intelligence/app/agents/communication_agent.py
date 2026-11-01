"""Communication Agent: drafts teacher reminders, feedback and follow-up messages (English / Tamil).

Drafts only. The engine never sends messages. Each draft creates an L3 ``send_teacher_message``
proposal that needs explicit mentor approval; delivery is the MARG application's responsibility.
Personal names are not sent to Claude: the model writes placeholders that are filled in locally.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.agents.base_agent import (
    AgentContext,
    AgentInput,
    Analysis,
    BaseAgent,
    DraftSpec,
    InsightValidationError,
    ProposedAction,
)
from app.providers.base import ComplexityHint, DataSection, LLMRequest
from app.utils.datetime_utils import fmt_local


class CommunicationInput(AgentInput):
    followup_ref: str | None = None
    teacher_ref: str | None = None
    purpose: Literal["reminder", "feedback", "followup"] = "reminder"
    language: Literal["en", "ta"] = "en"
    mentor_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _target(self) -> CommunicationInput:
        if not self.followup_ref and not self.teacher_ref:
            raise ValueError("Provide followup_ref or teacher_ref")
        return self


class MessageDraftOutput(BaseModel):
    body: str = Field(min_length=20, max_length=1200)


PLACEHOLDERS = {"{{teacher_name}}", "{{mentor_name}}", "{{school_name}}"}
_PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")

TEMPLATES = {
    ("en", "reminder"): (
        'Dear {{teacher_name}}, this is a gentle reminder about the action plan "{plan}" at '
        "{{school_name}}. The follow-up was due on {due}. Please share your progress update and any "
        "supporting evidence when convenient. Thank you. - {{mentor_name}}"
    ),
    ("en", "followup"): (
        'Dear {{teacher_name}}, I would like to follow up on the action plan "{plan}" at '
        "{{school_name}}. Please let me know how it is progressing and if you need any support. "
        "Thank you. - {{mentor_name}}"
    ),
    ("en", "feedback"): (
        'Dear {{teacher_name}}, thank you for your work on "{plan}" at {{school_name}}. I will '
        "review the update and share feedback during my next visit. - {{mentor_name}}"
    ),
    ("ta", "reminder"): (
        'அன்புள்ள {{teacher_name}}, {{school_name}} பள்ளியின் "{plan}" செயல் திட்டம் குறித்த '
        "நினைவூட்டல் இது. இதன் பின்தொடர்வு {due} அன்று நிறைவடைய வேண்டியிருந்தது. உங்கள் முன்னேற்றம் "
        "குறித்த தகவலையும் தொடர்புடைய ஆதாரங்களையும் வசதியான நேரத்தில் பகிரவும். நன்றி. - {{mentor_name}}"
    ),
    ("ta", "followup"): (
        'அன்புள்ள {{teacher_name}}, {{school_name}} பள்ளியின் "{plan}" செயல் திட்டத்தின் '
        "முன்னேற்றம் குறித்து அறிய விரும்புகிறேன். ஏதேனும் உதவி தேவைப்பட்டால் தெரிவிக்கவும். நன்றி. "
        "- {{mentor_name}}"
    ),
    ("ta", "feedback"): (
        'அன்புள்ள {{teacher_name}}, {{school_name}} பள்ளியில் "{plan}" தொடர்பான உங்கள் '
        "பணிக்கு நன்றி. அடுத்த பார்வையின்போது எனது கருத்துகளைப் பகிர்கிறேன். - {{mentor_name}}"
    ),
}


class CommunicationAgent(BaseAgent[CommunicationInput]):
    agent_id = "teacher_communication"
    description = (
        "Drafts respectful teacher messages in English or Tamil; never sends; creates an approval proposal"
    )
    input_model = CommunicationInput
    prompt_id = "teacher_communication"
    insight_model = MessageDraftOutput
    complexity = ComplexityHint.light
    allowed_actions = frozenset({"send_teacher_message"})

    def analyse(self, ctx: AgentContext, inp: CommunicationInput) -> Analysis:
        s, tz = ctx.snapshot, ctx.tz
        followup = (
            next((f for f in s.followups if f.id == inp.followup_ref), None) if inp.followup_ref else None
        )
        if inp.followup_ref and followup is None:
            raise LookupError(f"Follow-up {inp.followup_ref!r} not found for this mentor")
        teacher_ref = followup.teacher_ref if followup else inp.teacher_ref
        teacher = s.teacher(teacher_ref)
        if teacher is None:
            raise LookupError(f"Teacher {teacher_ref!r} not found for this mentor")
        if followup and inp.teacher_ref and inp.teacher_ref != followup.teacher_ref:
            raise ValueError("teacher_ref does not match the follow-up's teacher")
        plan = next((p for p in s.action_plans if followup and p.id == followup.action_plan_ref), None)
        school = s.school(teacher.school_ref)
        context = {
            "purpose": inp.purpose,
            "language": "Tamil" if inp.language == "ta" else "English",
            "action_plan_title": plan.title if plan else None,
            "followup_status": followup.status.value if followup else None,
            "due_date": fmt_local(followup.due_at, tz)[:10] if followup and followup.due_at else None,
            "teacher_reported_progress": followup.teacher_reported_progress if followup else None,
            "evidence_submitted": bool(followup and followup.evidence_description),
        }
        facts = {
            "teacher_ref": teacher.id,
            "followup_ref": followup.id if followup else None,
            "school_ref": teacher.school_ref,
            "language": inp.language,
            "purpose": inp.purpose,
            "context_used": context,
            "delivery": "NOT SENT - requires explicit mentor approval and delivery by the MARG application",
        }
        return Analysis(
            facts=facts,
            extra={
                "names": {
                    "{{teacher_name}}": teacher.name,
                    "{{mentor_name}}": s.mentor.name,
                    "{{school_name}}": school.name if school else "",
                },
                "context": context,
                "mentor_note": inp.mentor_note,
                "plan_title": plan.title if plan else inp.purpose,
                "due": context["due_date"] or "-",
            },
        )

    def needs_llm(self, ctx: AgentContext, inp: CommunicationInput, analysis: Analysis) -> bool:
        return True

    def llm_request(self, ctx: AgentContext, inp: CommunicationInput, analysis: Analysis) -> LLMRequest:
        data = [DataSection("message_context", analysis.extra["context"])]
        if analysis.extra["mentor_note"]:
            data.append(DataSection("mentor_note", analysis.extra["mentor_note"]))
        lang = "Tamil (Tamil script)" if inp.language == "ta" else "English"
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=data,
            max_output_tokens=2000,
            instruction=(
                f"Draft a concise, respectful {inp.purpose} message in {lang}. Use the "
                "placeholders {{teacher_name}}, {{school_name}} and {{mentor_name}} instead of "
                "names. Do not use any other placeholders."
            ),
        )

    def validate_insights(self, insights: MessageDraftOutput, analysis: Analysis) -> MessageDraftOutput:  # type: ignore[override]
        unknown = set(_PLACEHOLDER.findall(insights.body)) - PLACEHOLDERS
        if unknown:
            raise InsightValidationError(f"Unknown placeholders in draft: {sorted(unknown)}")
        return insights

    def finalise(
        self,
        ctx: AgentContext,
        inp: CommunicationInput,
        analysis: Analysis,
        insights: MessageDraftOutput | None,
    ) -> Analysis:  # type: ignore[override]
        if insights is not None:
            body, generated_by = insights.body, "ai"
        else:
            template = TEMPLATES[(inp.language, inp.purpose)]
            body = template.replace("{plan}", analysis.extra["plan_title"]).replace(
                "{due}", analysis.extra["due"]
            )
            generated_by = "template"
        for placeholder, value in analysis.extra["names"].items():
            body = body.replace(placeholder, value)
        draft = DraftSpec(
            teacher_ref=analysis.facts["teacher_ref"],
            followup_ref=analysis.facts["followup_ref"],
            purpose=inp.purpose,
            language=inp.language,
            body=body,
            generated_by=generated_by,
        )
        analysis.drafts = [draft]
        analysis.facts["draft"] = {
            "draft_id": str(draft.draft_id),
            "body": body,
            "generated_by": generated_by,
            "language": inp.language,
        }
        if inp.language == "ta" and generated_by == "template":
            analysis.facts["language_note"] = (
                "Tamil template text should be reviewed by a native speaker before use"
            )
        analysis.proposals = [
            ProposedAction(
                action_type="send_teacher_message",
                target_type="teacher",
                target_ref=draft.teacher_ref,
                payload={
                    "draft_id": str(draft.draft_id),
                    "teacher_ref": draft.teacher_ref,
                    "language": draft.language,
                    "purpose": draft.purpose,
                    "body": body,
                },
                rationale="Message drafted for mentor review. Sending requires explicit mentor approval.",
            )
        ]
        return analysis

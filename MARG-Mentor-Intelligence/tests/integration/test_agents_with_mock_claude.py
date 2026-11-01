"""Agents through the orchestrator with a scripted (mock) Claude provider."""

from __future__ import annotations

from app.providers.base import (
    LLMBudgetExceededError,
    LLMOutputInvalidError,
    LLMRefusalError,
    LLMTransientError,
)
from tests.conftest import MENTOR, FakeLLMProvider, build_container, make_settings

TASK_OK = {
    "summary": "Focus on the report first.",
    "next_actions": [
        {"task_ref": "TSK-001", "recommendation": "Finish the report", "reason": "Due today"},
        {"task_ref": "TSK-999", "recommendation": "Invented task", "reason": "Not in records"},
    ],
    "cautions": [],
}


async def run(container, agent, **params):
    return await container.orchestrator.run(agent, {"mentor_ref": "MEN-001", **params}, MENTOR)


async def test_ai_insights_are_validated_and_unknown_refs_dropped(db):
    fake = FakeLLMProvider({"TaskInsights": [TASK_OK]})
    c = build_container(make_settings(), db, provider=fake)
    v = await run(c, "task_intelligence")
    assert v.ai_status == "generated"
    content = v.result["ai_insights"]["content"]
    assert [a["task_ref"] for a in content["next_actions"]] == ["TSK-001"]
    assert v.result["ai_insights"]["label"].startswith("AI-generated")
    # Deterministic score is unchanged by the AI output.
    t1 = next(t for t in v.result["facts"]["tasks"] if t["task_ref"] == "TSK-001")
    assert t1["priority"]["calculation"] == "deterministic" and t1["priority"]["score"] is not None
    request, _ = fake.calls[0]
    assert request.mentor_ref == "MEN-001" and request.prompt_id == "task_intelligence"


async def test_invalid_output_retried_once_then_discarded(db):
    fake = FakeLLMProvider({"TaskInsights": [LLMOutputInvalidError("bad"), LLMOutputInvalidError("bad")]})
    c = build_container(make_settings(), db, provider=fake)
    v = await run(c, "task_intelligence")
    assert v.status.value == "completed"
    assert v.ai_status == "invalid_output" and v.result["ai_insights"] is None
    assert len(fake.calls) == 2
    assert v.result["facts"]["tasks"]  # deterministic result still delivered


async def test_repair_attempt_succeeds(db):
    fake = FakeLLMProvider({"TaskInsights": [LLMOutputInvalidError("bad"), TASK_OK]})
    v = await run(build_container(make_settings(), db, provider=fake), "task_intelligence")
    assert v.ai_status == "generated" and v.result["ai_meta"]["attempts"] == 2


async def test_refusal_transient_and_budget_degrade_gracefully(db):
    for exc, status in [
        (LLMRefusalError("no", "cyber"), "refused"),
        (LLMTransientError("down"), "unavailable"),
        (LLMBudgetExceededError("budget"), "budget_exceeded"),
    ]:
        fake = FakeLLMProvider({"WorkloadInsights": [exc]})
        c = build_container(make_settings(), db, provider=fake)
        v = await run(c, "workload_intelligence", days=7 + len(status))  # vary input -> new execution
        assert v.status.value == "completed" and v.ai_status == status
        assert v.result["facts"]["workload"]["workload_index"] is not None


async def test_use_ai_false_never_calls_claude(db):
    fake = FakeLLMProvider()
    v = await run(build_container(make_settings(), db, provider=fake), "daily_planning", use_ai=False)
    assert v.ai_status == "not_needed" and fake.calls == []


async def test_report_narrative_with_invented_numbers_is_rejected(db):
    bad = {"narrative": "You completed 37 tasks this week.", "highlights": []}
    fake = FakeLLMProvider({"ReportNarrative": [bad, bad]})
    v = await run(build_container(make_settings(), db, provider=fake), "reporting", period="weekly")
    assert v.ai_status == "invalid_output" and v.result["ai_insights"] is None
    good = {"narrative": "There are 2 overdue tasks.", "highlights": ["Follow up on overdue work"]}
    fake2 = FakeLLMProvider({"ReportNarrative": [good]})
    v2 = await run(build_container(make_settings(), db, provider=fake2), "reporting", period="daily")
    assert v2.ai_status == "generated"


async def test_communication_names_never_sent_and_substituted_locally(db):
    body = (
        "வணக்கம் {{teacher_name}}, {{school_name}} பள்ளியின் செயல் திட்டம் குறித்து நினைவூட்டுகிறேன். - {{mentor_name}}"
    )
    fake = FakeLLMProvider({"MessageDraftOutput": [{"body": body}]})
    v = await run(
        build_container(make_settings(), db, provider=fake),
        "teacher_communication",
        followup_ref="FU-001",
        language="ta",
    )
    request, _ = fake.calls[0]
    sent = str([s.payload for s in request.data]) + request.instruction
    assert "Selvi Murugesan" not in sent and "Kavitha" not in sent
    draft = v.result["facts"]["draft"]
    assert "Selvi Murugesan" in draft["body"] and "{{" not in draft["body"]
    assert draft["generated_by"] == "ai"
    [proposal] = v.result["proposals"]
    assert proposal["action_type"] == "send_teacher_message" and proposal["status"] == "pending"
    assert proposal["autonomy_level"] == "L3_explicit_approval" and proposal["requires_external_execution"]


async def test_communication_falls_back_to_template_on_bad_placeholders(db):
    bad = {"body": "Dear {{principal_name}}, please send the report at the earliest. Thanks."}
    fake = FakeLLMProvider({"MessageDraftOutput": [bad, bad]})
    v = await run(
        build_container(make_settings(), db, provider=fake), "teacher_communication", followup_ref="FU-001"
    )
    assert v.ai_status == "invalid_output"
    assert v.result["facts"]["draft"]["generated_by"] == "template"
    assert "Selvi Murugesan" in v.result["facts"]["draft"]["body"]

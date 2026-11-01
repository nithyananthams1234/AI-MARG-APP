"""Controlled live Claude test (costs a small number of tokens).

Run explicitly:  $env:RUN_LIVE_LLM_TESTS="1"; uv run pytest -m live_llm
Requires ANTHROPIC_API_KEY and ANTHROPIC_MODEL in the environment.
"""

from __future__ import annotations

import os

import pytest

from tests.conftest import MENTOR, build_container, make_settings

pytestmark = pytest.mark.live_llm


async def test_daily_plan_with_real_claude(db):
    if os.environ.get("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_LLM_TESTS=1 to run")
    key, model = os.environ.get("ANTHROPIC_API_KEY"), os.environ.get("ANTHROPIC_MODEL")
    if not key or not model:
        pytest.skip("ANTHROPIC_API_KEY and ANTHROPIC_MODEL are required")
    settings = make_settings(
        ai_enabled=True,
        anthropic_api_key=key,
        anthropic_model=model,
        anthropic_refusal_fallback=os.environ.get("ANTHROPIC_REFUSAL_FALLBACK", "off"),
    )
    c = build_container(settings, db)
    view = await c.orchestrator.run("daily_planning", {"mentor_ref": "MEN-001"}, MENTOR)
    assert view.status.value == "completed"
    assert view.ai_status == "generated", view.result.get("ai_meta")
    assert view.result["ai_insights"]["content"]["overview"]
    draft = await c.orchestrator.run(
        "teacher_communication", {"mentor_ref": "MEN-001", "followup_ref": "FU-001", "language": "ta"}, MENTOR
    )
    assert draft.result["facts"]["draft"]["generated_by"] == "ai"
    usage = await c.usage.summary()
    assert any(r["outcome"] == "success" for r in usage["by_model_and_outcome"])

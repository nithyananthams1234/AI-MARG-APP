"""Coach v1.2: mentor analysis + teacher-message material in the observation analysis."""

import httpx
import pytest

import app.coach as coach
from app.config import settings
from app.main import app
from app.schemas import AnalysisContent

pytestmark = pytest.mark.anyio

PASSAGES = [
    {"text": "Think-pair-share increases participation.", "document": "7.pdf",
     "title": "Active Learning", "page": 3, "distance": 0.3},
]

IMPROVEMENT = {
    "area": "Student participation",
    "evidence": "Only 4 of 30 students answered questions.",
    "possible_reason": "Possibly because questions were directed at the whole class.",
    "recommendation": "Introduce think-pair-share [S1] [S5].",
    "teacher_suggestion": "Try a quick think-pair-share after each new idea [S1].",
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "COACH_API_KEY", "k")
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://coach", headers={"X-API-Key": "k"})


def _fake(monkeypatch, content: dict):
    seen = {}
    monkeypatch.setattr(coach, "retrieve_context", lambda q, k=None: list(PASSAGES))

    async def structured(prompt, schema):
        seen["prompt"] = prompt
        return schema.model_validate(content)

    monkeypatch.setattr(coach, "generate_structured", structured)
    return seen


BODY = {"subject": "Science", "grade": "7", "topic": "Plants",
        "observation_notes": "Teacher explained photosynthesis clearly. Only 4 of 30 students answered questions."}


async def test_new_sections_returned_and_teacher_text_has_no_citations(client, monkeypatch):
    seen = _fake(monkeypatch, {
        "summary": "Clear explanation, low participation.",
        "strengths": [{"title": "Clear explanation", "evidence": "explained photosynthesis clearly"}],
        "priority_improvements": [IMPROVEMENT],
        "follow_up_actions": ["Count how many students answer at the next visit."],
        "teacher_response_options": [
            {"type": "agreement", "label": "I will try it", "response": "I will try think-pair-share [S1] tomorrow."},
        ],
    })
    r = await client.post("/api/v1/analyze/observation", json=BODY)
    assert r.status_code == 200, r.text
    body = r.json()
    imp = body["priority_improvements"][0]
    assert imp["teacher_suggestion"] == "Try a quick think-pair-share after each new idea."
    assert "[S1]" in imp["recommendation"] and "[S5]" not in imp["recommendation"]
    assert "[S" not in body["teacher_response_options"][0]["response"]
    assert body["strengths"][0]["title"] == "Clear explanation"
    # Prompt asks for 1-3 priorities, teacher-facing language and contextual options.
    assert "1 to 3 MOST important" in seen["prompt"] and "teacher_response_options" in seen["prompt"]


async def test_more_than_three_priorities_are_capped(client, monkeypatch):
    _fake(monkeypatch, {"summary": "s", "priority_improvements": [IMPROVEMENT] * 5,
                        "strengths": [{"title": "t", "evidence": "e"}] * 4})
    body = (await client.post("/api/v1/analyze/observation", json=BODY)).json()
    assert len(body["priority_improvements"]) == 3 and len(body["strengths"]) == 3


async def test_old_style_output_without_new_sections_still_valid(client, monkeypatch):
    _fake(monkeypatch, {"summary": "Only the original sections."})
    body = (await client.post("/api/v1/analyze/observation", json=BODY)).json()
    assert body["priority_improvements"] == [] and body["teacher_response_options"] == []


def test_schema_asks_model_for_every_section():
    required = AnalysisContent.model_json_schema()["required"]
    for key in ("priority_improvements", "teacher_response_options", "strengths", "follow_up_actions"):
        assert key in required


def test_invalid_option_type_is_rejected_by_validation():
    with pytest.raises(Exception):
        AnalysisContent.model_validate({"summary": "s", "teacher_response_options": [
            {"type": "teacher_replied", "label": "x", "response": "y"}]})

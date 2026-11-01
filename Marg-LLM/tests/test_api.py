"""Classroom Coach API tests with the retriever and LLM replaced by fakes (no model needed)."""

import httpx
import pytest

import app.coach as coach
from app.config import settings
from app.llm import nvidia_client
from app.main import app
from app.schemas import AnalysisContent

pytestmark = pytest.mark.anyio

PASSAGES = [
    {"text": "Use concrete materials such as fraction strips before symbols.", "document": "12.pdf",
     "title": "Teaching Fractions", "page": 4, "distance": 0.3},
    {"text": "Formative assessment checks understanding during the lesson.", "document": "38.pdf",
     "title": "CCE Manual", "page": 26, "distance": 0.35},
]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "COACH_API_KEY", "coach-test-key")
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://coach", headers={"X-API-Key": "coach-test-key"})


@pytest.fixture
def fake_rag(monkeypatch):
    calls = {}

    def retrieve(question, top_k=None):
        calls["query"] = question
        return list(PASSAGES)

    async def answer(prompt):
        calls["prompt"] = prompt
        return "Use fraction strips [S1]. Also see [S9]."

    async def structured(prompt, schema):
        calls["analysis_prompt"] = prompt
        return AnalysisContent(
            summary="Students followed steps without understanding.",
            findings=[{"title": "Procedural teaching", "description": "Rule only", "category": "Pedagogy",
                       "confidence": 0.8, "evidence_reference": "copied the steps"}],
            learning_gaps=[{"title": "Equivalence", "description": "Cannot explain", "severity": "high"}],
            recommendations=[{"title": "Fraction strips", "description": "Hands-on",
                              "rationale": "Concrete first [S1] [S7]", "category": "Pedagogy"}],
        )

    monkeypatch.setattr(coach, "retrieve_context", retrieve)
    monkeypatch.setattr(coach, "generate_answer", answer)
    monkeypatch.setattr(coach, "generate_structured", structured)
    return calls


async def test_requires_api_key(client):
    r = await client.post("/api/v1/chat", json={"question": "How to teach fractions?"}, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


async def test_chat_returns_grounded_answer_with_real_sources(client, fake_rag):
    r = await client.post(
        "/api/v1/chat", json={"question": "How to teach fractions?", "context": {"subject": "Mathematics", "grade": "6"}}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["grounded"] is True
    assert [s["document"] for s in body["sources"]] == ["12.pdf", "38.pdf"]
    assert body["sources"][0]["title"] == "Teaching Fractions" and body["sources"][0]["relevance"] == 0.7
    # Citation to a non-existent source is removed; the valid one is kept.
    assert "[S1]" in body["answer"] and "[S9]" not in body["answer"]
    # Classroom context enriches retrieval and is delimited in the prompt.
    assert "Mathematics" in fake_rag["query"]
    assert "<classroom_context>" in fake_rag["prompt"] and "<question>" in fake_rag["prompt"]


async def test_no_relevant_knowledge_is_reported_honestly(client, monkeypatch):
    monkeypatch.setattr(coach, "retrieve_context", lambda q, k=None: [])

    async def never(prompt):
        raise AssertionError("LLM must not be called without knowledge")

    monkeypatch.setattr(coach, "generate_answer", never)
    r = await client.post("/api/v1/chat", json={"question": "How do I bake a chocolate cake?"})
    assert r.status_code == 200
    assert r.json()["grounded"] is False and r.json()["sources"] == []


async def test_input_validation(client, fake_rag):
    assert (await client.post("/api/v1/chat", json={"question": "hi"})).status_code == 422
    assert (await client.post("/api/v1/chat", json={"question": "x" * 2001})).status_code == 422
    assert (await client.post("/api/v1/chat", json={"question": "valid question", "unexpected": 1})).status_code == 422
    r = await client.post("/api/v1/analyze/observation", json={"subject": "Maths", "observation_notes": "too short"})
    assert r.status_code == 422


async def test_observation_analysis_contract(client, fake_rag):
    r = await client.post(
        "/api/v1/analyze/observation",
        json={"subject": "Mathematics", "grade": "6", "topic": "Fractions",
              "observation_notes": "Teacher wrote the rule; students copied the steps; few could explain why.",
              "existing_findings": ["Limited student talk"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ai_suggested"
    assert body["findings"][0]["confidence"] == 0.8
    assert body["learning_gaps"][0]["severity"] == "high"
    assert "[S7]" not in body["recommendations"][0]["rationale"]
    assert "Limited student talk" in fake_rag["analysis_prompt"]
    assert len(body["sources"]) == 2


async def test_llm_unavailable_returns_503_without_internals(client, monkeypatch):
    monkeypatch.setattr(coach, "retrieve_context", lambda q, k=None: list(PASSAGES))

    async def down(prompt):
        raise nvidia_client.LLMUnavailable("NVIDIA service unavailable")

    monkeypatch.setattr(coach, "generate_answer", down)
    r = await client.post("/api/v1/chat", json={"question": "How to teach fractions?"})
    assert r.status_code == 503
    assert "11434" not in r.text and r.json()["code"] == "llm_unavailable"


async def test_unexpected_errors_do_not_leak(client, monkeypatch):
    def boom(q, k=None):
        raise RuntimeError("secret path D:/internal")

    monkeypatch.setattr(coach, "retrieve_context", boom)
    r = await client.post("/api/v1/chat", json={"question": "How to teach fractions?"})
    assert r.status_code == 500 and "secret" not in r.text


async def test_health_is_public():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://c") as c:
        assert (await c.get("/health")).status_code == 200

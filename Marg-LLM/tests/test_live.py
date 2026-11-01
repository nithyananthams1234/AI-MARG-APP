"""Live tests against the real knowledge base and NVIDIA-hosted model.

Run with:  RUN_LIVE_COACH_TESTS=1 pytest tests/test_live.py
Requires data/chroma_db and NVIDIA_API_KEY configured in .env.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_COACH_TESTS") != "1", reason="live test (set RUN_LIVE_COACH_TESTS=1)"
)


def test_retrieval_relevant_vs_offtopic():
    from app.rag.retriever import retrieve_context

    relevant = retrieve_context("What is formative assessment and how should mentors use it?")
    assert relevant and relevant[0]["distance"] < 0.45
    keys = [((p["title"] or p["document"]).lower(), p["page"]) for p in relevant]
    assert len(keys) == len(set(keys))  # de-duplicated
    assert retrieve_context("How do I bake a chocolate cake?") == []


@pytest.mark.anyio
async def test_live_chat_and_analysis():
    from app.coach import analyse_observation, ask_classroom_coach

    result = await ask_classroom_coach("How can a teacher check understanding during a lesson?")
    assert result["grounded"] and result["answer"].strip() and result["sources"]

    content, sources = await analyse_observation({
        "subject": "Mathematics", "grade": "6", "topic": "Equivalent fractions",
        "observation_notes": "The teacher wrote the rule on the board. Students copied steps. Only 3 of 36 "
                             "could explain why 2/4 equals 1/2. No materials were used.",
        "existing_findings": [],
    })
    assert content.summary and (content.findings or content.learning_gaps or content.recommendations)

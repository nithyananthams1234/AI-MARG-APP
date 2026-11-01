"""Classroom Coach: retrieval-augmented answers and observation analysis."""

from __future__ import annotations

import re

from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.llm.nvidia_client import generate_answer, generate_structured
from app.prompts.templates import analysis_prompt, chat_prompt
from app.rag.retriever import retrieve_context
from app.schemas import AnalysisContent, ClassroomContext, Source

NO_KNOWLEDGE_ANSWER = (
    "I could not find sufficiently relevant guidance in the MARG educational knowledge base "
    "for this question. Please rephrase it or add classroom details (subject, grade, topic)."
)


def _sources(passages: list[dict]) -> list[Source]:
    return [
        Source(
            document=p["document"],
            title=p.get("title"),
            page=p["page"],
            relevance=round(max(0.0, 1.0 - p["distance"]), 3),
            excerpt=p["text"][:280],
        )
        for p in passages
    ]


def _cited_only(answer: str, passages: list[dict]) -> str:
    """Remove citation markers that point to sources that were not provided."""
    valid = {f"S{i}" for i in range(1, len(passages) + 1)}
    return re.sub(r"\[(S\d+)\]", lambda m: m.group(0) if m.group(1) in valid else "", answer)


async def ask_classroom_coach(question: str, context: ClassroomContext | None = None) -> dict:
    ctx = context.model_dump(exclude_none=True) if context else None
    query = question
    if ctx:
        query = " ".join([question] + [str(v) for k, v in ctx.items() if k in ("subject", "grade", "topic")])

    passages = await run_in_threadpool(retrieve_context, query, settings.RETRIEVAL_TOP_K)
    if not passages:
        return {"answer": NO_KNOWLEDGE_ANSWER, "sources": [], "grounded": False}

    answer = await generate_answer(chat_prompt(question, passages, ctx))
    return {
        "answer": _cited_only(answer, passages),
        "sources": _sources(passages),
        "grounded": True,
    }


async def analyse_observation(req: dict) -> tuple[AnalysisContent, list[Source]]:
    query = " ".join(filter(None, [req.get("subject"), req.get("grade"), req.get("topic"), req["observation_notes"][:600]]))
    passages = await run_in_threadpool(retrieve_context, query, settings.RETRIEVAL_TOP_K)
    content = await generate_structured(analysis_prompt(req, passages), AnalysisContent)

    # Drop citations to sources that do not exist.
    for rec in content.recommendations:
        rec.rationale = _cited_only(rec.rationale, passages)
    for imp in content.priority_improvements:
        imp.recommendation = _cited_only(imp.recommendation, passages)
        # Teacher-facing text never carries citation markers.
        imp.teacher_suggestion = _no_citations(imp.teacher_suggestion)
    for opt in content.teacher_response_options:
        opt.response = _no_citations(opt.response)
    return content, _sources(passages)


def _no_citations(text: str) -> str:
    return re.sub(r"\s*\[S\d+\]", "", text).strip()

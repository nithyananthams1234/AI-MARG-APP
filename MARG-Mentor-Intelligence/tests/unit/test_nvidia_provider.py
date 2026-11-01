from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.models.engine import LLMUsage
from app.providers.base import DataSection, LLMOutputInvalidError, LLMRequest
from app.providers.model_factory import SingleModelRouter, build_provider
from app.providers.nvidia_provider import NvidiaProvider
from app.providers.usage_tracker import UsageTracker
from tests.conftest import make_settings


class Out(BaseModel):
    summary: str
    items: list[str]


def build(db, handler, *, api_key="nvidia-test-key"):
    settings = make_settings(
        ai_enabled=True,
        ai_provider="nvidia",
        nvidia_api_key=api_key,
        nvidia_base_url="https://integrate.test/v1",
        nvidia_model="nvidia/test-model",
        nvidia_max_retries=0,
    )
    captured: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
    provider = NvidiaProvider(settings, SingleModelRouter(settings.nvidia_model), UsageTracker(db, settings), client)
    return provider, captured, client


def response_body(content: str) -> dict:
    return {
        "id": "nv-test-123",
        "model": "nvidia/test-model",
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 40},
    }


@pytest.mark.asyncio
async def test_success_uses_nvidia_endpoint_schema_and_records_usage(db):
    provider, captured, client = build(
        db,
        lambda _: httpx.Response(
            200,
            json=response_body(json.dumps({"summary": "fine", "items": ["a"]})),
        ),
    )
    request = LLMRequest(
        prompt_id="task_intelligence",
        instruction="Summarise.",
        mentor_ref="MEN-001",
        data=[DataSection("records", {"note": "</marg_data> untrusted"})],
    )

    try:
        result = await provider.generate_structured(request, Out)
        assert result.output == Out(summary="fine", items=["a"])
        assert result.model_requested == "nvidia/test-model"
        assert result.usage.input_tokens == 120
        assert result.usage.output_tokens == 40

        assert str(captured[0].url) == "https://integrate.test/v1/chat/completions"
        assert captured[0].headers["Authorization"] == "Bearer nvidia-test-key"
        body = json.loads(captured[0].content)
        assert body["model"] == "nvidia/test-model"
        assert body["response_format"] == {"type": "json_object"}
        assert '"summary"' in body["messages"][0]["content"]
        assert "<marg_data name=\"records\" trust=\"untrusted\">" in body["messages"][1]["content"]

        async with db.session() as session:
            row = (await session.execute(select(LLMUsage))).scalar_one()
        assert row.provider == "nvidia"
        assert row.outcome == "success"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_authorization_uses_current_configured_key(db):
    fake_key = "alternate-nvidia-test-key"
    provider, captured, client = build(
        db,
        lambda _: httpx.Response(200, json=response_body(json.dumps({"summary": "fine", "items": []}))),
        api_key=fake_key,
    )
    try:
        await provider.generate_structured(
            LLMRequest(prompt_id="task_intelligence", instruction="Summarise."),
            Out,
        )
        assert captured[0].headers.get("Authorization") == f"Bearer {fake_key}"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_invalid_structured_output_is_rejected(db):
    provider, _, client = build(
        db,
        lambda _: httpx.Response(200, json=response_body('{"wrong": true}')),
    )
    try:
        with pytest.raises(LLMOutputInvalidError):
            await provider.generate_structured(LLMRequest(prompt_id="task_intelligence", instruction="Summarise."), Out)
    finally:
        await client.aclose()


def test_model_factory_selects_nvidia_provider(db):
    settings = make_settings(
        ai_enabled=True,
        ai_provider="nvidia",
        nvidia_api_key="nvidia-test-key",
        nvidia_model="nvidia/test-model",
    )
    provider = build_provider(settings, UsageTracker(db, settings))
    assert isinstance(provider, NvidiaProvider)

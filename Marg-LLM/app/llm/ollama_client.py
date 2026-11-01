"""Ollama client for the local Qwen model (model unchanged, configurable)."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
import ollama
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.prompts.templates import SYSTEM_PROMPT

logger = logging.getLogger("coach.llm")


class LLMUnavailable(RuntimeError):
    """The model server could not be reached or timed out."""


class LLMInvalidOutput(RuntimeError):
    """The model produced output that failed validation."""


def _client() -> ollama.AsyncClient:
    return ollama.AsyncClient(host=settings.OLLAMA_BASE_URL, timeout=settings.OLLAMA_TIMEOUT_SECONDS)


async def _chat(messages: list[dict], *, num_predict: int, fmt: dict | None = None) -> str:
    options = {
        "temperature": settings.OLLAMA_TEMPERATURE,
        "num_ctx": settings.OLLAMA_NUM_CTX,
        "num_predict": num_predict,
    }
    last_exc: Exception | None = None
    for attempt in range(2):  # one retry for transient connection errors
        try:
            response = await _client().chat(
                model=settings.OLLAMA_MODEL,
                messages=messages,
                options=options,
                format=fmt,
            )
            return response.message.content or ""
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException, ConnectionError) as exc:
            last_exc = exc
            logger.warning("Ollama call failed (attempt %s): %s", attempt + 1, type(exc).__name__)
            await asyncio.sleep(1)
        except ollama.ResponseError as exc:
            # e.g. model not pulled / server error: not transient
            raise LLMUnavailable(f"Model server error: {exc.error}") from exc
    raise LLMUnavailable("The local language model is not reachable") from last_exc


async def generate_answer(user_prompt: str) -> str:
    return (
        await _chat(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
            num_predict=settings.OLLAMA_MAX_ANSWER_TOKENS,
        )
    ).strip()


async def generate_structured(user_prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Schema-constrained JSON generation with validation and one repair attempt."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    json_schema = schema.model_json_schema()
    for attempt in range(2):
        raw = await _chat(messages, num_predict=settings.OLLAMA_MAX_ANALYSIS_TOKENS, fmt=json_schema)
        try:
            return schema.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Invalid structured output (attempt %s): %s", attempt + 1, str(exc)[:300])
            messages += [
                {"role": "assistant", "content": raw[:4000]},
                {
                    "role": "user",
                    "content": "That output was not valid for the required JSON schema. "
                    f"Validation error: {str(exc)[:500]}. Return corrected JSON only.",
                },
            ]
    raise LLMInvalidOutput("The model did not return a valid analysis")


async def model_available() -> bool:
    try:
        tags = await _client().list()
        names = {m.model for m in tags.models}
        return settings.OLLAMA_MODEL in names or f"{settings.OLLAMA_MODEL}:latest" in names
    except Exception:  # noqa: BLE001
        return False

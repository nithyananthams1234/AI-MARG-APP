"""NVIDIA-hosted LLM client for grounded answers and structured analysis."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.prompts.templates import SYSTEM_PROMPT

logger = logging.getLogger("coach.llm")


class LLMUnavailable(RuntimeError):
    """The hosted model service could not be reached or rejected the request."""


class LLMInvalidOutput(RuntimeError):
    """The model produced output that failed validation."""


def _headers() -> dict[str, str]:
    if settings.NVIDIA_API_KEY is None:
        raise LLMUnavailable("The NVIDIA API key is not configured.")
    api_key = settings.NVIDIA_API_KEY.get_secret_value().strip()
    if not api_key:
        raise LLMUnavailable("The NVIDIA API key is not configured.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def _chat(messages: list[dict], *, max_tokens: int, json_schema: dict | None = None) -> str:
    headers = _headers()
    payload = {
        "model": settings.NVIDIA_MODEL,
        "messages": messages,
        "temperature": settings.NVIDIA_TEMPERATURE,
        "max_tokens": max_tokens,
    }
    if json_schema is not None:
        payload["response_format"] = {"type": "json_object"}

    endpoint = f"{settings.NVIDIA_BASE_URL.rstrip('/')}/chat/completions"
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=settings.NVIDIA_TIMEOUT_SECONDS) as client:
        for attempt in range(2):
            try:
                response = await client.post(endpoint, json=payload, headers=headers)
            except httpx.RequestError as exc:
                last_exc = exc
                logger.warning("NVIDIA API call failed (attempt %s): %s", attempt + 1, type(exc).__name__)
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                raise LLMUnavailable("The NVIDIA-hosted language model is not reachable.") from last_exc

            if response.status_code == 200:
                try:
                    body = response.json()
                except ValueError as exc:
                    raise LLMInvalidOutput("NVIDIA returned an invalid response.") from exc
                choices = body.get("choices") if isinstance(body, dict) else None
                if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                    raise LLMInvalidOutput("NVIDIA returned no completion choices.")
                choice = choices[0]
                if choice.get("finish_reason") == "length":
                    raise LLMInvalidOutput("NVIDIA response was truncated at max_tokens.")
                message = choice.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str) or not content.strip():
                    raise LLMInvalidOutput("NVIDIA returned empty output.")
                return content

            if response.status_code in (401, 403):
                raise LLMUnavailable(f"NVIDIA authentication failed (HTTP {response.status_code}).")
            if response.status_code == 429 or response.status_code >= 500:
                logger.warning("NVIDIA API returned HTTP %s (attempt %s)", response.status_code, attempt + 1)
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                raise LLMUnavailable(f"NVIDIA API temporarily unavailable (HTTP {response.status_code}).")
            raise LLMUnavailable(f"NVIDIA rejected the request (HTTP {response.status_code}).")

    raise LLMUnavailable("The NVIDIA-hosted language model is not reachable.") from last_exc


async def generate_answer(user_prompt: str) -> str:
    return (
        await _chat(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
            max_tokens=settings.NVIDIA_MAX_ANSWER_TOKENS,
        )
    ).strip()


async def generate_structured(user_prompt: str, schema: type[BaseModel]) -> BaseModel:
    json_schema = schema.model_json_schema()
    system = (
        f"{SYSTEM_PROMPT}\n\nReturn only a JSON object matching this JSON Schema:\n"
        f"{json.dumps(json_schema, ensure_ascii=False)}"
    )
    raw = await _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
        max_tokens=settings.NVIDIA_MAX_ANALYSIS_TOKENS,
        json_schema=json_schema,
    )
    try:
        return schema.model_validate_json(raw)
    except (ValueError, ValidationError) as exc:
        logger.warning("NVIDIA returned output that failed schema validation: %s", str(exc)[:300])
        raise LLMInvalidOutput("NVIDIA output did not match the required analysis schema.") from exc


async def model_available() -> bool:
    if settings.NVIDIA_API_KEY is None or not settings.NVIDIA_API_KEY.get_secret_value().strip():
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{settings.NVIDIA_BASE_URL.rstrip('/')}/models",
                headers=_headers(),
            )
        if response.status_code != 200:
            return False
        body = response.json()
        if not isinstance(body, dict):
            return False
        models = body.get("data")
        if not isinstance(models, list):
            return False
        return any(
            model.get("id") == settings.NVIDIA_MODEL
            for model in models
            if isinstance(model, dict)
        )
    except (httpx.RequestError, ValueError):
        return False

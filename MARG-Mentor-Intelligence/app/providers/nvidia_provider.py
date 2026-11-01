"""NVIDIA-hosted LLM provider using the OpenAI-compatible chat completions API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.prompts.registry import DEFAULT_VERSION, system_prompt
from app.providers.base import (
    LLMOutputInvalidError,
    LLMPermanentError,
    LLMRefusalError,
    LLMRequest,
    LLMResult,
    LLMTransientError,
    LLMTruncatedError,
    LLMUsageInfo,
    T,
    render_data_sections,
)
from app.providers.model_factory import ModelRouter
from app.providers.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)


class NvidiaProvider:
    name = "nvidia"

    def __init__(
        self,
        settings: Settings,
        router: ModelRouter,
        usage: UsageTracker,
        client: httpx.AsyncClient | None = None,
    ):
        if settings.nvidia_api_key is None or not settings.nvidia_api_key.get_secret_value().strip():
            raise LLMPermanentError("NVIDIA API key is not configured")
        self._settings = settings
        self._router = router
        self._usage = usage
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self._settings.nvidia_timeout_seconds)

    def _headers(self) -> dict[str, str]:
        assert self._settings.nvidia_api_key is not None
        api_key = self._settings.nvidia_api_key.get_secret_value().strip()
        if not api_key:
            raise LLMPermanentError("NVIDIA API key is not configured")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, request: LLMRequest, model: str, output_model: type[BaseModel]) -> dict[str, Any]:
        user_text = request.instruction
        if request.data:
            user_text = f"{render_data_sections(request.data)}\n\n{request.instruction}"
        schema = json.dumps(output_model.model_json_schema(), ensure_ascii=False)
        system = (
            f"{system_prompt(request.prompt_id)}\n\n"
            "Return only a JSON object that conforms to this JSON Schema:\n"
            f"{schema}"
        )
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            "max_tokens": request.max_output_tokens or self._settings.nvidia_max_output_tokens,
            "response_format": {"type": "json_object"},
        }

    async def generate_structured(self, request: LLMRequest, output_model: type[T]) -> LLMResult[T]:
        await self._usage.check_budget(request.mentor_ref)
        model = self._router.select_model(request.complexity)
        endpoint = f"{self._settings.nvidia_base_url.rstrip('/')}/chat/completions"
        started = time.perf_counter()
        client = self._get_client()
        owns_client = self._client is None
        data: dict[str, Any] | None = None

        try:
            for attempt in range(self._settings.nvidia_max_retries + 1):
                try:
                    response = await client.post(endpoint, json=self._payload(request, model, output_model),
                                                 headers=self._headers())
                except httpx.RequestError as exc:
                    if attempt < self._settings.nvidia_max_retries:
                        await asyncio.sleep(min(2**attempt, 8))
                        continue
                    await self._record(request, model, None, "transient_error", started)
                    raise LLMTransientError("NVIDIA API connection error or timeout") from exc

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except ValueError as exc:
                        await self._record(request, model, None, "invalid_output", started)
                        raise LLMOutputInvalidError("NVIDIA returned an invalid response") from exc
                    if not isinstance(data, dict):
                        await self._record(request, model, None, "invalid_output", started)
                        raise LLMOutputInvalidError("NVIDIA returned an invalid response")
                    break

                if response.status_code in (401, 403):
                    await self._record(request, model, None, "rejected", started)
                    raise LLMPermanentError(f"NVIDIA authentication rejected (HTTP {response.status_code})")

                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self._settings.nvidia_max_retries:
                        delay = min(2**attempt, 8)
                        retry_after = response.headers.get("retry-after")
                        if retry_after:
                            try:
                                delay = min(float(retry_after), 30)
                            except ValueError:
                                pass
                        await asyncio.sleep(delay)
                        continue
                    outcome = "rate_limited" if response.status_code == 429 else "transient_error"
                    await self._record(request, model, None, outcome, started)
                    raise LLMTransientError(f"NVIDIA API temporarily unavailable (HTTP {response.status_code})")

                await self._record(request, model, None, "rejected", started)
                raise LLMPermanentError(f"NVIDIA rejected the request (HTTP {response.status_code})")

            if data is None:
                await self._record(request, model, None, "transient_error", started)
                raise LLMTransientError("NVIDIA request did not return a response")

            choices = data.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                await self._record(request, model, data, "invalid_output", started)
                raise LLMOutputInvalidError("NVIDIA returned no completion choices")

            choice = choices[0]
            finish_reason = choice.get("finish_reason")
            if finish_reason == "length":
                await self._record(request, model, data, "truncated", started)
                raise LLMTruncatedError("NVIDIA output was truncated at max_tokens")
            if finish_reason in {"content_filter", "refusal"}:
                await self._record(request, model, data, "refused", started)
                raise LLMRefusalError("NVIDIA declined the request", finish_reason)

            content = (choice.get("message") or {}).get("content")
            if not isinstance(content, str) or not content.strip():
                await self._record(request, model, data, "invalid_output", started)
                raise LLMOutputInvalidError("NVIDIA returned empty output")
            try:
                output = output_model.model_validate_json(content.strip())
            except ValidationError as exc:
                await self._record(request, model, data, "invalid_output", started)
                raise LLMOutputInvalidError("NVIDIA output failed schema validation") from exc

            latency = await self._record(request, model, data, "success", started)
            usage = self._usage_info(data)
            return LLMResult(
                output=output,
                model_requested=model,
                model_served=data.get("model") or model,
                stop_reason=finish_reason,
                usage=usage,
                provider_request_id=data.get("id"),
                latency_ms=latency,
                prompt_version=DEFAULT_VERSION,
            )
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _usage_info(data: dict[str, Any] | None) -> LLMUsageInfo:
        usage = (data or {}).get("usage")
        if not isinstance(usage, dict):
            usage = {}
        details = usage.get("prompt_tokens_details")
        if not isinstance(details, dict):
            details = {}
        return LLMUsageInfo(
            input_tokens=usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0,
            output_tokens=usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0,
            cache_read_tokens=details.get("cached_tokens", 0) or 0,
        )

    async def _record(
        self,
        request: LLMRequest,
        model: str,
        data: dict[str, Any] | None,
        outcome: str,
        started: float,
    ) -> int:
        latency_ms = int((time.perf_counter() - started) * 1000)
        choices = (data or {}).get("choices") or []
        await self._usage.record(
            provider=self.name,
            model_requested=model,
            model_served=(data or {}).get("model") or model,
            prompt_id=request.prompt_id,
            prompt_version=DEFAULT_VERSION,
            usage=self._usage_info(data),
            stop_reason=choices[0].get("finish_reason") if choices else None,
            outcome=outcome,
            latency_ms=latency_ms,
            provider_request_id=(data or {}).get("id"),
            mentor_ref=request.mentor_ref,
            execution_id=request.execution_id,
        )
        return latency_ms

"""Claude provider using the official Anthropic Python SDK.

Responsibilities: build the request, constrain the output with structured outputs
(``output_config.format`` built by the SDK's ``transform_schema`` from the Pydantic model), check the
stop reason *before* parsing (so refusals and truncation are reported correctly), validate the JSON
with Pydantic, map SDK errors to vendor-neutral errors and record token usage. It contains no
business rules. Transport retries (429/5xx/connection, honouring ``retry-after``) are done by the SDK.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic
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

REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        settings: Settings,
        router: ModelRouter,
        usage: UsageTracker,
        client: anthropic.AsyncAnthropic | None = None,
    ):
        if settings.anthropic_api_key is None:
            raise LLMPermanentError("Anthropic API key is not configured")
        self._settings = settings
        self._router = router
        self._usage = usage
        self._client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.anthropic_timeout_seconds,
            max_retries=settings.anthropic_max_retries,
        )

    def _build_kwargs(self, request: LLMRequest, model: str, output_model: type[BaseModel]) -> dict[str, Any]:
        user_text = request.instruction
        if request.data:
            user_text = f"{render_data_sections(request.data)}\n\n{request.instruction}"
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_output_tokens or self._settings.anthropic_max_output_tokens,
            "system": [
                {
                    "type": "text",
                    "text": system_prompt(request.prompt_id),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": user_text}],
        }
        output_config: dict[str, Any] = {
            "format": {"type": "json_schema", "schema": anthropic.transform_schema(output_model)}
        }
        if self._settings.anthropic_effort:
            output_config["effort"] = self._settings.anthropic_effort
        kwargs["output_config"] = output_config
        return kwargs

    async def generate_structured(self, request: LLMRequest, output_model: type[T]) -> LLMResult[T]:
        await self._usage.check_budget(request.mentor_ref)
        model = self._router.select_model(request.complexity)
        kwargs = self._build_kwargs(request, model, output_model)
        use_fallback = self._settings.anthropic_refusal_fallback == "default"

        started = time.perf_counter()
        try:
            if use_fallback:
                response = await self._client.beta.messages.create(
                    **kwargs, betas=[REFUSAL_FALLBACK_BETA], fallbacks="default"
                )
            else:
                response = await self._client.messages.create(**kwargs)
        except anthropic.APIConnectionError as exc:  # includes APITimeoutError
            await self._record(request, model, None, "transient_error", started)
            raise LLMTransientError("Claude API connection error or timeout") from exc
        except anthropic.RateLimitError as exc:
            await self._record(request, model, None, "rate_limited", started)
            raise LLMTransientError("Claude API rate limit reached") from exc
        except anthropic.APIStatusError as exc:
            outcome = "transient_error" if exc.status_code >= 500 else "rejected"
            await self._record(request, model, None, outcome, started)
            if exc.status_code >= 500:
                raise LLMTransientError(f"Claude API unavailable (HTTP {exc.status_code})") from exc
            raise LLMPermanentError(f"Claude API rejected the request (HTTP {exc.status_code})") from exc

        stop_reason = getattr(response, "stop_reason", None)
        usage = self._usage_info(response)
        request_id = getattr(response, "_request_id", None)
        model_served = getattr(response, "model", None)

        if stop_reason == "refusal":
            await self._record(request, model, response, "refused", started)
            details = getattr(response, "stop_details", None)
            raise LLMRefusalError("Claude declined the request", getattr(details, "category", None))
        if stop_reason == "max_tokens":
            await self._record(request, model, response, "truncated", started)
            raise LLMTruncatedError("Claude output was truncated at max_tokens")

        text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
        if not text:
            await self._record(request, model, response, "invalid_output", started)
            raise LLMOutputInvalidError("Claude returned no structured output")
        try:  # never trust model output without our own validation
            output = output_model.model_validate_json(text)
        except ValidationError as exc:
            await self._record(request, model, response, "invalid_output", started)
            raise LLMOutputInvalidError("Claude output failed validation") from exc

        if self._fallback_used(response):
            logger.warning(
                "llm_refusal_fallback_used",
                extra={"prompt_id": request.prompt_id, "model_requested": model, "model_served": model_served},
            )
        latency = await self._record(request, model, response, "success", started)
        logger.info(
            "llm_call_succeeded",
            extra={
                "prompt_id": request.prompt_id,
                "model": model_served,
                "output_tokens": usage.output_tokens,
            },
        )
        return LLMResult(
            output=output,
            model_requested=model,
            model_served=model_served,
            stop_reason=stop_reason,
            usage=usage,
            provider_request_id=request_id,
            latency_ms=latency,
            prompt_version=DEFAULT_VERSION,
        )

    @staticmethod
    def _fallback_used(response: Any) -> bool:
        """True when a fallback model served the message (fallback_message iteration)."""
        iterations = getattr(getattr(response, "usage", None), "iterations", None) or []
        return any(
            (it.get("type") if isinstance(it, dict) else getattr(it, "type", None)) == "fallback_message"
            for it in iterations
        )

    @staticmethod
    def _usage_info(response: Any) -> LLMUsageInfo:
        usage = getattr(response, "usage", None)
        if usage is None:
            return LLMUsageInfo()
        # With refusal fallbacks the top-level usage covers only the attempt that
        # produced the message; usage.iterations lists every (billed) attempt.
        iterations = getattr(usage, "iterations", None)
        if iterations:
            def total(field: str) -> int:
                return sum(
                    (it.get(field) if isinstance(it, dict) else getattr(it, field, 0)) or 0 for it in iterations
                )

            return LLMUsageInfo(
                input_tokens=total("input_tokens"),
                output_tokens=total("output_tokens"),
                cache_read_tokens=total("cache_read_input_tokens"),
                cache_creation_tokens=total("cache_creation_input_tokens"),
            )
        return LLMUsageInfo(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )

    async def _record(
        self, request: LLMRequest, model: str, response: Any, outcome: str, started: float
    ) -> int:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await self._usage.record(
            provider=self.name,
            model_requested=model,
            model_served=getattr(response, "model", None) if response is not None else None,
            prompt_id=request.prompt_id,
            prompt_version=DEFAULT_VERSION,
            usage=self._usage_info(response) if response is not None else LLMUsageInfo(),
            stop_reason=getattr(response, "stop_reason", None) if response is not None else None,
            outcome=outcome,
            latency_ms=latency_ms,
            provider_request_id=getattr(response, "_request_id", None) if response is not None else None,
            mentor_ref=request.mentor_ref,
            execution_id=request.execution_id,
        )
        return latency_ms


"""OpenRouter provider implementing the vendor-neutral LLMProvider Protocol.

Responsibilities:
- Build OpenAI-compatible chat completion requests for OpenRouter.
- Request structured JSON output conforming to the Pydantic schema.
- Validate responses against Pydantic models.
- Map HTTP/network errors to vendor-neutral LLM errors.
- Retry rate limits and transient server/network errors.
- Record token usage, latency, model, and outcomes via UsageTracker.
- Never log sensitive API keys or authorization headers.
"""

from __future__ import annotations

import asyncio
import logging
import time
import json
import httpx
import pytest
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


class OpenRouterProvider:
    name = "openrouter"

    def __init__(
        self,
        settings: Settings,
        router: ModelRouter,
        usage: UsageTracker,
        client: httpx.AsyncClient | None = None,
    ):
        if (
            settings.openrouter_api_key is None
            or not settings.openrouter_api_key.get_secret_value().strip()
        ):
            raise LLMPermanentError(
                "OpenRouter API key is not configured"
            )

        self._settings = settings
        self._router = router
        self._usage = usage
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client

        return httpx.AsyncClient(
            timeout=self._settings.openrouter_timeout_seconds
        )

    def _build_headers(self) -> dict[str, str]:
        assert self._settings.openrouter_api_key is not None

        return {
            "Authorization": (
                "Bearer "
                + self._settings.openrouter_api_key.get_secret_value()
            ),
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AI-MARG",
            "X-Title": "MARG Mentor Intelligence",
        }

    def _build_payload(
        self,
        request: LLMRequest,
        model: str,
        output_model: type[BaseModel],
        use_json_schema: bool = True,
    ) -> dict[str, Any]:

        user_text = request.instruction

        if request.data:
            user_text = (
                f"{render_data_sections(request.data)}"
                f"\n\n{request.instruction}"
            )

        messages = [
            {
                "role": "system",
                "content": system_prompt(request.prompt_id),
            },
            {
                "role": "user",
                "content": user_text,
            },
        ]

        max_tokens = request.max_output_tokens or getattr(
            self._settings,
            "openrouter_max_output_tokens",
            16000,
        )

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        # Optional OpenRouter fallback models.
        fallback_models = getattr(
            self._settings,
            "openrouter_fallback_models",
            "",
        )

        if fallback_models:
            fallbacks = [
                item.strip()
                for item in fallback_models.split(",")
                if item.strip() and item.strip() != model
            ]

            if fallbacks:
                payload["models"] = [model] + fallbacks

        if use_json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_model.__name__,
                    "strict": True,
                    "schema": output_model.model_json_schema(),
                },
            }
        else:
            payload["response_format"] = {
                "type": "json_object"
            }

        return payload

    @staticmethod
    def _clean_markdown_json(text: str) -> str:
        """Remove Markdown code fences surrounding JSON."""

        cleaned = text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        return cleaned

    async def generate_structured(
        self,
        request: LLMRequest,
        output_model: type[T],
    ) -> LLMResult[T]:

        await self._usage.check_budget(request.mentor_ref)

        model = self._router.select_model(request.complexity)

        endpoint = (
            f"{self._settings.openrouter_base_url.rstrip('/')}"
            "/chat/completions"
        )

        headers = self._build_headers()

        started = time.perf_counter()

        client = self._get_client()
        owns_client = self._client is None

        use_json_schema = True
        max_retries = self._settings.openrouter_max_retries

        response_data: dict[str, Any] | None = None
        last_error_status: int | None = None
        resp: httpx.Response | None = None

        try:
            # Network retries and JSON-schema fallback are tracked separately.
            # Switching JSON formats does not consume a retry.
            attempt = 0

            while attempt <= max_retries:

                payload = self._build_payload(
                    request,
                    model,
                    output_model,
                    use_json_schema=use_json_schema,
                )

                try:
                    resp = await client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                    )

                except (
                    httpx.ConnectError,
                    httpx.ReadTimeout,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                ) as exc:

                    if attempt < max_retries:
                        delay = min(2 ** attempt, 8)

                        logger.warning(
                            "openrouter_network_error_retry",
                            extra={
                                "attempt": attempt + 1,
                                "delay": delay,
                            },
                        )

                        attempt += 1
                        await asyncio.sleep(delay)
                        continue

                    await self._record(
                        request,
                        model,
                        None,
                        "transient_error",
                        started,
                    )

                    raise LLMTransientError(
                        "OpenRouter API connection error or timeout"
                    ) from exc

                status = resp.status_code
                last_error_status = status

                # Successful HTTP response.
                if status == 200:
                    try:
                        response_data = resp.json()

                    except ValueError as exc:
                        await self._record(
                            request,
                            model,
                            None,
                            "invalid_output",
                            started,
                        )

                        raise LLMOutputInvalidError(
                            "OpenRouter returned an unparseable HTTP 200 response"
                        ) from exc

                    break

                # Authentication errors are permanent.
                if status in (401, 403):
                    await self._record(
                        request,
                        model,
                        None,
                        "rejected",
                        started,
                    )

                    raise LLMPermanentError(
                        f"OpenRouter authentication rejected "
                        f"(HTTP {status})"
                    )

                # Retry rate limits and server errors.
                if status == 429 or status >= 500:

                    if attempt < max_retries:
                        delay = min(2 ** attempt, 8)

                        if status == 429:
                            retry_after = resp.headers.get(
                                "retry-after"
                            )

                            if retry_after:
                                try:
                                    delay = min(
                                        float(retry_after),
                                        30,
                                    )
                                except ValueError:
                                    pass

                        logger.warning(
                            "openrouter_transient_error_retry",
                            extra={
                                "attempt": attempt + 1,
                                "status": status,
                                "delay": delay,
                            },
                        )

                        attempt += 1
                        await asyncio.sleep(delay)
                        continue

                    outcome = (
                        "rate_limited"
                        if status == 429
                        else "transient_error"
                    )

                    await self._record(
                        request,
                        model,
                        None,
                        outcome,
                        started,
                    )

                    raise LLMTransientError(
                        "OpenRouter temporarily unavailable "
                        f"(HTTP {status})"
                    )

                # If strict JSON Schema is unsupported, retry once
                # using JSON object mode without consuming a retry.
                if status == 400 and use_json_schema:

                    error_text = resp.text.lower()

                    schema_error = any(
                        marker in error_text
                        for marker in (
                            "schema",
                            "response_format",
                            "json_schema",
                        )
                    )

                    if schema_error:
                        use_json_schema = False

                        logger.warning(
                            "openrouter_schema_mode_unsupported_"
                            "falling_back_to_json_object"
                        )

                        continue

                # Other client errors are permanent.
                await self._record(
                    request,
                    model,
                    None,
                    "rejected",
                    started,
                )

                raise LLMPermanentError(
                    f"OpenRouter rejected the request "
                    f"(HTTP {status})"
                )

            if response_data is None:
                await self._record(
                    request,
                    model,
                    None,
                    "transient_error",
                    started,
                )

                raise LLMTransientError(
                    "OpenRouter request failed "
                    f"(HTTP {last_error_status})"
                )

            # Extract response choices.
            choices = response_data.get("choices") or []

            if not choices:
                await self._record(
                    request,
                    model,
                    response_data,
                    "invalid_output",
                    started,
                )

                raise LLMOutputInvalidError(
                    "OpenRouter returned an empty choices list"
                )

            choice = choices[0]

            finish_reason = choice.get("finish_reason")

            model_served = (
                response_data.get("model") or model
            )

            request_id = (
                response_data.get("id")
                or (
                    resp.headers.get("x-request-id")
                    if resp is not None
                    else None
                )
            )

            usage_info = self._usage_info(response_data)

            # Handle truncated responses.
            if finish_reason == "length":
                await self._record(
                    request,
                    model,
                    response_data,
                    "truncated",
                    started,
                )

                raise LLMTruncatedError(
                    "OpenRouter output was truncated at max_tokens"
                )

            # Handle refusal responses.
            if finish_reason in (
                "content_filter",
                "refusal",
            ):
                await self._record(
                    request,
                    model,
                    response_data,
                    "refused",
                    started,
                )

                raise LLMRefusalError(
                    "OpenRouter declined the request",
                    finish_reason,
                )

            message = choice.get("message") or {}
            raw_text = message.get("content")

            if (
                not isinstance(raw_text, str)
                or not raw_text.strip()
            ):
                await self._record(
                    request,
                    model,
                    response_data,
                    "invalid_output",
                    started,
                )

                raise LLMOutputInvalidError(
                    "OpenRouter returned empty or invalid message content"
                )

            cleaned = self._clean_markdown_json(raw_text)

            # Validate generated JSON against the Pydantic model.
            try:
                output = output_model.model_validate_json(
                    cleaned
                )

            except ValidationError as exc:
                await self._record(
                    request,
                    model,
                    response_data,
                    "invalid_output",
                    started,
                )

                raise LLMOutputInvalidError(
                    f"OpenRouter output failed schema validation: {exc}"
                ) from exc

            # Record successful usage.
            latency = await self._record(
                request,
                model,
                response_data,
                "success",
                started,
            )

            logger.info(
                "openrouter_call_succeeded",
                extra={
                    "prompt_id": request.prompt_id,
                    "model": model_served,
                    "output_tokens": usage_info.output_tokens,
                },
            )

            return LLMResult(
                output=output,
                model_requested=model,
                model_served=model_served,
                stop_reason=finish_reason,
                usage=usage_info,
                provider_request_id=request_id,
                latency_ms=latency,
                prompt_version=DEFAULT_VERSION,
            )

        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _usage_info(
        data: dict[str, Any] | None,
    ) -> LLMUsageInfo:

        if not data:
            return LLMUsageInfo()

        usage = data.get("usage") or {}

        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0

        details = usage.get("prompt_tokens_details") or {}

        cached_tokens = details.get("cached_tokens", 0) or 0

        return LLMUsageInfo(
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            cache_read_tokens=cached_tokens,
            cache_creation_tokens=0,
        )

    async def _record(
        self,
        request: LLMRequest,
        model_requested: str,
        response_data: dict[str, Any] | None,
        outcome: str,
        started: float,
    ) -> int:

        latency_ms = int(
            (time.perf_counter() - started) * 1000
        )

        usage = self._usage_info(response_data)

        model_served = (
            response_data.get("model")
            if response_data
            else None
        ) or model_requested

        stop_reason = None

        if response_data and response_data.get("choices"):
            stop_reason = (
                response_data["choices"][0].get("finish_reason")
            )

        request_id = (
            response_data.get("id")
            if response_data
            else None
        )

        await self._usage.record(
            provider=self.name,
            model_requested=model_requested,
            model_served=model_served,
            prompt_id=request.prompt_id,
            prompt_version=DEFAULT_VERSION,
            usage=usage,
            stop_reason=stop_reason,
            outcome=outcome,
            latency_ms=latency_ms,
            provider_request_id=request_id,
            mentor_ref=request.mentor_ref,
            execution_id=request.execution_id,
        )

        return latency_ms

@pytest.mark.asyncio
async def test_json_schema_fallback_works_with_zero_retries(db):
    """Schema fallback must work without consuming a network retry."""
    calls = []

    def handler(request: httpx.Request):
        payload = json.loads(request.content)
        calls.append(payload)

        if len(calls) == 1:
            assert payload["response_format"]["type"] == "json_schema"
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Unsupported response_format json_schema"
                    }
                },
            )

        assert payload["response_format"]["type"] == "json_object"

        return httpx.Response(
            200,
            json=response_body(
                json.dumps({
                    "summary": "Fallback succeeded",
                    "items": ["First", "Second"],
                })
            ),
        )

    provider, captured, client = build(
        db,
        handler,
        openrouter_max_retries=0,
    )

    try:
        result = await provider.generate_structured(REQ, Out)

        assert result.output.summary == "Fallback succeeded"
        assert result.output.items == ["First", "Second"]
        assert len(calls) == 2
        assert len(captured) == 2

    finally:
        await client.aclose()

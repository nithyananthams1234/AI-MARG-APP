"""Model routing and provider construction.

The router interface supports configurable LLM providers and models.
Complexity-based routing can be added later without changing agents.
"""

from __future__ import annotations

from typing import Protocol

from app.config import Settings
from app.providers.base import ComplexityHint, LLMDisabledError, LLMProvider, LLMRequest, LLMResult, T
from app.providers.usage_tracker import UsageTracker


class ModelRouter(Protocol):
    def select_model(self, hint: ComplexityHint) -> str: ...


class SingleModelRouter:
    def __init__(self, model: str):
        if not model.strip():
            raise ValueError("A model identifier must be configured")
        self.model = model.strip()

    def select_model(self, hint: ComplexityHint) -> str:
        return self.model


class DisabledProvider:
    """Used when AI_ENABLED=false. Agents fall back to deterministic results."""

    name = "disabled"

    async def generate_structured(self, request: LLMRequest, output_model: type[T]) -> LLMResult[T]:
        raise LLMDisabledError("AI reasoning is disabled by configuration")


def build_provider(settings: Settings, usage: UsageTracker) -> LLMProvider:
    if not settings.ai_enabled:
        return DisabledProvider()

    if settings.ai_provider == "anthropic":
        from app.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            settings,
            SingleModelRouter(settings.anthropic_model),
            usage,
        )

    if settings.ai_provider == "openrouter":
        from app.providers.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(
            settings,
            SingleModelRouter(settings.openrouter_model),
            usage,
        )

    if settings.ai_provider == "nvidia":
        from app.providers.nvidia_provider import NvidiaProvider
        return NvidiaProvider(
            settings,
            SingleModelRouter(settings.nvidia_model),
            usage,
        )

    raise ValueError(f"Unsupported AI_PROVIDER {settings.ai_provider!r}")

"""Vendor-neutral LLM provider interface.

Business logic and agents depend only on this module, never on a vendor SDK, so the reasoning
provider can be replaced without rewriting agents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ComplexityHint(StrEnum):
    """Recorded with every call. The single-model router ignores it today (future routing hook)."""

    light = "light"
    standard = "standard"
    complex = "complex"


@dataclass(frozen=True)
class DataSection:
    """Untrusted data (records, teacher text) passed to the model. Always wrapped as data."""

    name: str
    payload: Any


@dataclass
class LLMRequest:
    prompt_id: str
    instruction: str
    data: list[DataSection] = field(default_factory=list)
    complexity: ComplexityHint = ComplexityHint.standard
    max_output_tokens: int | None = None
    mentor_ref: str | None = None
    execution_id: str | None = None


@dataclass
class LLMUsageInfo:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


@dataclass
class LLMResult(Generic[T]):
    output: T
    model_requested: str
    model_served: str | None
    stop_reason: str | None
    usage: LLMUsageInfo
    provider_request_id: str | None
    latency_ms: int
    prompt_version: str


class LLMError(Exception):
    code = "llm_error"


class LLMDisabledError(LLMError):
    code = "ai_disabled"


class LLMBudgetExceededError(LLMError):
    code = "budget_exceeded"


class LLMTransientError(LLMError):
    """Timeouts, rate limits, overload, 5xx. Safe to retry later."""

    code = "provider_unavailable"


class LLMPermanentError(LLMError):
    """Authentication, permission, invalid request. Never retried automatically."""

    code = "provider_rejected"


class LLMRefusalError(LLMError):
    code = "refused"

    def __init__(self, message: str, category: str | None = None):
        super().__init__(message)
        self.category = category


class LLMTruncatedError(LLMError):
    code = "truncated"


class LLMOutputInvalidError(LLMError):
    code = "invalid_output"


class LLMProvider(Protocol):
    name: str

    async def generate_structured(self, request: LLMRequest, output_model: type[T]) -> LLMResult[T]: ...


def render_data_sections(sections: list[DataSection]) -> str:
    """Render untrusted data in clearly delimited blocks. Closing tags inside data are neutralised."""
    blocks = []
    for section in sections:
        body = json.dumps(section.payload, ensure_ascii=False, default=str, sort_keys=True, indent=1)
        body = body.replace("</marg_data", "<\\/marg_data")
        blocks.append(f'<marg_data name="{section.name}" trust="untrusted">\n{body}\n</marg_data>')
    return "\n\n".join(blocks)

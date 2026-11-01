from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.db.session import Database
from app.dependencies import Container
from app.main import create_app
from app.providers.base import LLMProvider, LLMRequest, LLMResult, LLMUsageInfo
from app.security.permissions import Principal
from app.seed.demo_data import seed_demo_data

ANCHOR = date(2026, 11, 2)  # Monday
FIXED_NOW = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)  # 08:30 Asia/Kolkata
MENTOR = Principal("MEN-001")
HEADERS = {"X-Actor-Ref": "MEN-001"}


def make_settings(**overrides: Any) -> Settings:
    # Explicit values so real environment variables (e.g. the developer's API key) never leak into tests.
    base: dict[str, Any] = {
        "app_env": "test",
        "ai_enabled": False,
        "ai_provider": "anthropic",
        "db_backend": "sqlite",
        "visit_duration_minutes": 180,
        "anthropic_api_key": None,
        "anthropic_model": "",
        "engine_api_key": None,
        "anthropic_effort": "",
        "llm_pricing": "",
        "anthropic_refusal_fallback": "off",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


class FakeLLMProvider:
    """Scripted stand-in for Claude. ``responses`` maps output model name -> list of outputs or exceptions."""

    name = "fake"

    def __init__(
        self, responses: dict[str, list[Any]] | None = None, default: Callable[[type], Any] | None = None
    ):
        self.responses = responses or {}
        self.default = default
        self.calls: list[tuple[LLMRequest, str]] = []

    async def generate_structured(self, request: LLMRequest, output_model: type) -> LLMResult:
        self.calls.append((request, output_model.__name__))
        queue = self.responses.get(output_model.__name__)
        item = queue.pop(0) if queue else (self.default(output_model) if self.default else None)
        if isinstance(item, Exception):
            raise item
        if item is None:
            raise AssertionError(f"No scripted response for {output_model.__name__}")
        output = item if isinstance(item, output_model) else output_model.model_validate(item)
        return LLMResult(
            output=output,
            model_requested="test-model",
            model_served="test-model",
            stop_reason="end_turn",
            usage=LLMUsageInfo(input_tokens=100, output_tokens=50),
            provider_request_id="req_test",
            latency_ms=5,
            prompt_version="v1",
        )


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    database = Database.sqlite()
    await database.create_all()
    await seed_demo_data(database, ANCHOR)
    yield database
    await database.dispose()


def build_container(
    settings: Settings, db: Database, provider: LLMProvider | None = None, now: datetime = FIXED_NOW
) -> Container:
    return Container.build(settings, db=db, provider=provider, clock=lambda: now)


@pytest.fixture
def container(settings: Settings, db: Database) -> Container:
    return build_container(settings, db)


@pytest.fixture
async def client(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(container)
    app.state.container = container
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c

"""Service container and FastAPI dependencies (identity, API key)."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import Header, HTTPException, Request

from app.config import BackendMode, Settings
from app.core.agent_registry import AgentRegistry, default_registry
from app.core.approval_engine import ApprovalEngine
from app.core.orchestrator import Orchestrator
from app.db.session import Database
from app.integrations.base_adapter import MentorDataAdapter
from app.integrations.demo_adapter import DemoDataAdapter
from app.integrations.marg_backend.client import HttpMARGBackendAdapter
from app.providers.base import LLMProvider
from app.providers.model_factory import build_provider
from app.providers.usage_tracker import UsageTracker
from app.security.permissions import Principal, PrincipalKind
from app.utils.datetime_utils import utcnow


@dataclass
class Container:
    settings: Settings
    db: Database
    adapter: MentorDataAdapter
    usage: UsageTracker
    provider: LLMProvider
    registry: AgentRegistry
    orchestrator: Orchestrator
    approvals: ApprovalEngine

    @classmethod
    def build(
        cls,
        settings: Settings,
        db: Database | None = None,
        provider: LLMProvider | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> Container:
        db = db or Database.from_settings(settings)
        adapter: MentorDataAdapter
        if settings.backend_mode is BackendMode.marg:
            adapter = HttpMARGBackendAdapter.from_settings(settings)
        else:
            adapter = DemoDataAdapter(db)
        usage = UsageTracker(db, settings)
        provider = provider or build_provider(settings, usage)
        registry = default_registry()
        return cls(
            settings=settings,
            db=db,
            adapter=adapter,
            usage=usage,
            provider=provider,
            registry=registry,
            orchestrator=Orchestrator(db, adapter, provider, settings, registry, clock),
            approvals=ApprovalEngine(db, adapter, settings, clock),
        )


def get_container(request: Request) -> Container:
    return request.app.state.container


async def get_principal(
    request: Request,
    x_actor_ref: str | None = Header(
        default=None, description="DEV ONLY: acting user reference (e.g. MEN-001)"
    ),
    x_actor_role: str | None = Header(
        default=None, description="DEV ONLY: comma-separated provisional roles"
    ),
    x_actor_kind: str | None = Header(default=None, description="DEV ONLY: 'human' (default) or 'system'"),
    x_api_key: str | None = Header(
        default=None, description="Engine API key, required if ENGINE_API_KEY is set"
    ),
) -> Principal:
    settings: Settings = request.app.state.container.settings
    if settings.engine_api_key is not None:
        expected = settings.engine_api_key.get_secret_value().encode("utf-8")
        supplied = (x_api_key or "").strip().encode("utf-8")
        # Byte comparison: constant-time, and safe for non-ASCII header values (str compare_digest raises).
        if not supplied or not secrets.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
    # Identity headers are trusted either in development (DEV_AUTH_HEADER_ENABLED)
    # or from the MARG backend gateway, which must have passed the API-key check above.
    gateway = settings.trusted_gateway_identity and settings.engine_api_key is not None
    if not (settings.dev_auth_header_enabled or gateway):
        raise HTTPException(status_code=401, detail="Authentication is not configured")
    if not x_actor_ref or len(x_actor_ref) > 64:
        raise HTTPException(status_code=401, detail="X-Actor-Ref header is required")
    roles = frozenset(r.strip() for r in (x_actor_role or "").split(",") if r.strip())
    kind = PrincipalKind.system if (x_actor_kind or "").lower() == "system" else PrincipalKind.human
    return Principal(actor_ref=x_actor_ref, roles=roles, kind=kind)

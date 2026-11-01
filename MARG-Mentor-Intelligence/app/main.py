"""FastAPI application factory for the MARG Mentor Intelligence Engine (prototype)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import agents, health, operations
from app.api.responses import UTF8JSONResponse
from app.config import DbBackend, get_settings
from app.core.agent_registry import UnknownAgentError
from app.core.approval_engine import ProposalStateError
from app.core.orchestrator import ExecutionFailed, OrchestratorError
from app.dependencies import Container
from app.integrations.base_adapter import RecordNotFound
from app.integrations.marg_backend.client import BackendRejected, BackendUnavailable
from app.monitoring.logging_config import configure_logging, request_id_var
from app.schemas.common import SCHEMA_VERSION
from app.security.permissions import PermissionDenied

logger = logging.getLogger(__name__)

DESCRIPTION = """
Planning and coordination engine for education mentors and Cluster Resource Persons.

* **Deterministic Python** calculates priorities, deadlines, workload, schedules and status.
* **NVIDIA-hosted inference** (one configurable model) explains, summarises and drafts - its output is validated and
  labelled as AI-generated, and it never changes calculated values.
* **Approval controls**: agents only *propose* consequential actions; a human approves them.
  Teacher messages are never sent by this engine.

**Prototype notice:** operational records are **DEMO DATA**. Integration with the main MARG backend
is pending its OpenAPI compatibility audit. Development identity headers (`X-Actor-Ref`,
`X-Actor-Role`) are provisional.
"""


def _error(status: int, code: str, message: str, extra: dict | None = None) -> JSONResponse:
    body = {
        "schema_version": SCHEMA_VERSION,
        "success": False,
        "data": None,
        "error": {"code": code, "message": message, **(extra or {})},
        "meta": {},
    }
    return UTF8JSONResponse(status_code=status, content=jsonable_encoder(body))


def create_app(container: Container | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if container is None:
            settings = get_settings()
            configure_logging(settings.log_level, settings.log_format)
            app.state.container = Container.build(settings)
            info = await app.state.container.db.verify()
            if settings.db_backend is DbBackend.sqlite:
                await app.state.container.db.create_all()
            logger.info("engine_started", extra={"database": info, "config": settings.describe()})
        else:
            app.state.container = container
        yield
        await app.state.container.db.dispose()

    app = FastAPI(
        title="MARG Mentor Intelligence Engine",
        version="0.1.0-prototype",
        description=DESCRIPTION,
        lifespan=lifespan,
        default_response_class=UTF8JSONResponse,
    )
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(operations.router)

    @app.middleware("http")
    async def request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID", "")
        if not rid or len(rid) > 64 or not rid.replace("-", "").isalnum():
            rid = str(uuid.uuid4())
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(PermissionDenied)
    async def _denied(_: Request, exc: PermissionDenied) -> JSONResponse:
        return _error(403, "permission_denied", str(exc))

    @app.exception_handler(ExecutionFailed)
    async def _exec_failed(_: Request, exc: ExecutionFailed) -> JSONResponse:
        return _error(exc.http_status, exc.error_code, str(exc), {"execution_id": str(exc.execution_id)})

    @app.exception_handler(OrchestratorError)
    async def _orch(_: Request, exc: OrchestratorError) -> JSONResponse:
        return _error(exc.http_status, exc.code, str(exc))

    @app.exception_handler(ProposalStateError)
    async def _proposal(_: Request, exc: ProposalStateError) -> JSONResponse:
        return _error(exc.http_status, exc.code, str(exc))

    @app.exception_handler(BackendUnavailable)
    async def _backend_down(_: Request, exc: BackendUnavailable) -> JSONResponse:
        return _error(503, "backend_unavailable", str(exc))

    @app.exception_handler(BackendRejected)
    async def _backend_rejected(_: Request, exc: BackendRejected) -> JSONResponse:
        return _error(409, "backend_rejected", str(exc))

    @app.exception_handler(UnknownAgentError)
    @app.exception_handler(RecordNotFound)
    @app.exception_handler(LookupError)
    async def _not_found(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, KeyError):  # programming errors are not "not found"
            logger.exception("unhandled_key_error")
            return _error(500, "internal_error", "An internal error occurred")
        return _error(404, "not_found", str(exc).strip("'\""))

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def _invalid(_: Request, exc: Exception) -> JSONResponse:
        errors = exc.errors() if hasattr(exc, "errors") else []
        safe = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in errors]
        return _error(422, "validation_error", "Request validation failed", {"details": safe})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error")
        return _error(500, "internal_error", "An internal error occurred")

    return app


app = create_app()

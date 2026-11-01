"""Health endpoints. They never expose secret values."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.responses import UTF8JSONResponse
from app.dependencies import Container, get_container

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health/live", summary="Process is running")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Configuration and database readiness (no secrets)")
async def ready(c: Container = Depends(get_container)) -> JSONResponse:
    checks: dict[str, object] = {"configuration": c.settings.describe()}
    healthy = True
    try:
        checks["database"] = {"status": "ok", **(await c.db.verify())}
    except Exception as exc:  # report the class of failure only
        logger.warning("readiness_db_failed", extra={"error_type": type(exc).__name__})
        checks["database"] = {"status": "error", "error_type": type(exc).__name__}
        healthy = False
    checks["redis"] = {"status": "not_configured", "note": "Background jobs are a later phase"}
    checks["ai_provider"] = {
        "status": "enabled" if c.settings.ai_enabled else "disabled",
        "provider": c.provider.name,
    }
    if c.settings.backend_mode.value == "marg":
        # Real MARG backend: verify it is reachable (liveness endpoint, no data).
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(c.settings.marg_backend_url.rstrip("/") + "/health")
            ok = r.status_code == 200
        except httpx.HTTPError:
            ok = False
        checks["backend"] = {"mode": "marg", "status": "ok" if ok else "unreachable"}
        healthy = healthy and ok
    else:
        checks["backend"] = {"mode": c.settings.backend_mode.value, "note": "DEMO DATA - development only"}
    return UTF8JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "not_ready", "checks": checks},
    )

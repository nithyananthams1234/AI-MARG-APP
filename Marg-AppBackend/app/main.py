import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.action_plan_steps.router import router as action_plan_step_router
from app.action_plans.router import router as action_plan_router
from app.ai.router import router as ai_router
from app.auth.router import router as auth_router
from app.classrooms.router import router as classroom_router
from app.coach.router import router as coach_router
from app.mentor_ai.integration_router import router as mentor_intelligence_integration_router
from app.mentor_ai.router import router as mentor_ai_router
from app.core.config import settings
from app.database.session import AsyncSessionLocal, engine
from app.services.notifications import generate_reminders
from app.evidence.router import router as evidence_router
from app.follow_ups.router import router as follow_up_router
from app.learning_gaps.router import router as learning_gap_router
from app.mentor_schools.router import router as mentor_school_router
from app.mentor_tasks.router import router as mentor_task_router
from app.notifications.router import router as notifications_router
from app.observation_findings.router import router as observation_finding_router
from app.observations.router import router as observation_router
from app.recommendations.router import router as recommendation_router
from app.reports.router import router as reports_router
from app.schedules.router import router as schedule_router
from app.school_visits.router import router as school_visit_router
from app.schools.router import router as school_router
from app.sync.router import router as sync_router
from app.teachers.router import router as teacher_router
from app.teachers.router import school_teacher_router
from app.timetables.router import router as timetable_router
from app.whatsapp.router import router as whatsapp_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("marg.backend")

async def _reminder_loop() -> None:
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await generate_reminders(db)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Reminder generation failed")
        await asyncio.sleep(settings.reminders_interval_minutes * 60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = None
    if settings.reminders_inline and settings.app_env != "test":
        task = asyncio.create_task(_reminder_loop())
    yield
    if task:
        task.cancel()


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version="0.2.0",
    description="MARG Educational Mentoring Platform Backend",
    # Interactive docs are disabled in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # bearer tokens, no cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    # Note: X-Service-Key is deliberately not allowed from browsers.
    expose_headers=["X-Request-ID", "Retry-After"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id[:64]
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info(
        "%s %s -> %s %.0fms rid=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
        request.state.request_id,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak internal error details to clients; log them with the request id.
    rid = getattr(request.state, "request_id", "-")
    logger.exception("Unhandled error rid=%s", rid)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": rid},
    )


for router in (
    auth_router,
    school_router,
    teacher_router,
    school_teacher_router,
    classroom_router,
    timetable_router,
    school_visit_router,
    observation_router,
    observation_finding_router,
    learning_gap_router,
    recommendation_router,
    action_plan_router,
    action_plan_step_router,
    follow_up_router,
    evidence_router,
    mentor_task_router,
    schedule_router,
    sync_router,
    ai_router,
    mentor_school_router,
    notifications_router,
    reports_router,
    whatsapp_router,
    coach_router,
    mentor_ai_router,
    mentor_intelligence_integration_router,
):
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Infrastructure"])
async def health():
    """Liveness: the process is up."""
    return {"status": "ok", "service": "marg-backend"}


@app.get("/health/database", tags=["Infrastructure"])
async def database_health():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "message": "PostgreSQL connection successful",
        }
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail={"status": "disconnected", "message": "PostgreSQL connection failed"},
        )


@app.get("/health/ready", tags=["Infrastructure"])
async def readiness():
    """Readiness: database reachable and schema migrated to the expected head."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    checks: dict[str, str] = {}
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            current = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
        checks["database"] = "ok"
        head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        checks["migrations"] = "ok" if current == head else f"pending (db={current}, head={head})"
    except Exception:  # noqa: BLE001
        checks["database"] = "unavailable"

    ready = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if ready else 503, content={"ready": ready, "checks": checks})

"""MARG Classroom Coach API (NVIDIA-hosted LLM + RAG)."""

import logging
import secrets
import time
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.coach import analyse_observation, ask_classroom_coach
from app.config import settings
from app.llm.nvidia_client import LLMInvalidOutput, LLMUnavailable, model_available
from app.rag import retriever
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ObservationAnalysisRequest,
    ObservationAnalysisResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("coach.api")

if settings.is_production and not settings.COACH_API_KEY:
    raise RuntimeError("COACH_API_KEY must be set when APP_ENV=production")
if settings.is_production and (
    settings.NVIDIA_API_KEY is None or not settings.NVIDIA_API_KEY.get_secret_value().strip()
):
    raise RuntimeError("NVIDIA_API_KEY must be set when APP_ENV=production")

app = FastAPI(
    title="MARG Classroom Coach API",
    description="Retrieval-augmented educational assistant (NVIDIA-hosted LLM + ChromaDB).",
    version="1.1.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Service-to-service authentication. Disabled only when no key is configured (local dev)."""
    expected = settings.COACH_API_KEY
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = (request.headers.get("X-Request-ID") or uuid.uuid4().hex)[:64]
    request.state.request_id = rid
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    logger.info("%s %s -> %s %.0fms rid=%s", request.method, request.url.path,
                response.status_code, (time.perf_counter() - started) * 1000, rid)
    return response


@app.exception_handler(LLMUnavailable)
async def llm_unavailable(request: Request, exc: LLMUnavailable):
    logger.warning("LLM unavailable: %s", exc)
    return JSONResponse(status_code=503, content={
        "detail": "The Classroom Coach language model is currently unavailable. Please try again shortly.",
        "code": "llm_unavailable",
    })


@app.exception_handler(LLMInvalidOutput)
async def llm_invalid(request: Request, exc: LLMInvalidOutput):
    return JSONResponse(status_code=502, content={
        "detail": "The Classroom Coach could not produce a valid analysis. Please try again.",
        "code": "llm_invalid_output",
    })


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.exception("Unhandled error rid=%s", getattr(request.state, "request_id", "-"))
    return JSONResponse(status_code=500, content={
        "detail": "Classroom Coach internal error",
        "request_id": getattr(request.state, "request_id", None),
    })


@app.get("/")
async def root():
    return {"service": "marg-classroom-coach", "status": "ok"}


@app.get("/health")
async def health():
    """Liveness only (does not load models)."""
    return {"status": "ok", "service": "marg-classroom-coach"}


@app.get("/health/ready")
async def ready():
    checks: dict[str, str] = {}
    chunks = None
    try:
        chunks = retriever.chunk_count()
        checks["vector_store"] = "ok" if chunks > 0 else "empty"
    except Exception:  # noqa: BLE001
        checks["vector_store"] = "unavailable"
    checks["llm"] = "ok" if await model_available() else "unavailable"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={
        "ready": ok,
        "checks": checks,
        "llm_model": settings.NVIDIA_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "knowledge_chunks": chunks,
    })


@app.get("/api/v1/knowledge/stats", dependencies=[Depends(require_api_key)])
async def knowledge_stats():
    return {"collection": settings.COLLECTION_NAME, "total_chunks": retriever.chunk_count()}


@app.post("/api/v1/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(request: ChatRequest):
    result = await ask_classroom_coach(request.question, request.context)
    return ChatResponse(question=request.question, model=settings.NVIDIA_MODEL, **result)


@app.post(
    "/api/v1/analyze/observation",
    response_model=ObservationAnalysisResponse,
    dependencies=[Depends(require_api_key)],
)
async def analyze_observation(request: ObservationAnalysisRequest):
    content, sources = await analyse_observation(request.model_dump())
    return ObservationAnalysisResponse(**content.model_dump(), sources=sources, model=settings.NVIDIA_MODEL)

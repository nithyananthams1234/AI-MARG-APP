"""Mentor AI Assistant endpoints for mentors (proxied to Mentor Intelligence).

The backend authenticates the mentor (JWT) and asserts *that* mentor's
identity to MI together with MI's engine API key. The frontend never talks
to MI or Anthropic directly and never sees either key. A mentor can only
act as themselves: ``mentor_ref`` is always the authenticated user's id.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.auth.role_dependencies import get_current_mentor
from app.core.config import settings
from app.models.identity import User

logger = logging.getLogger("marg.mentor_ai")

router = APIRouter(prefix="/mentor-ai", tags=["Mentor AI Assistant"])

# Agent name (MARG API) -> MI endpoint path. Allow-list: nothing else is forwarded.
AGENTS: dict[str, str] = {
    "task_prioritisation": "/api/v1/tasks/prioritise",
    "time_analysis": "/api/v1/time/analysis",
    "schedule_analysis": "/api/v1/schedule/analysis",
    "workload_analysis": "/api/v1/workload/analysis",
    "followup_analysis": "/api/v1/followups/analysis",
    "visit_planning": "/api/v1/school-visits/plan",
    "daily_plan": "/api/v1/plans/daily",
    "weekly_plan": "/api/v1/plans/weekly",
    "report": "/api/v1/reports",
    "teacher_message_draft": "/api/v1/communications/drafts",
}


class AgentRunRequest(BaseModel):
    """Agent-specific options (forwarded after removing identity fields)."""

    model_config = ConfigDict(extra="allow")
    use_ai: bool = True


class ProposalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=500)


class ExternalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: bool
    detail: str | None = Field(default=None, max_length=500)


def _headers(mentor: User, request: Request, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "X-Actor-Ref": str(mentor.id),
        "X-Actor-Role": "mentor",
        "Content-Type": "application/json",
    }
    if settings.mentor_intelligence_api_key:
        headers["X-API-Key"] = settings.mentor_intelligence_api_key
    rid = getattr(request.state, "request_id", None)
    if rid:
        headers["X-Request-ID"] = rid
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key[:200]
    return headers


async def _call(
    method: str,
    path: str,
    mentor: User,
    request: Request,
    *,
    json: dict | None = None,
    params: dict | None = None,
    idempotency_key: str | None = None,
) -> Any:
    url = settings.mentor_intelligence_url.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=settings.mentor_intelligence_timeout_seconds) as client:
            r = await client.request(
                method, url, json=json, params=params, headers=_headers(mentor, request, idempotency_key)
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="The Mentor AI Assistant took too long to respond.")
    except httpx.RequestError:
        logger.warning("Mentor Intelligence unreachable at %s", url)
        raise HTTPException(status_code=503, detail="The Mentor AI Assistant is currently unavailable.")

    try:
        body = r.json()
    except ValueError:
        body = None

    if r.status_code in (401, 403) and not (isinstance(body, dict) and body.get("error")):
        raise HTTPException(status_code=503, detail="The Mentor AI Assistant is not configured correctly.")
    if r.status_code >= 400:
        # MI envelope: {"success": false, "error": {"code", "message"}}
        message = None
        if isinstance(body, dict):
            err = body.get("error") or {}
            message = err.get("message") if isinstance(err, dict) else None
            message = message or (body.get("detail") if isinstance(body.get("detail"), str) else None)
        status_code = r.status_code if r.status_code in (400, 403, 404, 409, 422, 429) else 502
        raise HTTPException(status_code=status_code, detail=message or "The Mentor AI Assistant request failed.")
    return body


@router.get("/status")
async def status(request: Request, mentor: User = Depends(get_current_mentor)):
    url = settings.mentor_intelligence_url.rstrip("/") + "/health/ready"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
        body = r.json()
        return {"available": r.status_code == 200, "details": body.get("data", body)}
    except (httpx.RequestError, ValueError):
        return {"available": False, "details": {"service": "unreachable"}}


@router.get("/agents")
async def list_agents(mentor: User = Depends(get_current_mentor)):
    return {"agents": sorted(AGENTS)}


@router.post("/agents/{agent}")
async def run_agent(
    agent: str,
    body: AgentRunRequest,
    request: Request,
    mentor: User = Depends(get_current_mentor),
    idempotency_key: str | None = Header(default=None),
):
    path = AGENTS.get(agent)
    if path is None:
        raise HTTPException(status_code=404, detail="Unknown Mentor AI agent.")
    payload = body.model_dump()
    payload.pop("mentor_ref", None)  # identity is never taken from the client
    payload["mentor_ref"] = str(mentor.id)
    return await _call("POST", path, mentor, request, json=payload, idempotency_key=idempotency_key)


@router.get("/executions")
async def list_executions(
    request: Request, limit: int = Query(default=20, ge=1, le=100), mentor: User = Depends(get_current_mentor)
):
    return await _call("GET", "/api/v1/executions", mentor, request, params={"mentor_ref": str(mentor.id), "limit": limit})


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str, request: Request, mentor: User = Depends(get_current_mentor)):
    return await _call("GET", f"/api/v1/executions/{execution_id}", mentor, request)


@router.get("/proposals")
async def list_proposals(
    request: Request,
    status_filter: Literal["pending", "approved", "rejected", "executed", "execution_failed", "expired"] | None = Query(default=None, alias="status"),
    mentor: User = Depends(get_current_mentor),
):
    params: dict[str, str] = {"mentor_ref": str(mentor.id)}
    if status_filter:
        params["status"] = status_filter
    return await _call("GET", "/api/v1/proposals", mentor, request, params=params)


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str, request: Request, mentor: User = Depends(get_current_mentor)):
    return await _call("GET", f"/api/v1/proposals/{proposal_id}", mentor, request)


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str, body: ProposalDecision, request: Request, mentor: User = Depends(get_current_mentor)
):
    return await _call("POST", f"/api/v1/proposals/{proposal_id}/approve", mentor, request, json=body.model_dump())


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str, body: ProposalDecision, request: Request, mentor: User = Depends(get_current_mentor)
):
    return await _call("POST", f"/api/v1/proposals/{proposal_id}/reject", mentor, request, json=body.model_dump())


@router.post("/proposals/{proposal_id}/external-result")
async def proposal_external_result(
    proposal_id: str, body: ExternalResult, request: Request, mentor: User = Depends(get_current_mentor)
):
    """Report the outcome of an approved external action (e.g. message sent via WhatsApp)."""
    return await _call(
        "POST", f"/api/v1/proposals/{proposal_id}/external-result", mentor, request, json=body.model_dump()
    )


@router.get("/plans")
async def list_plans(
    request: Request,
    plan_type: Literal["daily", "weekly"] | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    mentor: User = Depends(get_current_mentor),
):
    params: dict[str, Any] = {"mentor_ref": str(mentor.id), "limit": limit}
    if plan_type:
        params["plan_type"] = plan_type
    return await _call("GET", "/api/v1/plans", mentor, request, params=params)

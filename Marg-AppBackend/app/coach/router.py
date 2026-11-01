"""Classroom Coach endpoints for mentors (proxied to the Coach service)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.database.session import get_db_session
from app.integrations import classroom_coach
from app.models.classroom import Classroom
from app.models.identity import User
from app.models.observation import Observation

router = APIRouter(prefix="/coach", tags=["Classroom Coach"])


class CoachContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str | None = Field(default=None, max_length=100)
    grade: str | None = Field(default=None, max_length=30)
    topic: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


class CoachChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=2000)
    # Ground the answer in one of the mentor's observations (optional).
    observation_id: UUID | None = None
    context: CoachContext | None = None


class CoachSource(BaseModel):
    document: str
    title: str | None = None
    page: int
    relevance: float | None = None
    excerpt: str | None = None


class CoachChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[CoachSource]
    grounded: bool
    model: str | None = None


@router.get("/status")
async def coach_status(current_user: User = Depends(get_current_mentor)):
    return await classroom_coach.readiness()


@router.post("/chat", response_model=CoachChatResponse)
async def coach_chat(
    payload: CoachChatRequest,
    request: Request,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    context = payload.context.model_dump(exclude_none=True) if payload.context else {}

    if payload.observation_id is not None:
        observation = (
            await db.execute(
                select(Observation).where(
                    Observation.id == payload.observation_id, Observation.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if observation is None:
            raise HTTPException(status_code=404, detail="Observation not found.")
        classroom = (
            await db.execute(select(Classroom).where(Classroom.id == observation.classroom_id))
        ).scalar_one_or_none()
        # Only educational context is shared; no teacher/student identities.
        context = {
            "subject": observation.subject,
            "grade": classroom.grade if classroom else None,
            "topic": observation.topic,
            "notes": (observation.notes or "")[:4000] or None,
            **context,
        }

    try:
        data = await classroom_coach.chat(
            payload.question, context or None, request_id=getattr(request.state, "request_id", None)
        )
    except classroom_coach.CoachError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc

    try:
        return CoachChatResponse.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="The Classroom Coach returned an invalid response.") from exc

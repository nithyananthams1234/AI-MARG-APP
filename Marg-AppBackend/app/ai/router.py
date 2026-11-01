
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timezone

import logging

from fastapi import BackgroundTasks

from app.auth.role_dependencies import get_current_mentor
from app.core.config import settings
from app.database.session import AsyncSessionLocal, get_db_session
from app.models.ai_job import AIJob
from app.models.classroom import Classroom
from app.models.identity import User
from app.models.learning_gap import LearningGap
from app.models.observation import Observation
from app.models.observation_finding import ObservationFinding
from app.models.recommendation import Recommendation
from app.schemas.ai import (
    AIAnalysisResponse,
    AIJobApplyRequest,
    AIJobApplyResponse,
    AIJobCreate,
    AIJobResponse,
)
from app.services.ai_job import process_ai_job

logger = logging.getLogger("marg.ai")


router = APIRouter(prefix="/ai", tags=["AI Integration"])


ALLOWED_ENTITY_TYPES = {
    "observation",
    "learning_gap",
    "recommendation",
    "action_plan",
}


async def _build_observation_input(db: AsyncSession, observation_id: UUID) -> dict:
    """Build the analysis input from the database (scoped to the mentor)."""
    observation = (
        await db.execute(
            select(Observation).where(
                Observation.id == observation_id, Observation.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if observation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation not found.")
    if not observation.notes or len(observation.notes.strip()) < 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Add at least a few sentences of observation notes before requesting AI analysis.",
        )
    classroom = (
        await db.execute(select(Classroom).where(Classroom.id == observation.classroom_id))
    ).scalar_one_or_none()
    findings = (
        await db.execute(
            select(ObservationFinding.title).where(
                ObservationFinding.observation_id == observation.id,
                ObservationFinding.deleted_at.is_(None),
                ObservationFinding.status != "rejected",
            )
        )
    ).scalars().all()
    # No teacher or student names are sent to the AI service.
    return {
        "subject": observation.subject,
        "grade": classroom.grade if classroom else None,
        "topic": observation.topic,
        "observation_notes": observation.notes.strip(),
        "existing_findings": list(findings),
    }


async def _process_in_background(job_id: UUID) -> None:
    """Process a job right away in a system session (the job is already authorised)."""
    async with AsyncSessionLocal() as db:
        try:
            await process_ai_job(db, job_id)
        except HTTPException:
            pass  # failure is recorded on the job
        except Exception:  # noqa: BLE001
            logger.exception("Inline AI job %s failed", job_id)


@router.post(
    "/jobs",
    response_model=AIJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ai_job(
    request: AIJobCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    if request.entity_type not in ALLOWED_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported AI entity type.",
        )

    if request.job_type == "observation_analysis":
        if request.entity_type != "observation":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="observation_analysis jobs must reference an observation.",
            )
        input_payload = await _build_observation_input(db, request.entity_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This AI job type is not available yet.",
        )

    job = AIJob(
        requested_by=current_user.id,
        created_by=current_user.id,
        updated_by=current_user.id,
        job_type=request.job_type,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        input_payload=input_payload,
        status="queued",
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    if settings.ai_inline_processing:
        background_tasks.add_task(_process_in_background, job.id)

    return job


@router.post(
    "/jobs/{job_id}/apply",
    response_model=AIJobApplyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_ai_job_suggestions(
    job_id: UUID,
    request: AIJobApplyRequest,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    """Record mentor-selected AI suggestions as ``ai_suggested`` records.

    Created findings and recommendations keep status ``ai_suggested`` and
    still require the mentor's explicit approval before becoming official.
    """
    job = (
        await db.execute(select(AIJob).where(AIJob.id == job_id, AIJob.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI job not found.")
    if job.status != "completed" or not job.result_payload:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="AI job has no completed result.")
    if job.entity_type != "observation":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only observation analyses can be applied.")

    observation = (
        await db.execute(
            select(Observation).where(Observation.id == job.entity_id, Observation.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if observation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation not found.")
    if observation.status == "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Submit the observation before recording findings.",
        )

    if (job.result_payload or {}).get("applied_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="These AI suggestions were already recorded. Review them in the observation.",
        )

    analysis = AIAnalysisResponse.model_validate(job.result_payload)

    def pick(items: list, idx: int, kind: str):
        if idx >= len(items):
            raise HTTPException(status_code=422, detail=f"Invalid {kind} index {idx}.")
        return items[idx]

    finding_ids, gap_ids, rec_ids = [], [], []
    for idx in dict.fromkeys(request.finding_indexes):
        f = pick(analysis.findings, idx, "finding")
        finding = ObservationFinding(
            observation_id=observation.id,
            title=f.title[:200],
            description=f.description,
            category=f.category[:100],
            status="ai_suggested",
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(finding)
        await db.flush()
        finding_ids.append(finding.id)

    for idx in dict.fromkeys(request.learning_gap_indexes):
        g = pick(analysis.learning_gaps, idx, "learning gap")
        gap = LearningGap(
            observation_id=observation.id,
            title=g.title[:200],
            description=g.description,
            subject=(g.subject or observation.subject)[:100],
            grade=(g.grade or job.input_payload.get("grade")),
            severity=g.severity,
            status="identified",
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(gap)
        await db.flush()
        gap_ids.append(gap.id)

    for sel in request.recommendations:
        r = pick(analysis.recommendations, sel.index, "recommendation")
        if sel.learning_gap_index is not None:
            if sel.learning_gap_index >= len(gap_ids):
                raise HTTPException(status_code=422, detail="learning_gap_index must refer to a selected learning gap.")
            gap_id = gap_ids[sel.learning_gap_index]
        elif sel.learning_gap_id is not None:
            existing_gap = (
                await db.execute(
                    select(LearningGap).where(
                        LearningGap.id == sel.learning_gap_id, LearningGap.deleted_at.is_(None)
                    )
                )
            ).scalar_one_or_none()
            if existing_gap is None:
                raise HTTPException(status_code=404, detail="Learning gap not found.")
            gap_id = existing_gap.id
        else:
            raise HTTPException(status_code=422, detail="Each recommendation must be linked to a learning gap.")
        rec = Recommendation(
            learning_gap_id=gap_id,
            title=r.title[:200],
            description=r.description,
            rationale=r.rationale,
            category=r.category[:100],
            status="ai_suggested",
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(rec)
        await db.flush()
        rec_ids.append(rec.id)

    # Mark the job as applied (in the same transaction) so suggestions are
    # never recorded twice.
    job.result_payload = {
        **job.result_payload,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "applied_by": str(current_user.id),
    }
    await db.commit()
    return AIJobApplyResponse(finding_ids=finding_ids, learning_gap_ids=gap_ids, recommendation_ids=rec_ids)


@router.get(
    "/jobs",
    response_model=list[AIJobResponse],
)
async def list_ai_jobs(
    job_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    query = select(AIJob).where(
        AIJob.requested_by == current_user.id,
        AIJob.deleted_at.is_(None),
    )

    if job_status is not None:
        allowed_statuses = {
            "queued",
            "processing",
            "completed",
            "failed",
            "cancelled",
        }

        if job_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid AI job status.",
            )

        query = query.where(AIJob.status == job_status)

    query = query.order_by(AIJob.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


@router.get(
    "/jobs/{job_id}",
    response_model=AIJobResponse,
)
async def get_ai_job(
    job_id: UUID,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(AIJob).where(
            AIJob.id == job_id,
            AIJob.requested_by == current_user.id,
            AIJob.deleted_at.is_(None),
        )
    )

    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI job not found.",
        )

    return job

@router.patch(
    "/jobs/{job_id}/cancel",
    response_model=AIJobResponse,
)
async def cancel_ai_job(
    job_id: UUID,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(AIJob)
        .where(
            AIJob.id == job_id,
            AIJob.requested_by == current_user.id,
            AIJob.deleted_at.is_(None),
        )
        .with_for_update()
    )

    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="AI job not found.",
        )

    if job.status != "queued":
        raise HTTPException(
            status_code=409,
            detail="Only queued AI jobs can be cancelled.",
        )

    job.status = "cancelled"
    job.updated_by = current_user.id
    job.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(job)

    return job


@router.patch(
    "/jobs/{job_id}/retry",
    response_model=AIJobResponse,
)
async def retry_ai_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(AIJob)
        .where(
            AIJob.id == job_id,
            AIJob.requested_by == current_user.id,
            AIJob.deleted_at.is_(None),
        )
        .with_for_update()
    )

    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="AI job not found.",
        )

    if job.status != "failed":
        raise HTTPException(
            status_code=409,
            detail="Only failed AI jobs can be retried.",
        )

    job.status = "queued"
    job.error_message = None
    job.result_payload = None
    job.started_at = None
    job.completed_at = None
    job.updated_at = datetime.now(timezone.utc)
    job.updated_by = current_user.id

    await db.commit()
    await db.refresh(job)

    if settings.ai_inline_processing:
        background_tasks.add_task(_process_in_background, job.id)

    return job

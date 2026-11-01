
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIJob
from app.services.ai_provider import generate_ai_analysis
from app.services.notifications import notify


async def process_ai_job(
    db: AsyncSession,
    job_id: UUID,
) -> AIJob:
    """
    Process one queued AI job.

    AI results are saved only in the AI job record.
    Official MARG business records are never modified here.
    """

    result = await db.execute(
        select(AIJob)
        .where(
            AIJob.id == job_id,
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
            detail=f"AI job cannot be processed from status '{job.status}'.",
        )

    job.status = "processing"
    job.started_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)

    await db.commit()

    try:
        analysis = await generate_ai_analysis(job.input_payload)

        job.result_payload = analysis.model_dump(mode="json")
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = None

        if job.requested_by is not None:
            await notify(
                db,
                user_id=job.requested_by,
                title="AI analysis ready for review",
                message=(
                    f"{len(analysis.findings)} finding(s), {len(analysis.learning_gaps)} learning gap(s) "
                    f"and {len(analysis.recommendations)} recommendation(s) were suggested. "
                    "Nothing is recorded until you review and approve it."
                ),
                notification_type="ai_job_completed",
                reference_entity_type=job.entity_type,
                reference_entity_id=job.entity_id,
                once=False,
            )

        await db.commit()
        await db.refresh(job)

        return job

    except Exception as exc:
        await db.rollback()

        # Only user-safe messages (HTTPException details we raise ourselves)
        # are stored; anything else becomes a generic message.
        message = (
            exc.detail
            if isinstance(exc, HTTPException) and isinstance(exc.detail, str)
            else "AI processing failed. Please retry the job."
        )

        result = await db.execute(
            select(AIJob).where(AIJob.id == job_id)
        )
        failed_job = result.scalar_one_or_none()

        if failed_job is not None:
            failed_job.status = "failed"
            failed_job.error_message = message
            failed_job.completed_at = datetime.now(timezone.utc)
            failed_job.updated_at = datetime.now(timezone.utc)
            if failed_job.requested_by is not None:
                await notify(
                    db,
                    user_id=failed_job.requested_by,
                    title="AI analysis could not be completed",
                    message=message,
                    notification_type="ai_job_failed",
                    reference_entity_type=failed_job.entity_type,
                    reference_entity_id=failed_job.entity_id,
                    once=False,
                )

            await db.commit()
            await db.refresh(failed_job)

        raise

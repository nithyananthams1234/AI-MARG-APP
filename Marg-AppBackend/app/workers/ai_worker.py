
import asyncio
import logging

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.ai_job import AIJob
from app.services.ai_job import process_ai_job
from app.services.notifications import generate_reminders


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("marg.ai_worker")

POLL_INTERVAL_SECONDS = 5


async def process_next_job() -> bool:
    """Find and process the oldest queued AI job."""

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AIJob.id)
            .where(
                AIJob.status == "queued",
                AIJob.deleted_at.is_(None),
            )
            .order_by(AIJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        job_id = result.scalar_one_or_none()

        if job_id is None:
            return False

        try:
            await process_ai_job(db, job_id)
            logger.info("AI job %s processed.", job_id)
        except Exception:
            logger.exception("AI job %s failed.", job_id)

        return True


REMINDER_INTERVAL_SECONDS = 600


async def run_worker() -> None:
    logger.info("MARG AI worker started.")
    last_reminders = 0.0

    while True:
        try:
            loop_time = asyncio.get_running_loop().time()
            if loop_time - last_reminders >= REMINDER_INTERVAL_SECONDS:
                async with AsyncSessionLocal() as db:
                    await generate_reminders(db)
                last_reminders = loop_time

            job_found = await process_next_job()

            if not job_found:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        except asyncio.CancelledError:
            logger.info("MARG AI worker stopped.")
            raise

        except Exception:
            logger.exception("Unexpected AI worker error.")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("MARG AI worker stopped.")

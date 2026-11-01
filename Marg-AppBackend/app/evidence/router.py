
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.role_dependencies import get_current_mentor
from app.core.config import settings
from app.database.session import get_db_session
from app.models.evidence import Evidence
from app.models.identity import User
from app.models.observation import Observation
from app.models.follow_up import FollowUp
from app.schemas.evidence import EvidenceResponse
from app.storage.service import delete_evidence_file, open_evidence_stream, save_evidence_file
from starlette.concurrency import run_in_threadpool


router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.post("/", response_model=EvidenceResponse, status_code=201)
async def upload_evidence(
    observation_id: uuid.UUID | None = Form(default=None),
    follow_up_id: uuid.UUID | None = Form(default=None),
    description: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    if (observation_id is None) == (follow_up_id is None):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of observation_id or follow_up_id.",
        )

    if observation_id:
        result = await db.execute(
            select(Observation).where(
                Observation.id == observation_id,
                Observation.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Observation not found.")

    if follow_up_id:
        result = await db.execute(
            select(FollowUp).where(
                FollowUp.id == follow_up_id,
                FollowUp.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Follow-up not found.")

    if description and len(description) > 1000:
        raise HTTPException(status_code=422, detail="Description is too long.")

    metadata = await save_evidence_file(file)

    evidence = Evidence(
        observation_id=observation_id,
        follow_up_id=follow_up_id,
        description=description,
        created_by=current_user.id,
        updated_by=current_user.id,
        **metadata,
    )

    try:
        db.add(evidence)
        await db.commit()
        await db.refresh(evidence)
    except Exception:
        await db.rollback()
        # Remove the orphaned object from whichever backend stored it.
        await run_in_threadpool(delete_evidence_file, metadata["storage_key"])
        raise

    return evidence


@router.get("/", response_model=list[EvidenceResponse])
async def list_evidence(
    observation_id: uuid.UUID | None = None,
    follow_up_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    query = select(Evidence).where(Evidence.deleted_at.is_(None))

    if observation_id:
        query = query.where(Evidence.observation_id == observation_id)

    if follow_up_id:
        query = query.where(Evidence.follow_up_id == follow_up_id)

    query = query.order_by(Evidence.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Evidence).where(
            Evidence.id == evidence_id,
            Evidence.deleted_at.is_(None),
        )
    )
    evidence = result.scalar_one_or_none()

    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found.")

    return evidence


@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_mentor),
):
    result = await db.execute(
        select(Evidence).where(
            Evidence.id == evidence_id,
            Evidence.deleted_at.is_(None),
        )
    )
    evidence = result.scalar_one_or_none()

    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found.")

    try:
        stream = await open_evidence_stream(evidence.storage_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid storage reference.")

    # Strip characters that could break the Content-Disposition header.
    safe_name = "".join(ch for ch in evidence.original_filename if ch not in {'"', '\r', '\n'})
    return StreamingResponse(
        stream,
        media_type=evidence.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    observation_id: uuid.UUID | None
    follow_up_id: uuid.UUID | None
    original_filename: str
    content_type: str
    file_size_bytes: int
    checksum_sha256: str | None
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceUploadRequest(BaseModel):
    description: str | None = Field(default=None, max_length=1000)
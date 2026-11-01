
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class WhatsAppMessageCreate(BaseModel):
    recipient: str = Field(min_length=8, max_length=30)
    message_type: Literal["text", "template"]
    content: str | None = None
    template_name: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=255)


class WhatsAppMessageResponse(BaseModel):
    id: UUID
    direction: str
    recipient: str
    message_type: str
    content: str | None
    template_name: str | None
    provider_message_id: str | None
    idempotency_key: str
    status: str
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)

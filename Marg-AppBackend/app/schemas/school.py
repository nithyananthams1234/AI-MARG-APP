
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SchoolCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=50)
    address: str | None = None
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    block: str | None = Field(default=None, max_length=100)
    travel_minutes_from_base: int | None = Field(default=None, ge=0, le=600)


class SchoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    code: str | None = Field(default=None, min_length=2, max_length=50)
    address: str | None = None
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    block: str | None = Field(default=None, max_length=100)
    travel_minutes_from_base: int | None = Field(default=None, ge=0, le=600)
    is_active: bool | None = None


class SchoolResponse(BaseModel):
    id: UUID
    name: str
    code: str
    address: str | None
    district: str | None
    state: str | None
    block: str | None = None
    travel_minutes_from_base: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)

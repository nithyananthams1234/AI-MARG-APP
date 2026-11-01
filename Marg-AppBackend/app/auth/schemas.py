from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    refresh_expires_in: int | None = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=20, max_length=200)
    all_devices: bool = False


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AssignedSchoolSummary(BaseModel):
    id: UUID
    name: str
    code: str
    district: str | None = None


class CurrentUserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    role: str
    roles: list[str]
    assigned_schools: list[AssignedSchoolSummary]

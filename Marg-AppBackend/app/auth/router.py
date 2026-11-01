
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import rate_limit
from app.auth.dependencies import get_current_user
from app.auth.hashing import hash_password, verify_password
from app.auth.jwt import create_access_token
from app.auth.role_dependencies import (
    ADMIN_ROLE,
    MENTOR_ROLE,
    get_current_mentor,
    get_user_role_names,
)
from app.auth.schemas import (
    AssignedSchoolSummary,
    CurrentUserResponse,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from app.core.config import settings
from app.database.session import get_db_session
from app.models.identity import User
from app.models.refresh_token import RefreshToken
from app.models.school import School

router = APIRouter(prefix="/auth", tags=["Authentication"])

LOGIN_ROLES = {MENTOR_ROLE, ADMIN_ROLE}

# Verifying against a dummy hash when the user does not exist keeps response
# timing similar for valid and invalid emails (user enumeration defence).
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _issue_tokens(
    db: AsyncSession,
    user: User,
    roles: set[str],
    family_id: uuid.UUID | None = None,
    device_label: str | None = None,
) -> tuple[TokenResponse, RefreshToken]:
    raw_refresh = secrets.token_urlsafe(48)
    refresh = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_refresh),
        family_id=family_id or uuid.uuid4(),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
        device_label=device_label,
    )
    db.add(refresh)
    await db.flush()

    tokens = TokenResponse(
        access_token=create_access_token(str(user.id), roles=sorted(roles)),
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_token=raw_refresh,
        refresh_expires_in=settings.refresh_token_expire_days * 86400,
    )
    return tokens, refresh


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session),
):
    """OAuth2 password login (form fields ``username`` = email, ``password``)."""
    email = credentials.username.strip().lower()
    rate_limit.check_login_allowed(request, email)

    result = await db.execute(
        select(User).where(
            User.email == email,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    password_ok = verify_password(
        credentials.password, user.password_hash if user else _DUMMY_HASH
    )
    roles = await get_user_role_names(db, user.id) if user else set()

    if user is None or not password_ok or not (roles & LOGIN_ROLES):
        rate_limit.record_failed_login(request, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    rate_limit.reset_login_attempts(request, email)
    tokens, _ = await _issue_tokens(
        db, user, roles, device_label=(request.headers.get("user-agent") or "")[:100]
    )
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Exchange a refresh token for a new access + refresh token (rotation)."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == _hash_token(data.refresh_token))
        .with_for_update()
    )
    stored = result.scalar_one_or_none()
    if stored is None:
        raise invalid

    if stored.revoked_at is not None:
        # Reuse of a rotated/revoked token: assume theft, revoke the family.
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == stored.family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.commit()
        raise invalid

    if stored.expires_at <= now:
        raise invalid

    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise invalid

    roles = await get_user_role_names(db, user.id)
    if not roles & LOGIN_ROLES:
        raise invalid

    tokens, new_refresh = await _issue_tokens(
        db, user, roles, family_id=stored.family_id, device_label=stored.device_label
    )
    stored.revoked_at = now
    stored.replaced_by_id = new_refresh.id
    await db.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    data: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke the given refresh token (or all of the user's sessions).

    Access tokens are short-lived and expire on their own; clients must
    discard them on logout.
    """
    now = datetime.now(timezone.utc)
    stmt = update(RefreshToken).where(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked_at.is_(None),
    )
    if not data.all_devices:
        if not data.refresh_token:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="refresh_token is required unless all_devices is true",
            )
        stmt = stmt.where(RefreshToken.token_hash == _hash_token(data.refresh_token))

    await db.execute(stmt.values(revoked_at=now))
    await db.commit()


@router.get("/me", response_model=CurrentUserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db_session),
):
    roles = await get_user_role_names(db, current_user.id)
    # School query is automatically restricted to the mentor's assignments.
    schools = (
        await db.execute(
            select(School)
            .where(School.deleted_at.is_(None))
            .order_by(School.name)
        )
    ).scalars().all()

    return CurrentUserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        role=MENTOR_ROLE,
        roles=sorted(roles),
        assigned_schools=[
            AssignedSchoolSummary(id=s.id, name=s.name, code=s.code, district=s.district)
            for s in schools
        ],
    )

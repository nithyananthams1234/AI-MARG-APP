
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

ACCESS_TOKEN_TYPE = "access"


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    roles: list[str] | None = None,
) -> str:
    now = datetime.now(timezone.utc)

    expires_at = now + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expires_at,
        "jti": uuid.uuid4().hex,
        "typ": ACCESS_TOKEN_TYPE,
        # Informational only: authorisation always re-reads roles from the DB.
        "roles": roles or [],
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat", "sub"]},
    )
    # Tokens issued before typed tokens existed carry no "typ"; accept those,
    # but never accept a token explicitly typed as something else.
    if payload.get("typ", ACCESS_TOKEN_TYPE) != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Not an access token")
    return payload

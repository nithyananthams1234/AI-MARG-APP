
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessScope, load_assigned_school_ids, set_scope
from app.auth.dependencies import get_current_user
from app.database.session import get_db_session
from app.models.identity import Role, User, UserRole

MENTOR_ROLE = "Mentor"
ADMIN_ROLE = "Administrator"


async def get_user_role_names(db: AsyncSession, user_id) -> set[str]:
    result = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return set(result.scalars().all())


async def get_current_mentor(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    roles = await get_user_role_names(db, current_user.id)

    if MENTOR_ROLE not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mentor access required",
        )

    # Restrict every subsequent query in this request to the mentor's
    # actively assigned schools / owned records (see app.auth.access).
    school_ids = await load_assigned_school_ids(db, current_user.id)
    set_scope(db, AccessScope(user_id=current_user.id, school_ids=school_ids))

    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """System administration (school assignments). Not a mentor workflow."""
    roles = await get_user_role_names(db, current_user.id)

    if ADMIN_ROLE not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )

    set_scope(db, AccessScope(user_id=current_user.id, unrestricted=True))
    return current_user

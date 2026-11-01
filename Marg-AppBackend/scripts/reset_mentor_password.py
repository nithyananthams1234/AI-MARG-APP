from __future__ import annotations

import asyncio
import getpass
import sys
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.auth.hashing import hash_password, verify_password
from app.auth.role_dependencies import MENTOR_ROLE, get_user_role_names
from app.database.session import AsyncSessionLocal, engine
from app.models.identity import User

TARGET_ID = UUID("bb662d24-bf3f-4623-b3ae-0ce02a70cb75")


async def reset_password(password: str) -> None:
    if engine.url.database != "marg_db":
        raise RuntimeError("Refusing to reset: configured database is not marg_db.")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.id == TARGET_ID,
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise RuntimeError("Refusing to reset: the selected account was not found.")
        if not user.is_active or user.deleted_at is not None:
            raise RuntimeError("Refusing to reset: the selected account is not active.")

        roles = await get_user_role_names(db, user.id)
        if MENTOR_ROLE not in roles:
            raise RuntimeError("Refusing to reset: the selected account is not a mentor.")

        new_hash = hash_password(password)
        if not verify_password(password, new_hash):
            raise RuntimeError("Password verification failed before update.")

        result = await db.execute(
            update(User)
            .where(User.id == TARGET_ID)
            .values(password_hash=new_hash)
        )
        if result.rowcount != 1:
            raise RuntimeError("Refusing to commit: exactly one account was not updated.")

        stored_hash = await db.scalar(
            select(User.password_hash).where(
                User.id == TARGET_ID,
            )
        )
        if stored_hash is None or not verify_password(password, stored_hash):
            raise RuntimeError("Stored password verification failed; update rolled back.")

        await db.commit()


def main() -> int:
    password = getpass.getpass("Enter new mentor password (input hidden): ")
    confirmation = getpass.getpass("Confirm new mentor password (input hidden): ")
    if not password:
        print("RESET_FAILED: Password must not be empty.")
        return 1
    if password != confirmation:
        print("RESET_FAILED: Password entries did not match.")
        return 1

    try:
        asyncio.run(reset_password(password))
    except RuntimeError as exc:
        print(f"RESET_FAILED: {exc}")
        return 1
    except SQLAlchemyError as exc:
        print(f"RESET_FAILED: {type(exc).__name__}")
        return 1

    print(f"RESET_SUCCEEDED: password updated for mentor account {TARGET_ID}.")
    print("PASSWORD_AUTH_CHECK=PASS (backend verifier and active Mentor role confirmed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Database safety guard.

The PostgreSQL server also hosts the MARG application database (``marg_db``). The engine must never
connect to it. This guard is applied before connecting, after connecting, and in Alembic.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class DatabaseGuardError(RuntimeError):
    pass


def check_database_name(db_name: str, forbidden: set[str]) -> None:
    if db_name.strip().lower() in {f.lower() for f in forbidden}:
        raise DatabaseGuardError(f"Refusing to use forbidden database {db_name!r}")


async def verify_postgres_target(
    conn: AsyncConnection, expected_db: str, expected_schema: str
) -> dict[str, str]:
    row = (await conn.execute(text("SELECT current_database(), current_schema(), current_user"))).one()
    current_db, current_schema, current_user = row[0], row[1], row[2]
    if current_db != expected_db:
        raise DatabaseGuardError(f"Connected to database {current_db!r}, expected {expected_db!r}")
    if current_schema != expected_schema:
        raise DatabaseGuardError(
            f"Active schema is {current_schema!r}, expected {expected_schema!r}. "
            "Check that the schema exists and is owned by the application role."
        )
    return {"database": current_db, "schema": current_schema, "user": current_user}

"""Alembic environment for the Mentor Intelligence Engine database.

Safety: the database URL is built from settings (never stored in alembic.ini). Before running any
migration the guard refuses forbidden database names (e.g. ``marg_db``) and verifies the connected
database and schema. The version table lives in the engine schema.

Options:
  alembic upgrade head                      -> schema DB_SCHEMA (default: mie)
  alembic -x schema=mie_test upgrade head   -> test schema
  alembic -x sqlite_url=sqlite+aiosqlite:///./x.db revision --autogenerate -m "..."  (offline generation)
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  (register models)
from app.config import get_settings
from app.db.base import Base
from app.db.guard import DatabaseGuardError, check_database_name
from app.db.session import postgres_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
x_args = context.get_x_argument(as_dictionary=True)


def _do_run(connection: Connection, schema: str | None) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=schema,
        compare_type=True,
        render_as_batch=schema is None,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    if "sqlite_url" in x_args:
        engine = create_async_engine(x_args["sqlite_url"], poolclass=pool.NullPool)
        async with engine.connect() as connection:
            await connection.run_sync(_do_run, None)
        await engine.dispose()
        return

    settings = get_settings()
    schema = x_args.get("schema", settings.db_schema)
    if schema not in {settings.db_schema, settings.db_test_schema}:
        raise DatabaseGuardError(f"Schema {schema!r} is not an approved engine schema")
    check_database_name(settings.db_name, settings.forbidden_db_names)
    engine = create_async_engine(
        postgres_url(settings),
        poolclass=pool.NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with engine.connect() as connection:
        row = (await connection.exec_driver_sql("SELECT current_database(), current_schema()")).one()
        if row[0] != settings.db_name:
            raise DatabaseGuardError(f"Connected to {row[0]!r}, expected {settings.db_name!r}")
        if row[1] != schema:
            raise DatabaseGuardError(
                f"Active schema is {row[1]!r}, expected {schema!r} (does the schema exist?)"
            )
        print(f"[migrations] target verified: database={row[0]} schema={row[1]}")
        await connection.run_sync(_do_run, schema)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline SQL generation is not supported; run migrations against the verified database.")
asyncio.run(run_async_migrations())

"""Async engine and session management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import URL, event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import DbBackend, Settings
from app.db.base import Base
from app.db.guard import check_database_name, verify_postgres_target


def postgres_url(settings: Settings) -> URL:
    check_database_name(settings.db_name, settings.forbidden_db_names)
    return URL.create(
        "postgresql+asyncpg",
        username=settings.db_user,
        password=settings.db_password.get_secret_value() if settings.db_password else None,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


class Database:
    def __init__(self, engine: AsyncEngine, *, kind: DbBackend, expected_db: str | None, schema: str | None):
        self.engine = engine
        self.kind = kind
        self.expected_db = expected_db
        self.schema = schema
        self.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    # ------------------------------------------------------------ constructors
    @classmethod
    def from_settings(cls, settings: Settings, *, schema: str | None = None) -> Database:
        if settings.db_backend is DbBackend.sqlite:
            return cls.sqlite(f"sqlite+aiosqlite:///{settings.sqlite_path}")
        schema = schema or settings.db_schema
        engine = create_async_engine(
            postgres_url(settings),
            pool_pre_ping=True,
            connect_args={"server_settings": {"search_path": schema, "application_name": "marg_mie"}},
        )
        return cls(engine, kind=DbBackend.postgres, expected_db=settings.db_name, schema=schema)

    @classmethod
    def sqlite(cls, url: str = "sqlite+aiosqlite://") -> Database:
        kwargs: dict[str, object] = {}
        if url in {"sqlite+aiosqlite://", "sqlite+aiosqlite:///:memory:"}:
            kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
        engine = create_async_engine(url, **kwargs)

        @event.listens_for(engine.sync_engine, "connect")
        def _fk_on(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return cls(engine, kind=DbBackend.sqlite, expected_db=None, schema=None)

    # ------------------------------------------------------------ operations
    async def verify(self) -> dict[str, str]:
        """Connect and run the safety guard. Returns a safe description of the target."""
        async with self.engine.connect() as conn:
            if self.kind is DbBackend.postgres:
                assert self.expected_db and self.schema
                return await verify_postgres_target(conn, self.expected_db, self.schema)
            await conn.exec_driver_sql("SELECT 1")
            return {"database": "sqlite (local development)", "schema": "-", "user": "-"}

    async def create_all(self) -> None:
        """Create tables directly. Used for SQLite and tests; PostgreSQL uses Alembic migrations."""
        import app.models  # noqa: F401  (register models)

        if self.kind is DbBackend.postgres:
            await self.verify()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()

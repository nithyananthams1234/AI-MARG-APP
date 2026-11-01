
from collections.abc import AsyncGenerator

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Importing registers the global ORM event hooks (access scoping, versioning).
from app.auth import access as _access  # noqa: F401
from app.database import events as _events  # noqa: F401


# Create the PostgreSQL database engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    **(
        {"poolclass": NullPool}
        if settings.database_nullpool
        else {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 10}
    ),
)


# Create an asynchronous session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# Database session dependency for FastAPI.
# Request sessions are marked so that row-level access scoping applies
# (deny-by-default until an authenticated scope is attached).
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        _access.mark_request_session(session)
        yield session

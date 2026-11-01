"""PostgreSQL integration tests. Run explicitly:  uv run pytest -m postgres

Uses the configured database (must be marg_mentor_intelligence) and the TEST schema (DB_TEST_SCHEMA,
default mie_test). Tables in the test schema are created and dropped by the test; nothing else is touched.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.config import ConfigurationError, get_settings
from app.db.base import Base
from app.db.guard import DatabaseGuardError
from app.db.session import Database
from app.seed.demo_data import seed_demo_data
from tests.conftest import ANCHOR, MENTOR, build_container

pytestmark = pytest.mark.postgres


@pytest.fixture
async def pg_db():
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        pytest.skip(f"PostgreSQL not configured: {exc}")
    if settings.db_backend.value != "postgres":
        pytest.skip("DB_BACKEND is not postgres")
    db = Database.from_settings(settings, schema=settings.db_test_schema)
    info = await db.verify()
    assert info["database"] == settings.db_name == "marg_mentor_intelligence"
    assert info["schema"] == settings.db_test_schema
    import app.models  # noqa: F401

    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await seed_demo_data(db, ANCHOR)
    yield settings, db
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db.dispose()


async def test_guard_and_end_to_end_on_postgres(pg_db):
    settings, db = pg_db
    async with db.engine.connect() as conn:
        assert (await conn.execute(text("SELECT current_database()"))).scalar() == "marg_mentor_intelligence"
    c = build_container(settings.model_copy(update={"ai_enabled": False}), db)
    view = await c.orchestrator.run("daily_planning", {"mentor_ref": "MEN-001"}, MENTOR)
    assert view.status.value == "completed"
    sched = await c.orchestrator.run("schedule_intelligence", {"mentor_ref": "MEN-001"}, MENTOR)
    import uuid

    pid = uuid.UUID(sched.result["proposals"][0]["proposal_id"])
    assert (await c.approvals.approve(MENTOR, pid))["status"] == "executed"


async def test_wrong_schema_is_detected(pg_db):
    settings, _ = pg_db
    db = Database.from_settings(settings, schema="schema_that_does_not_exist")
    with pytest.raises(DatabaseGuardError):
        await db.verify()
    await db.dispose()

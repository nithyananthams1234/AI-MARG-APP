"""
Backend test fixtures.

Tests run against the dedicated PostgreSQL database named ``marg_test``.
Every test starts from empty tables. TEST_DATABASE_URL must be provided
separately so tests never inherit runtime database credentials from .env.
A hard guard refuses to run against any other database name.
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

# --------------------------------------------------------------------------
# Configure the environment BEFORE importing the application.
# --------------------------------------------------------------------------
_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
_test_url = os.environ.get("TEST_DATABASE_URL")
if not _test_url:
    raise RuntimeError(
        "TEST_DATABASE_URL must point to the dedicated marg_test database; "
        "runtime DATABASE_URL is not used for tests"
    )

if make_url(_test_url).database != "marg_test":
    raise RuntimeError("Refusing to run tests against a database not named 'marg_test'")

os.environ["DATABASE_URL"] = _test_url
os.environ["DATABASE_NULLPOOL"] = "true"
os.environ.setdefault("JWT_SECRET_KEY", _env.get("JWT_SECRET_KEY") or "test-secret-" + "x" * 40)
os.environ["APP_ENV"] = "test"
os.environ["AI_PROVIDER"] = "classroom_coach"
os.environ["CLASSROOM_COACH_URL"] = "http://coach.invalid"
os.environ["AI_INLINE_PROCESSING"] = "true"

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.auth import rate_limit  # noqa: E402
from app.auth.hashing import hash_password  # noqa: E402
from app.database.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Classroom,
    MentorSchool,
    Role,
    School,
    SchoolTeacher,
    Teacher,
    User,
    UserRole,
)

PASSWORD = "Test-Password-123!"


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _reset_database() -> None:
    async with engine.begin() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename <> 'alembic_version'"
                )
            )
        ).scalars().all()
        if tables:
            await conn.execute(
                text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE")
            )


@pytest.fixture
async def world(anyio_backend):
    """Two mentors with one school each, one administrator, teachers and classrooms."""
    await _reset_database()
    rate_limit.reset_all()

    async with AsyncSessionLocal() as db:
        roles = {name: Role(name=name) for name in ("Mentor", "Supervisor", "Administrator")}
        db.add_all(roles.values())

        mentor_a = User(full_name="Mentor A", email="mentor.a@test.marg", password_hash=hash_password(PASSWORD), is_active=True)
        mentor_b = User(full_name="Mentor B", email="mentor.b@test.marg", password_hash=hash_password(PASSWORD), is_active=True)
        admin = User(full_name="Admin", email="admin@test.marg", password_hash=hash_password(PASSWORD), is_active=True)
        supervisor = User(full_name="Supervisor", email="sup@test.marg", password_hash=hash_password(PASSWORD), is_active=True)
        db.add_all([mentor_a, mentor_b, admin, supervisor])
        await db.flush()
        db.add_all(
            [
                UserRole(user_id=mentor_a.id, role_id=roles["Mentor"].id),
                UserRole(user_id=mentor_b.id, role_id=roles["Mentor"].id),
                UserRole(user_id=admin.id, role_id=roles["Administrator"].id),
                UserRole(user_id=supervisor.id, role_id=roles["Supervisor"].id),
            ]
        )

        school_a = School(name="Test School A", code="TSA", district="District A", state="Tamil Nadu", is_active=True)
        school_b = School(name="Test School B", code="TSB", district="District B", state="Tamil Nadu", is_active=True)
        db.add_all([school_a, school_b])
        await db.flush()

        db.add_all(
            [
                MentorSchool(user_id=mentor_a.id, school_id=school_a.id, assigned_from=date(2026, 1, 1), is_active=True),
                MentorSchool(user_id=mentor_b.id, school_id=school_b.id, assigned_from=date(2026, 1, 1), is_active=True),
            ]
        )

        teacher_a = Teacher(full_name="Teacher A", employee_code="T-A", is_active=True)
        teacher_b = Teacher(full_name="Teacher B", employee_code="T-B", is_active=True)
        db.add_all([teacher_a, teacher_b])
        await db.flush()
        db.add_all(
            [
                SchoolTeacher(school_id=school_a.id, teacher_id=teacher_a.id, is_active=True),
                SchoolTeacher(school_id=school_b.id, teacher_id=teacher_b.id, is_active=True),
            ]
        )
        class_a = Classroom(school_id=school_a.id, name="6-A", grade="6", section="A", academic_year="2026-27", capacity=40)
        class_b = Classroom(school_id=school_b.id, name="7-B", grade="7", section="B", academic_year="2026-27", capacity=40)
        db.add_all([class_a, class_b])
        await db.commit()

        ids = {
            "mentor_a": mentor_a.id,
            "mentor_b": mentor_b.id,
            "admin": admin.id,
            "school_a": school_a.id,
            "school_b": school_b.id,
            "teacher_a": teacher_a.id,
            "teacher_b": teacher_b.id,
            "class_a": class_a.id,
            "class_b": class_b.id,
        }
    return ids


@pytest.fixture
async def client(anyio_backend):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> dict:
    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


async def auth_headers(client: httpx.AsyncClient, email: str) -> dict:
    tokens = await login(client, email)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def new_key() -> str:
    return uuid.uuid4().hex

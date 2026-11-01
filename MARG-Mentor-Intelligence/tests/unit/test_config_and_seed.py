import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config import Settings
from app.models import domain as m
from app.schemas.common import (
    ActionPlanStatus,
    AIJobStatus,
    FollowUpStatus,
    Priority,
    ProposalStatus,
    TaskStatus,
    VisitStatus,
)
from tests.conftest import make_settings


def test_ai_enabled_requires_key_and_model():
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        make_settings(ai_enabled=True, ai_provider="anthropic", anthropic_model="m")
    with pytest.raises(ValidationError, match="ANTHROPIC_MODEL"):
        make_settings(ai_enabled=True, ai_provider="anthropic", anthropic_api_key="sk-ant-test-key")
    assert make_settings(
        ai_enabled=True, ai_provider="anthropic", anthropic_api_key="sk-ant-test-key", anthropic_model="m"
    ).ai_enabled


def test_nvidia_provider_requires_key_and_model():
    with pytest.raises(ValidationError, match="NVIDIA_API_KEY"):
        make_settings(ai_enabled=True, ai_provider="nvidia", nvidia_model="nvidia/test-model")
    with pytest.raises(ValidationError, match="NVIDIA_MODEL"):
        make_settings(ai_enabled=True, ai_provider="nvidia", nvidia_api_key="nvidia-test-key", nvidia_model="")
    settings = make_settings(
        ai_enabled=True,
        ai_provider="nvidia",
        nvidia_api_key="nvidia-test-key",
        nvidia_model="nvidia/test-model",
    )
    assert settings.ai_provider == "nvidia"
    assert "nvidia-test-key" not in str(settings.describe())


@pytest.mark.parametrize("name", ["marg_db", "MARG_DB", "postgres"])
def test_forbidden_database_names(name):
    with pytest.raises(ValidationError, match="forbidden"):
        make_settings(db_name=name)


def test_marg_backend_mode_requires_service_key():
    with pytest.raises(ValidationError, match="MARG_BACKEND_SERVICE_KEY"):
        make_settings(backend_mode="marg")
    s = make_settings(backend_mode="marg", marg_backend_service_key="svc-key-" + "x" * 24)
    assert s.backend_mode.value == "marg"


def test_trusted_gateway_requires_engine_api_key():
    with pytest.raises(ValidationError, match="ENGINE_API_KEY"):
        make_settings(trusted_gateway_identity=True)


def test_dev_header_refused_in_production():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            ai_enabled=False,
            dev_auth_header_enabled=True,
            pseudonymisation_key="x" * 40,
            db_password="p",
        )


def test_secrets_not_exposed():
    s = make_settings(
        ai_enabled=True,
        ai_provider="anthropic",
        anthropic_api_key="sk-ant-SUPERSECRET-123",
        anthropic_model="m",
    )
    assert "SUPERSECRET" not in repr(s)
    assert "SUPERSECRET" not in str(s.describe())
    assert "SUPERSECRET" not in s.model_dump_json()


def test_canonical_status_values_are_exact():
    assert [v.value for v in VisitStatus] == ["planned", "in_progress", "completed", "cancelled"]
    assert [v.value for v in TaskStatus] == ["pending", "in_progress", "completed", "cancelled"]
    assert [v.value for v in FollowUpStatus] == [
        "pending",
        "teacher_responded",
        "evidence_submitted",
        "mentor_verified",
        "needs_revision",
        "closed",
    ]
    assert [v.value for v in ActionPlanStatus] == [
        "draft",
        "pending_approval",
        "approved",
        "in_progress",
        "completed",
        "overdue",
        "cancelled",
    ]
    assert [v.value for v in Priority] == ["low", "medium", "high", "critical"]
    assert [v.value for v in AIJobStatus] == ["queued", "processing", "completed", "failed", "cancelled"]
    assert [v.value for v in ProposalStatus] == [
        "pending",
        "approved",
        "rejected",
        "expired",
        "executed",
        "execution_failed",
    ]


def test_no_model_ids_or_marg_db_hardcoded_in_application_code():
    root = Path(__file__).resolve().parents[2] / "app"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"claude-(opus|sonnet|haiku|fable)", text), f"model id hardcoded in {path}"
        if path.name not in {"config.py", "guard.py"}:  # forbidden-name list and guard documentation
            assert "marg_db" not in text, f"marg_db referenced in {path}"


async def test_seed_has_at_least_ten_records_per_dataset_and_is_labelled(db):
    async with db.session() as s:
        for model in (
            m.School,
            m.Teacher,
            m.Task,
            m.SchoolVisit,
            m.Observation,
            m.FollowUp,
            m.ActionPlan,
            m.ScheduleItem,
            m.WorkloadActivity,
        ):
            count = (await s.execute(select(func.count()).select_from(model))).scalar_one()
            assert count >= 10, model.__tablename__
            not_demo = (
                await s.execute(select(func.count()).select_from(model).where(model.is_demo.is_(False)))
            ).scalar_one()
            assert not_demo == 0
        names = (await s.execute(select(m.School.name))).scalars().all()
        assert all(n.endswith("(DEMO)") for n in names)

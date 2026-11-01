from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.common import Priority, TaskStatus
from app.schemas.records import TaskRecord
from app.services.priority import analyse_dependencies, classify, compute_priority, deadline_proximity

NOW = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)


def task(
    id="T1", u=80, i=60, r=40, due=NOW + timedelta(days=7), deps=(), status=TaskStatus.pending
) -> TaskRecord:
    return TaskRecord(
        id=id,
        title="t",
        description=None,
        category="x",
        status=status,
        due_at=due,
        estimated_minutes=30,
        urgency=u,
        impact=i,
        risk=r,
        depends_on=list(deps),
        school_ref=None,
        created_at=NOW,
        updated_at=NOW,
        completed_at=None,
    )


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, Priority.low),
        (24.99, Priority.low),
        (25, Priority.medium),
        (49.99, Priority.medium),
        (50, Priority.high),
        (74.99, Priority.high),
        (75, Priority.critical),
        (100, Priority.critical),
    ],
)
def test_classification_boundaries(score, expected):
    assert classify(score) == expected


def test_classify_rejects_out_of_range():
    with pytest.raises(ValueError):
        classify(100.1)


def test_deadline_proximity():
    assert deadline_proximity(NOW - timedelta(hours=1), NOW, 14) == 100.0
    assert deadline_proximity(NOW + timedelta(days=14), NOW, 14) == 0.0
    assert deadline_proximity(NOW + timedelta(days=7), NOW, 14) == 50.0
    assert deadline_proximity(None, NOW, 14) is None


def test_full_score_uses_exact_formula():
    t = task(u=80, i=60, r=40, due=NOW + timedelta(days=7))
    blocked = task(id="T2", deps=["T1"])
    res = compute_priority(t, NOW, [t, blocked], horizon_days=14, points_per_blocked_task=25)
    # 0.30*80 + 0.25*60 + 0.20*40 + 0.15*50 + 0.10*25 = 24 + 15 + 8 + 7.5 + 2.5 = 57.0
    assert res.status == "complete"
    assert res.score == 57.0
    assert res.priority == Priority.high
    assert res.missing_factors == []


def test_missing_factor_is_never_defaulted():
    t = task(u=None, r=None)
    res = compute_priority(t, NOW, [t], 14, 25)
    assert res.status == "incomplete"
    assert res.score is None and res.priority is None
    assert res.factors["urgency"] is None and res.factors["risk"] is None
    assert set(res.missing_factors) == {"urgency", "risk"}
    # bounds: known part only, and known + 100 * missing weights (0.30 + 0.20)
    known = 0.25 * 60 + 0.15 * 50
    assert res.score_bounds == (round(known, 2), round(known + 50, 2))


def test_missing_deadline_is_flagged_not_invented():
    res = compute_priority(task(due=None), NOW, [task(due=None)], 14, 25)
    assert res.status == "incomplete"
    assert "deadline_proximity" in res.missing_factors
    assert res.factor_sources["deadline_proximity"] == "due date not recorded"


def test_out_of_range_verified_value_rejected():
    with pytest.raises(ValueError):
        TaskRecord.model_validate(task().model_dump() | {"urgency": 120})


def test_dependency_analysis_detects_blocking_unknown_and_cycles():
    a, b = task(id="A", deps=["B"]), task(id="B", deps=["A"])
    c = task(id="C", deps=["ZZZ"])
    deps = analyse_dependencies([a, b, c])
    assert deps.blocked_by_open["A"] == ["B"]
    assert deps.unknown_references["C"] == ["ZZZ"]
    assert deps.cycles

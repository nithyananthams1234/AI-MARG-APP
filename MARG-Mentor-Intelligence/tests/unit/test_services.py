"""Deterministic services against the DEMO DATA snapshot."""

from datetime import timedelta

from app.services.followups import analyse_followups
from app.services.planning import build_day_plan
from app.services.schedule import calendar_entries, find_conflicts, find_visit_slot
from app.services.visits import school_attention
from app.services.workload import window_workload
from app.utils.datetime_utils import local_day_bounds
from tests.conftest import ANCHOR, FIXED_NOW


async def snapshot(container, mentor="MEN-001"):
    return await container.adapter.get_mentor_snapshot(mentor)


async def test_conflicts_detected_on_anchor_day(container):
    s = await snapshot(container)
    lo, hi = local_day_bounds(ANCHOR, container.settings.tz)
    conflicts = find_conflicts(s, calendar_entries(s, lo, hi))
    overlaps = {tuple(sorted(c.entries)) for c in conflicts if c.type == "overlap"}
    assert ("SCH-ITM-03", "VIS-009") in overlaps
    assert ("SCH-ITM-02", "SCH-ITM-03") in overlaps


async def test_full_day_training_conflicts_with_visit(container):
    s = await snapshot(container)
    lo, hi = local_day_bounds(ANCHOR + timedelta(days=2), container.settings.tz)
    conflicts = find_conflicts(s, calendar_entries(s, lo, hi))
    assert any(set(c.entries) == {"SCH-ITM-06", "VIS-011"} for c in conflicts)


async def test_no_visit_slot_when_travel_time_unknown(container):
    s = await snapshot(container)
    lo, hi = local_day_bounds(ANCHOR, container.settings.tz)
    assert (
        find_visit_slot(s, "SCH-010", 120, ANCHOR, 7, calendar_entries(s, lo, hi + timedelta(days=7))) is None
    )


async def test_workload_index_and_lower_bound(container):
    s = await snapshot(container)
    w = window_workload(s, ANCHOR, 7, FIXED_NOW, 80, 100)
    assert w.workload_index is not None
    assert w.index_is_lower_bound  # TSK-008 and WLA-007 have no estimates
    assert "TSK-005" in w.overdue_tasks
    assert any(d.date == ANCHOR + timedelta(days=2) and d.status == "overloaded" for d in w.per_day)
    assert w.metric_note.startswith("Administrative")


async def test_workload_unavailable_without_working_hours(container):
    s = await snapshot(container, "MEN-002")
    w = window_workload(s, ANCHOR, 7, FIXED_NOW, 80, 100)
    assert w.workload_index is None and w.status == "unknown"
    assert any(m.field == "working_hours" for m in w.missing_data)


async def test_followups_keep_progress_layers_separate(container):
    s = await snapshot(container)
    res = analyse_followups(s, FIXED_NOW)
    items = {i.followup_ref: i for i in res.items}
    assert items["FU-003"].progress.teacher_reported is not None
    assert items["FU-003"].progress.mentor_verified is None
    assert "evidence_missing" in items["FU-003"].flags
    assert items["FU-004"].category == "awaiting_mentor_verification"
    assert items["FU-005"].progress.mentor_verified is not None
    assert items["FU-001"].overdue
    # Instruction-like teacher text is preserved as unverified data and changes nothing.
    assert "IGNORE PREVIOUS INSTRUCTIONS" in items["FU-010"].progress.teacher_reported["text"]
    assert items["FU-010"].status.value == "teacher_responded"
    assert "due_date_not_recorded" in items["FU-011"].flags


async def test_school_attention_flags_missing_history(container):
    s = await snapshot(container)
    ranking = {a.school_ref: a for a in school_attention(s, FIXED_NOW)}
    assert "no_completed_visit_in_records" in ranking["SCH-009"].flags
    assert ranking["SCH-009"].components["days_since_last_visit"] is None
    assert not ranking["SCH-009"].score_complete


async def test_daily_plan_lists_items_that_cannot_fit(container):
    s = await snapshot(container)
    plan, _ = build_day_plan(s, ANCHOR, FIXED_NOW, 14, 25)
    reasons = {u.ref: u.reason for u in plan.unscheduled}
    assert reasons["TSK-008"] == "Time estimate not recorded"
    assert "Blocked by open dependency" in reasons["TSK-003"] or reasons["TSK-003"].startswith("Not enough")
    assert plan.capacity["available_minutes"] == 480
    placed = [i for i in plan.timeline if i.source == "placed_by_engine"]
    for a in plan.timeline:  # placed items never overlap fixed calendar items
        for b in placed:
            if a is not b and a.source == "calendar":
                assert b.end <= a.start or b.start >= a.end


async def test_daily_plan_without_working_hours(container):
    s = await snapshot(container, "MEN-002")
    plan, _ = build_day_plan(s, ANCHOR, FIXED_NOW, 14, 25)
    assert plan.working_window is None
    assert plan.note and "Working hours are not recorded" in plan.note

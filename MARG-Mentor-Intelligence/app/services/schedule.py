"""Deterministic calendar analysis: entries, conflicts, working windows and free slots.

Travel time is used only when recorded. Missing travel data or school availability is reported,
never invented.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.schemas.common import MissingData, VisitStatus
from app.schemas.records import MentorSnapshot
from app.utils.datetime_utils import at_local, local_day_bounds, minutes_between, overlap_minutes


class CalendarEntry(BaseModel):
    ref: str
    kind: str  # school_visit | meeting | training | ...
    title: str
    start: datetime
    end: datetime
    school_ref: str | None = None
    movable: bool = False


class Conflict(BaseModel):
    type: str  # overlap | outside_working_hours | non_working_day | school_unavailable | travel_gap
    severity: str  # high | medium | info
    entries: list[str]
    detail: str
    overlap_minutes: int | None = None


class Slot(BaseModel):
    start: datetime
    end: datetime
    minutes: int


def working_window(snapshot: MentorSnapshot, day: date) -> tuple[datetime, datetime] | None:
    mentor = snapshot.mentor
    if mentor.work_start is None or mentor.work_end is None or mentor.working_days is None:
        return None
    if day.isoweekday() not in mentor.working_days:
        return None
    tz = ZoneInfo(mentor.timezone)
    return at_local(day, mentor.work_start, tz), at_local(day, mentor.work_end, tz)


def working_hours_missing(snapshot: MentorSnapshot) -> list[MissingData]:
    m = snapshot.mentor
    missing = []
    for field, value in (
        ("work_start", m.work_start),
        ("work_end", m.work_end),
        ("working_days", m.working_days),
    ):
        if value is None:
            missing.append(
                MissingData(
                    entity_type="mentor",
                    entity_ref=m.id,
                    field=field,
                    impact="Available working time cannot be calculated",
                )
            )
    return missing


def calendar_entries(snapshot: MentorSnapshot, start: datetime, end: datetime) -> list[CalendarEntry]:
    entries: list[CalendarEntry] = []
    for v in snapshot.visits:
        if (
            v.status in (VisitStatus.planned, VisitStatus.in_progress)
            and v.scheduled_end > start
            and v.scheduled_start < end
        ):
            school = snapshot.school(v.school_ref)
            entries.append(
                CalendarEntry(
                    ref=v.id,
                    kind="school_visit",
                    title=f"Visit: {school.name if school else v.school_ref}",
                    start=v.scheduled_start,
                    end=v.scheduled_end,
                    school_ref=v.school_ref,
                    movable=v.status == VisitStatus.planned,
                )
            )
    for item in snapshot.schedule_items:
        if item.end_at > start and item.start_at < end:
            entries.append(
                CalendarEntry(
                    ref=item.id,
                    kind=item.kind,
                    title=item.title,
                    start=item.start_at,
                    end=item.end_at,
                    school_ref=item.school_ref,
                )
            )
    return sorted(entries, key=lambda e: (e.start, e.end))


def find_conflicts(snapshot: MentorSnapshot, entries: list[CalendarEntry]) -> list[Conflict]:
    tz = ZoneInfo(snapshot.mentor.timezone)
    conflicts: list[Conflict] = []
    for i, a in enumerate(entries):
        for b in entries[i + 1 :]:
            if b.start >= a.end:
                break
            mins = overlap_minutes(a.start, a.end, b.start, b.end)
            if mins > 0:
                conflicts.append(
                    Conflict(
                        type="overlap",
                        severity="high",
                        entries=[a.ref, b.ref],
                        overlap_minutes=mins,
                        detail=f"'{a.title}' and '{b.title}' overlap by {mins} minutes",
                    )
                )
    for e in entries:
        day = e.start.astimezone(tz).date()
        window = working_window(snapshot, day)
        if snapshot.mentor.working_days is not None and day.isoweekday() not in snapshot.mentor.working_days:
            conflicts.append(
                Conflict(
                    type="non_working_day",
                    severity="medium",
                    entries=[e.ref],
                    detail=f"'{e.title}' is scheduled on a non-working day",
                )
            )
        elif window and (e.start < window[0] or e.end > window[1]):
            conflicts.append(
                Conflict(
                    type="outside_working_hours",
                    severity="medium",
                    entries=[e.ref],
                    detail=f"'{e.title}' extends outside recorded working hours",
                )
            )
        if e.kind == "school_visit" and e.school_ref:
            school = snapshot.school(e.school_ref)
            if school and school.available_days is not None and day.isoweekday() not in school.available_days:
                conflicts.append(
                    Conflict(
                        type="school_unavailable",
                        severity="high",
                        entries=[e.ref],
                        detail=f"{school.name} is not recorded as available on this weekday",
                    )
                )
    # Consecutive entries at different schools on the same day: travel time between schools is not recorded.
    for a, b in zip(entries, entries[1:], strict=False):
        same_day = a.end.astimezone(tz).date() == b.start.astimezone(tz).date()
        if same_day and a.school_ref and b.school_ref and a.school_ref != b.school_ref and b.start >= a.end:
            conflicts.append(
                Conflict(
                    type="travel_gap",
                    severity="info",
                    entries=[a.ref, b.ref],
                    detail=(
                        f"{minutes_between(a.end, b.start)} minutes between locations; school-to-school "
                        "travel time is not recorded, so feasibility cannot be verified"
                    ),
                )
            )
    return conflicts


def travel_buffer(snapshot: MentorSnapshot, school_ref: str | None) -> int | None:
    school = snapshot.school(school_ref)
    return school.travel_minutes_from_base if school else None


def free_slots(
    snapshot: MentorSnapshot, day: date, entries: list[CalendarEntry], min_minutes: int = 15
) -> list[Slot]:
    window = working_window(snapshot, day)
    if window is None:
        return []
    start, end = window
    busy = sorted((max(e.start, start), min(e.end, end)) for e in entries if e.end > start and e.start < end)
    slots: list[Slot] = []
    cursor = start
    for b_start, b_end in busy:
        if b_start > cursor and minutes_between(cursor, b_start) >= min_minutes:
            slots.append(Slot(start=cursor, end=b_start, minutes=minutes_between(cursor, b_start)))
        cursor = max(cursor, b_end)
    if end > cursor and minutes_between(cursor, end) >= min_minutes:
        slots.append(Slot(start=cursor, end=end, minutes=minutes_between(cursor, end)))
    return slots


def _round_up_quarter(moment: datetime) -> datetime:
    """Round up to the next quarter hour (keeps suggested times practical)."""
    moment = moment.replace(second=0, microsecond=0)
    extra = (-moment.minute) % 15
    return moment + timedelta(minutes=extra)


def find_visit_slot(
    snapshot: MentorSnapshot,
    school_ref: str,
    duration_minutes: int,
    from_day: date,
    days: int,
    entries: list[CalendarEntry],
    not_before: datetime | None = None,
) -> tuple[datetime, datetime] | None:
    """Earliest slot that fits the visit plus recorded travel each way, on a day the school is available."""
    school = snapshot.school(school_ref)
    if school is None or school.travel_minutes_from_base is None:
        return None
    travel = school.travel_minutes_from_base
    tz = ZoneInfo(snapshot.mentor.timezone)
    for offset in range(days):
        day = from_day + timedelta(days=offset)
        if school.available_days is not None and day.isoweekday() not in school.available_days:
            continue
        day_start, day_end = local_day_bounds(day, tz)
        day_entries = [e for e in entries if e.end > day_start and e.start < day_end]
        for slot in free_slots(snapshot, day, day_entries):
            start = slot.start + timedelta(minutes=travel)
            if not_before and start < not_before:
                start = not_before
            start = _round_up_quarter(start)
            end = start + timedelta(minutes=duration_minutes)
            if end + timedelta(minutes=travel) <= slot.end:
                return start, end
    return None

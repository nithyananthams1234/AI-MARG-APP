"""Timezone helpers. Store UTC; compute working windows in the mentor's local timezone."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(UTC)


def local_date(moment: datetime, tz: ZoneInfo) -> date:
    return moment.astimezone(tz).date()


def at_local(day: date, clock: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, clock, tzinfo=tz).astimezone(UTC)


def local_day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = at_local(day, time(0, 0), tz)
    return start, at_local(day + timedelta(days=1), time(0, 0), tz)


def minutes_between(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def overlap_minutes(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> int:
    return minutes_between(max(a_start, b_start), min(a_end, b_end))


def fmt_local(moment: datetime | None, tz: ZoneInfo) -> str | None:
    return moment.astimezone(tz).isoformat() if moment else None

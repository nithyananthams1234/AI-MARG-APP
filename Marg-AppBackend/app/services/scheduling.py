
from datetime import datetime, timedelta, timezone


def calculate_visit_duration_minutes(
    start_at: datetime,
    end_at: datetime,
) -> int:
    """Calculate the duration of a school visit in minutes."""

    if start_at.tzinfo is None or end_at.tzinfo is None:
        raise ValueError("Both datetimes must include timezone information.")

    if end_at <= start_at:
        raise ValueError("End time must be later than start time.")

    duration = (end_at - start_at).total_seconds() / 60

    return int(duration)


def calculate_daily_workload(
    visit_durations: list[int],
) -> dict:
    """Calculate total scheduled visit time and workload."""

    if any(
        not isinstance(duration, int)
        or isinstance(duration, bool)
        or duration < 0
        for duration in visit_durations
    ):
        raise ValueError("Visit durations must be non-negative integers.")

    total_minutes = sum(visit_durations)

    return {
        "total_visits": len(visit_durations),
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 2),
    }


def detect_schedule_overlap(
    new_start: datetime,
    new_end: datetime,
    existing_schedules: list[tuple[datetime, datetime]],
) -> bool:
    """Check whether a proposed schedule overlaps existing schedules."""

    if new_start.tzinfo is None or new_end.tzinfo is None:
        raise ValueError("Schedule datetimes must include timezone information.")

    if new_end <= new_start:
        raise ValueError("End time must be later than start time.")

    for existing_start, existing_end in existing_schedules:
        if existing_start.tzinfo is None or existing_end.tzinfo is None:
            raise ValueError("Existing schedule datetimes must include timezones.")

        if new_start < existing_end and new_end > existing_start:
            return True

    return False

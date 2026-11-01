
from datetime import date
from uuid import UUID

from pydantic import BaseModel


class SchoolReportResponse(BaseModel):
    school_id: UUID
    school_name: str
    total_visits: int
    completed_visits: int
    total_observations: int
    total_learning_gaps: int
    open_learning_gaps: int = 0
    total_action_plans: int
    completed_action_plans: int
    open_follow_ups: int = 0


class MentorDashboardResponse(BaseModel):
    total_schools: int
    total_visits: int
    completed_visits: int
    pending_tasks: int
    completed_tasks: int
    total_learning_gaps: int
    total_action_plans: int
    # Added for the mentor dashboard; all computed from database records.
    upcoming_visits: int = 0
    overdue_tasks: int = 0
    total_observations: int = 0
    recommendations_awaiting_review: int = 0
    active_action_plans: int = 0
    open_follow_ups: int = 0
    follow_ups_awaiting_verification: int = 0
    unread_notifications: int = 0


class LearningGapReportItem(BaseModel):
    school_id: UUID
    school_name: str
    total_learning_gaps: int
    critical_severity: int = 0
    high_severity: int
    medium_severity: int
    low_severity: int
    resolved: int = 0


class ActivityDay(BaseModel):
    day: date
    visits_completed: int
    observations_recorded: int
    tasks_completed: int


class ActivityReportResponse(BaseModel):
    start_date: date
    end_date: date
    days: list[ActivityDay]


class DateRangeRequest(BaseModel):
    start_date: date
    end_date: date

"""Port for operational data access.

Agents and the orchestrator never read or write operational records directly; they go through
this interface. The only implementation today is the DEMO adapter. A MARG HTTP adapter will be
implemented after the MARG OpenAPI compatibility audit - no MARG endpoints are assumed here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.schemas.records import MentorSnapshot


class AdapterError(Exception):
    pass


class RecordNotFound(AdapterError):
    pass


class MentorDataAdapter(ABC):
    @abstractmethod
    async def list_mentors(self) -> list[dict[str, str]]: ...

    @abstractmethod
    async def get_mentor_snapshot(self, mentor_ref: str) -> MentorSnapshot: ...

    # Write operations: called only by the approval engine after an approved proposal.
    @abstractmethod
    async def reschedule_visit(
        self, mentor_ref: str, visit_ref: str, start: datetime, end: datetime
    ) -> dict: ...

    @abstractmethod
    async def schedule_visit(
        self, mentor_ref: str, school_ref: str, start: datetime, end: datetime, purpose: str
    ) -> dict: ...

    @abstractmethod
    async def update_task_due_date(self, mentor_ref: str, task_ref: str, due_at: datetime) -> dict: ...

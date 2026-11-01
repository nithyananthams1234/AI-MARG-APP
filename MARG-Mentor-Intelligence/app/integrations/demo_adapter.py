"""DEMO DATA adapter - DEVELOPMENT ONLY.

Reads and writes the synthetic DEMO DATA stored in the engine's own database. Every snapshot is
marked ``data_source="demo"`` and ``is_demo=True``. It must never be presented as production data,
and it is never used as a silent fallback for a failing MARG backend.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.db.session import Database
from app.integrations.base_adapter import MentorDataAdapter, RecordNotFound
from app.models import domain as m
from app.schemas.common import DataSource, VisitStatus
from app.schemas.records import (
    ActionPlanRecord,
    FollowUpRecord,
    MentorRecord,
    MentorSnapshot,
    ObservationRecord,
    ScheduleItemRecord,
    SchoolRecord,
    TaskRecord,
    TeacherRecord,
    VisitRecord,
    WorkloadActivityRecord,
)

logger = logging.getLogger(__name__)


class DemoDataAdapter(MentorDataAdapter):
    def __init__(self, db: Database):
        self._db = db
        logger.warning("DEMO DATA adapter active - development data only, not production records")

    async def list_mentors(self) -> list[dict[str, str]]:
        async with self._db.session() as s:
            rows = (await s.execute(select(m.Mentor).order_by(m.Mentor.id))).scalars().all()
        return [
            {"mentor_ref": r.id, "name": r.name, "role_title": r.role_title, "data_source": "demo"}
            for r in rows
        ]

    async def get_mentor_snapshot(self, mentor_ref: str) -> MentorSnapshot:
        async with self._db.session() as s:
            mentor = await s.get(m.Mentor, mentor_ref)
            if mentor is None:
                raise RecordNotFound(f"Mentor {mentor_ref!r} not found")

            async def rows(model: Any, *where: Any) -> list[Any]:
                return list((await s.execute(select(model).where(*where).order_by(model.id))).scalars().all())

            schools = await rows(m.School, m.School.mentor_ref == mentor_ref)
            school_ids = [x.id for x in schools]
            teachers = await rows(m.Teacher, m.Teacher.school_ref.in_(school_ids)) if school_ids else []
            return MentorSnapshot(
                data_source=DataSource.demo,
                is_demo=True,
                mentor=MentorRecord.model_validate(mentor),
                schools=[SchoolRecord.model_validate(x) for x in schools],
                teachers=[TeacherRecord.model_validate(x) for x in teachers],
                tasks=[
                    TaskRecord.model_validate(x) for x in await rows(m.Task, m.Task.mentor_ref == mentor_ref)
                ],
                visits=[
                    VisitRecord.model_validate(x)
                    for x in await rows(m.SchoolVisit, m.SchoolVisit.mentor_ref == mentor_ref)
                ],
                observations=[
                    ObservationRecord.model_validate(x)
                    for x in await rows(m.Observation, m.Observation.mentor_ref == mentor_ref)
                ],
                action_plans=[
                    ActionPlanRecord.model_validate(x)
                    for x in await rows(m.ActionPlan, m.ActionPlan.mentor_ref == mentor_ref)
                ],
                followups=[
                    FollowUpRecord.model_validate(x)
                    for x in await rows(m.FollowUp, m.FollowUp.mentor_ref == mentor_ref)
                ],
                schedule_items=[
                    ScheduleItemRecord.model_validate(x)
                    for x in await rows(m.ScheduleItem, m.ScheduleItem.mentor_ref == mentor_ref)
                ],
                workload_activities=[
                    WorkloadActivityRecord.model_validate(x)
                    for x in await rows(m.WorkloadActivity, m.WorkloadActivity.mentor_ref == mentor_ref)
                ],
            )

    async def reschedule_visit(self, mentor_ref: str, visit_ref: str, start: datetime, end: datetime) -> dict:
        async with self._db.session() as s:
            visit = await s.get(m.SchoolVisit, visit_ref)
            if visit is None or visit.mentor_ref != mentor_ref:
                raise RecordNotFound(f"Visit {visit_ref!r} not found for this mentor")
            if visit.status != VisitStatus.planned:
                raise ValueError(f"Only planned visits can be rescheduled (status is {visit.status})")
            previous = {"start": visit.scheduled_start.isoformat(), "end": visit.scheduled_end.isoformat()}
            visit.scheduled_start, visit.scheduled_end = start, end
            await s.commit()
        return {
            "visit_ref": visit_ref,
            "previous": previous,
            "new": {"start": start.isoformat(), "end": end.isoformat()},
            "data_source": "demo",
        }

    async def schedule_visit(
        self, mentor_ref: str, school_ref: str, start: datetime, end: datetime, purpose: str
    ) -> dict:
        async with self._db.session() as s:
            school = await s.get(m.School, school_ref)
            if school is None or school.mentor_ref != mentor_ref:
                raise RecordNotFound(f"School {school_ref!r} not found for this mentor")
            existing = (await s.execute(select(m.SchoolVisit.id))).scalars().all()
            visit_ref = f"VIS-{len(existing) + 1:03d}-P"
            while visit_ref in existing:
                visit_ref += "X"
            s.add(
                m.SchoolVisit(
                    id=visit_ref,
                    mentor_ref=mentor_ref,
                    school_ref=school_ref,
                    status=VisitStatus.planned.value,
                    scheduled_start=start,
                    scheduled_end=end,
                    purpose=purpose,
                    is_demo=True,
                )
            )
            await s.commit()
        return {
            "visit_ref": visit_ref,
            "school_ref": school_ref,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "status": "planned",
            "data_source": "demo",
        }

    async def update_task_due_date(self, mentor_ref: str, task_ref: str, due_at: datetime) -> dict:
        async with self._db.session() as s:
            task = await s.get(m.Task, task_ref)
            if task is None or task.mentor_ref != mentor_ref:
                raise RecordNotFound(f"Task {task_ref!r} not found for this mentor")
            previous = task.due_at.isoformat() if task.due_at else None
            task.due_at = due_at
            task.updated_at = datetime.now(due_at.tzinfo)
            await s.commit()
        return {
            "task_ref": task_ref,
            "previous_due_at": previous,
            "new_due_at": due_at.isoformat(),
            "data_source": "demo",
        }

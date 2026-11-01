
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School, Teacher, SchoolTeacher
from app.models.mentor_school import MentorSchool
from app.models.classroom import Classroom
from app.models.timetable import Timetable
from app.models.school_visits import SchoolVisit
from app.models.observation import Observation
from app.models.observation_finding import ObservationFinding
from app.models.learning_gap import LearningGap
from app.models.recommendation import Recommendation
from app.models.action_plan import ActionPlan
from app.models.action_plan_step import ActionPlanStep
from app.models.follow_up import FollowUp
from app.models.mentor_task import MentorTask
from app.models.schedule import Schedule


ZERO_UUID = uuid.UUID(int=0)

SYNC_MODELS = {
    "school": School,
    "teacher": Teacher,
    "school_teacher": SchoolTeacher,
    "classroom": Classroom,
    "timetable": Timetable,
    "school_visit": SchoolVisit,
    "observation": Observation,
    "observation_finding": ObservationFinding,
    "learning_gap": LearningGap,
    "recommendation": Recommendation,
    "action_plan": ActionPlan,
    "action_plan_step": ActionPlanStep,
    "follow_up": FollowUp,
    "mentor_task": MentorTask,
    "schedule": Schedule,
}


def serialize_value(value: Any):
    if isinstance(value, (uuid.UUID, datetime, date)):
        return value.isoformat() if not isinstance(value, uuid.UUID) else str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    return value


def serialize_record(record) -> dict:
    return {
        column.key: serialize_value(getattr(record, column.key))
        for column in record.__table__.columns
    }


def school_access_filter(entity_type, model, user_id):
    assigned_school = (
        select(MentorSchool.school_id)
        .where(
            MentorSchool.user_id == user_id,
            MentorSchool.is_active.is_(True),
            MentorSchool.deleted_at.is_(None),
            or_(
                MentorSchool.assigned_from.is_(None),
                MentorSchool.assigned_from <= date.today(),
            ),
            or_(
                MentorSchool.assigned_until.is_(None),
                MentorSchool.assigned_until >= date.today(),
            ),
        )
    )

    school_id = None

    if entity_type == "school":
        school_id = model.id

    elif entity_type in ("teacher", "school_teacher"):
        if entity_type == "teacher":
            return model.id.in_(
                select(SchoolTeacher.teacher_id).where(
                    SchoolTeacher.school_id.in_(assigned_school),
                    SchoolTeacher.is_active.is_(True),
                    SchoolTeacher.deleted_at.is_(None),
                )
            )
        school_id = model.school_id

    elif entity_type == "classroom":
        school_id = model.school_id

    elif entity_type == "timetable":
        return model.classroom_id.in_(
            select(Classroom.id).where(
                Classroom.school_id.in_(assigned_school),
                Classroom.deleted_at.is_(None),
            )
        )

    elif entity_type == "school_visit":
        school_id = model.school_id

    elif entity_type == "observation":
        return model.school_visit_id.in_(
            select(SchoolVisit.id).where(
                SchoolVisit.school_id.in_(assigned_school),
                SchoolVisit.deleted_at.is_(None),
            )
        )

    elif entity_type == "observation_finding":
        return model.observation_id.in_(
            select(Observation.id).where(
                Observation.school_visit_id.in_(
                    select(SchoolVisit.id).where(
                        SchoolVisit.school_id.in_(assigned_school),
                        SchoolVisit.deleted_at.is_(None),
                    )
                ),
                Observation.deleted_at.is_(None),
            )
        )

    elif entity_type == "learning_gap":
        return model.observation_id.in_(
            select(Observation.id).where(
                Observation.school_visit_id.in_(
                    select(SchoolVisit.id).where(
                        SchoolVisit.school_id.in_(assigned_school)
                    )
                )
            )
        )

    elif entity_type == "recommendation":
        return model.learning_gap_id.in_(
            select(LearningGap.id).where(
                LearningGap.observation_id.in_(
                    select(Observation.id).where(
                        Observation.school_visit_id.in_(
                            select(SchoolVisit.id).where(
                                SchoolVisit.school_id.in_(assigned_school)
                            )
                        )
                    )
                )
            )
        )

    elif entity_type == "action_plan":
        return model.recommendation_id.in_(
            select(Recommendation.id).where(
                school_access_filter(
                    "recommendation", Recommendation, user_id
                )
            )
        )

    elif entity_type == "action_plan_step":
        return model.action_plan_id.in_(
            select(ActionPlan.id).where(
                school_access_filter("action_plan", ActionPlan, user_id)
            )
        )

    elif entity_type == "follow_up":
        return model.action_plan_step_id.in_(
            select(ActionPlanStep.id).where(
                school_access_filter(
                    "action_plan_step", ActionPlanStep, user_id
                )
            )
        )

    elif entity_type == "mentor_task":
        # Tasks belong to their owner (school is optional).
        return func.coalesce(model.mentor_id, model.created_by) == user_id

    elif entity_type == "schedule":
        school_id = model.school_id

    if school_id is not None:
        return school_id.in_(assigned_school)

    raise ValueError(f"Unsupported sync entity: {entity_type}")


async def fetch_sync_changes(
    db: AsyncSession,
    user_id: uuid.UUID,
    cursor_updated_at: datetime | None,
    cursor_entity_type: str | None,
    cursor_entity_id: uuid.UUID | None,
    limit: int,
):
    if cursor_updated_at is not None:
        if cursor_updated_at.tzinfo is None:
            raise ValueError("Sync cursor must include a timezone.")

        if cursor_entity_type is None or cursor_entity_id is None:
            raise ValueError("A complete composite sync cursor is required.")

    changes = []

    for entity_type, model in SYNC_MODELS.items():
        query = select(model).where(
            school_access_filter(entity_type, model, user_id)
        )

        if cursor_updated_at is not None:
            query = query.where(
                or_(
                    model.updated_at > cursor_updated_at,
                    and_(
                        model.updated_at == cursor_updated_at,
                        entity_type > cursor_entity_type,
                    ),
                    and_(
                        model.updated_at == cursor_updated_at,
                        entity_type == cursor_entity_type,
                        model.id > cursor_entity_id,
                    ),
                )
            )

        query = query.order_by(model.updated_at, model.id).limit(limit + 1)

        result = await db.execute(query)
        records = result.scalars().all()

        for record in records:
            changes.append({
                "id": record.id,
                "entity_type": entity_type,
                "entity_id": record.id,
                "operation_type": (
                    "delete" if record.deleted_at is not None
                    else "create" if record.version == 1
                    else "update"
                ),
                "payload": (
                    {"id": str(record.id), "deleted": True}
                    if record.deleted_at is not None
                    else serialize_record(record)
                ),
                "version": record.version,
                "updated_at": record.updated_at,
            })

    changes.sort(
        key=lambda item: (
            item["updated_at"],
            item["entity_type"],
            str(item["entity_id"]),
        )
    )

    has_more = len(changes) > limit
    changes = changes[:limit]

    if changes:
        last = changes[-1]
        next_cursor = {
            "updated_at": last["updated_at"],
            "entity_type": last["entity_type"],
            "entity_id": last["entity_id"],
        }
    else:
        next_cursor = {
            "updated_at": cursor_updated_at,
            "entity_type": cursor_entity_type,
            "entity_id": cursor_entity_id,
        }

    return changes, next_cursor, has_more

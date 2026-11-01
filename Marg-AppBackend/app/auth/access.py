"""
Row-level data access control for MARG.

Every authenticated API request carries an ``AccessScope`` on its database
session. A single SQLAlchemy ``do_orm_execute`` hook then appends the
appropriate filter to every ORM SELECT that touches a scoped entity, so a
mentor can only ever read (and therefore only ever modify) records that
belong to the schools they are actively assigned to, or records they own.

Design notes
------------
* Deny by default: a request session without a scope sees no scoped rows.
* Background workers / CLI scripts use sessions that are not marked as
  request sessions and are therefore unscoped (system context).
* Out-of-scope records surface as 404 (not 403) so record existence is not
  leaked across schools.
* Column/relationship refresh loads are not filtered (the object was already
  authorised when it was first loaded).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import and_, event, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.models.action_plan import ActionPlan
from app.models.action_plan_step import ActionPlanStep
from app.models.ai_job import AIJob
from app.models.classroom import Classroom
from app.models.evidence import Evidence
from app.models.follow_up import FollowUp
from app.models.learning_gap import LearningGap
from app.models.mentor_school import MentorSchool
from app.models.mentor_task import MentorTask
from app.models.notifications import Notification
from app.models.observation import Observation
from app.models.observation_finding import ObservationFinding
from app.models.recommendation import Recommendation
from app.models.schedule import Schedule
from app.models.school import School, SchoolTeacher, Teacher
from app.models.school_visits import SchoolVisit
from app.models.sync_operation import SyncOperation
from app.models.timetable import Timetable
from app.models.whatsapp_message import WhatsAppMessage

REQUEST_SESSION_KEY = "marg_request_session"
SCOPE_KEY = "marg_access_scope"
# Execution option for internal, authorisation-related lookups that must see
# rows regardless of scope (e.g. resolving the scope itself, global
# uniqueness checks). Never pass this for data returned to a client.
BYPASS_SCOPE = {"marg_bypass_scope": True}


@dataclass(frozen=True)
class AccessScope:
    user_id: uuid.UUID
    school_ids: tuple[uuid.UUID, ...] = field(default_factory=tuple)
    unrestricted: bool = False


async def load_assigned_school_ids(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[uuid.UUID, ...]:
    """Schools the user is currently, actively assigned to."""
    today = date.today()
    result = await db.execute(
        select(MentorSchool.school_id).where(
            MentorSchool.user_id == user_id,
            MentorSchool.is_active.is_(True),
            MentorSchool.deleted_at.is_(None),
            or_(MentorSchool.assigned_from.is_(None), MentorSchool.assigned_from <= today),
            or_(MentorSchool.assigned_until.is_(None), MentorSchool.assigned_until >= today),
        ),
        execution_options=BYPASS_SCOPE,
    )
    return tuple(dict.fromkeys(result.scalars().all()))


def mark_request_session(db: AsyncSession) -> None:
    db.info[REQUEST_SESSION_KEY] = True


def set_scope(db: AsyncSession, scope: AccessScope) -> None:
    db.info[SCOPE_KEY] = scope


def get_scope(db: AsyncSession) -> AccessScope | None:
    return db.info.get(SCOPE_KEY)


def _criteria(scope: AccessScope | None) -> list:
    """Build per-entity loader criteria for a scope (None => deny all)."""
    scoped_entities = (
        School, Classroom, Timetable, Teacher, SchoolTeacher, SchoolVisit,
        Observation, ObservationFinding, LearningGap, Recommendation,
        ActionPlan, ActionPlanStep, FollowUp, Evidence, MentorTask, Schedule,
        AIJob, Notification, SyncOperation, WhatsAppMessage, MentorSchool,
    )
    if scope is None:
        return [with_loader_criteria(e, false(), include_aliases=True) for e in scoped_entities]

    ids = list(scope.school_ids)
    uid = scope.user_id

    visit_ids = select(SchoolVisit.id).where(SchoolVisit.school_id.in_(ids))
    obs_ids = select(Observation.id).where(Observation.school_visit_id.in_(visit_ids))
    gap_ids = select(LearningGap.id).where(LearningGap.observation_id.in_(obs_ids))
    rec_ids = select(Recommendation.id).where(Recommendation.learning_gap_id.in_(gap_ids))
    plan_ids = select(ActionPlan.id).where(ActionPlan.recommendation_id.in_(rec_ids))
    step_ids = select(ActionPlanStep.id).where(ActionPlanStep.action_plan_id.in_(plan_ids))
    fu_ids = select(FollowUp.id).where(FollowUp.action_plan_step_id.in_(step_ids))
    classroom_ids = select(Classroom.id).where(Classroom.school_id.in_(ids))
    teacher_ids = select(SchoolTeacher.teacher_id).where(
        SchoolTeacher.school_id.in_(ids), SchoolTeacher.deleted_at.is_(None)
    )

    rules = {
        School: School.id.in_(ids),
        Classroom: Classroom.school_id.in_(ids),
        Timetable: Timetable.classroom_id.in_(classroom_ids),
        Teacher: or_(Teacher.id.in_(teacher_ids), Teacher.created_by == uid),
        SchoolTeacher: SchoolTeacher.school_id.in_(ids),
        SchoolVisit: SchoolVisit.school_id.in_(ids),
        Observation: Observation.school_visit_id.in_(visit_ids),
        ObservationFinding: ObservationFinding.observation_id.in_(obs_ids),
        LearningGap: LearningGap.observation_id.in_(obs_ids),
        Recommendation: Recommendation.learning_gap_id.in_(gap_ids),
        ActionPlan: ActionPlan.recommendation_id.in_(rec_ids),
        ActionPlanStep: ActionPlanStep.action_plan_id.in_(plan_ids),
        FollowUp: FollowUp.action_plan_step_id.in_(step_ids),
        Evidence: or_(Evidence.observation_id.in_(obs_ids), Evidence.follow_up_id.in_(fu_ids)),
        MentorTask: and_(
            func.coalesce(MentorTask.mentor_id, MentorTask.created_by) == uid,
            or_(MentorTask.school_id.is_(None), MentorTask.school_id.in_(ids)),
        ),
        Schedule: Schedule.school_id.in_(ids),
        AIJob: AIJob.requested_by == uid,
        Notification: Notification.user_id == uid,
        SyncOperation: SyncOperation.created_by == uid,
        WhatsAppMessage: WhatsAppMessage.created_by == uid,
        MentorSchool: MentorSchool.user_id == uid,
    }
    return [with_loader_criteria(e, c, include_aliases=True) for e, c in rules.items()]


@event.listens_for(Session, "do_orm_execute")
def _apply_access_scope(state: ORMExecuteState) -> None:
    session = state.session
    if not session.info.get(REQUEST_SESSION_KEY):
        return  # system context (workers, CLI, seed scripts)
    if not state.is_select or state.is_column_load or state.is_relationship_load:
        return
    if state.execution_options.get("marg_bypass_scope"):
        return
    scope: AccessScope | None = session.info.get(SCOPE_KEY)
    if scope is not None and scope.unrestricted:
        return
    state.statement = state.statement.options(*_criteria(scope))

"""Notification creation and reminder generation.

Reminders are derived from real records (tasks, visits, action plan steps,
follow-ups). Each (user, type, entity) reminder is created at most once, so
the generator can run as often as needed (idempotent).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_plan import ActionPlan
from app.models.action_plan_step import ActionPlanStep
from app.models.follow_up import FollowUp
from app.models.mentor_task import MentorTask
from app.models.notifications import Notification
from app.models.school import School
from app.models.school_visits import SchoolVisit

logger = logging.getLogger("marg.notifications")


async def notify(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str,
    message: str,
    notification_type: str,
    reference_entity_type: str | None = None,
    reference_entity_id: uuid.UUID | None = None,
    once: bool = True,
) -> Notification | None:
    """Add a notification (caller commits). With ``once`` the same
    (user, type, entity) notification is never created twice."""
    if once and reference_entity_id is not None:
        exists = await db.execute(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.notification_type == notification_type,
                Notification.reference_entity_id == reference_entity_id,
            )
        )
        if exists.first() is not None:
            return None
    n = Notification(
        user_id=user_id,
        title=title[:255],
        message=message,
        notification_type=notification_type,
        reference_entity_type=reference_entity_type,
        reference_entity_id=reference_entity_id,
        is_read=False,
    )
    db.add(n)
    return n


async def generate_reminders(db: AsyncSession, now: datetime | None = None) -> int:
    """Create due/overdue reminders across all mentors (system context)."""
    now = now or datetime.now(timezone.utc)
    created = 0

    async def add(**kwargs) -> None:
        nonlocal created
        if await notify(db, **kwargs) is not None:
            created += 1

    # Tasks due within 24h / overdue
    tasks = (
        await db.execute(
            select(MentorTask).where(
                MentorTask.deleted_at.is_(None),
                MentorTask.status.in_(["pending", "in_progress"]),
                MentorTask.due_at.is_not(None),
                MentorTask.due_at <= now + timedelta(hours=24),
            )
        )
    ).scalars().all()
    for t in tasks:
        owner = t.mentor_id or t.created_by
        if owner is None:
            continue
        overdue = t.due_at < now
        await add(
            user_id=owner,
            title="Task overdue" if overdue else "Task due soon",
            message=f"'{t.title}' {'was due' if overdue else 'is due'} on {t.due_at:%d %b %Y, %H:%M} UTC.",
            notification_type="task_overdue" if overdue else "task_due_soon",
            reference_entity_type="mentor_task",
            reference_entity_id=t.id,
        )

    # Visits in the next 24h
    visits = (
        await db.execute(
            select(SchoolVisit, School.name)
            .join(School, School.id == SchoolVisit.school_id)
            .where(
                SchoolVisit.deleted_at.is_(None),
                SchoolVisit.status == "planned",
                SchoolVisit.scheduled_at >= now,
                SchoolVisit.scheduled_at <= now + timedelta(hours=24),
            )
        )
    ).all()
    for v, school_name in visits:
        owner = v.mentor_id or v.created_by
        if owner is None:
            continue
        await add(
            user_id=owner,
            title="Upcoming school visit",
            message=f"Visit to {school_name} is scheduled for {v.scheduled_at:%d %b %Y, %H:%M} UTC.",
            notification_type="visit_upcoming",
            reference_entity_type="school_visit",
            reference_entity_id=v.id,
        )

    # Action plan steps due within 2 days or overdue
    steps = (
        await db.execute(
            select(ActionPlanStep, ActionPlan.title)
            .join(ActionPlan, ActionPlan.id == ActionPlanStep.action_plan_id)
            .where(
                ActionPlanStep.deleted_at.is_(None),
                ActionPlanStep.status.in_(["pending", "in_progress"]),
                ActionPlanStep.due_date <= (now + timedelta(days=2)).date(),
            )
        )
    ).all()
    for step, plan_title in steps:
        if step.created_by is None:
            continue
        overdue = step.due_date < now.date()
        await add(
            user_id=step.created_by,
            title="Action plan step overdue" if overdue else "Action plan step due",
            message=f"Step '{step.title}' of plan '{plan_title}' is due on {step.due_date:%d %b %Y}.",
            notification_type="step_overdue" if overdue else "step_due_soon",
            reference_entity_type="action_plan_step",
            reference_entity_id=step.id,
        )

    # Follow-ups waiting for the mentor to verify evidence
    follow_ups = (
        await db.execute(
            select(FollowUp).where(
                FollowUp.deleted_at.is_(None),
                FollowUp.status == "evidence_submitted",
            )
        )
    ).scalars().all()
    for fu in follow_ups:
        if fu.created_by is None:
            continue
        await add(
            user_id=fu.created_by,
            title="Follow-up evidence to verify",
            message=f"Evidence was submitted for follow-up: {fu.description[:120]}",
            notification_type="follow_up_needs_verification",
            reference_entity_type="follow_up",
            reference_entity_id=fu.id,
        )

    await db.commit()
    if created:
        logger.info("Generated %s reminder notification(s)", created)
    return created


async def count_unread(db: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id, Notification.is_read.is_(False)
            )
        )
    ).scalar_one()

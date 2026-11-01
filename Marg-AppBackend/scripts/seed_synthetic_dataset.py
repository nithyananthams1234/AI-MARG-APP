"""Seed a repeatable, synthetic dataset for the existing MARG mentor.

The script targets only the runtime database ``marg_db`` as ``marg_app``.
It is a dry run unless ``--apply`` is supplied, never resets/deletes data,
and uses deterministic UUIDs so repeated runs do not create duplicates.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.mentor_tasks.router import apply_priority
from app.models import (
    ActionPlan,
    ActionPlanStep,
    Classroom,
    FollowUp,
    LearningGap,
    MentorSchool,
    MentorTask,
    Notification,
    Observation,
    ObservationFinding,
    Recommendation,
    Role,
    Schedule,
    School,
    SchoolTeacher,
    SchoolVisit,
    Teacher,
    Timetable,
    User,
    UserRole,
)


NAMESPACE = uuid.UUID("c2694315-5f70-4eab-9cb4-6ddde87c61a1")
MARKER = "AIMARG-DEMO-2026-11"
TIMEZONE = timezone.utc
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
SUBJECTS = ("Mathematics", "Science", "English", "Tamil", "Social Studies")


def stable_id(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


class SyntheticSeeder:
    def __init__(self, db: AsyncSession, mentor: User, today: date):
        self.db = db
        self.mentor = mentor
        self.today = today
        self.created = 0

    async def ensure(self, model: type, key: str, **fields):
        record_id = stable_id(key)
        record = await self.db.get(model, record_id)
        if record is None:
            record = model(id=record_id, **fields)
            self.db.add(record)
            await self.db.flush()
            self.created += 1
        return record

    def at(self, offset: int, hour: int = 10, minute: int = 0) -> datetime:
        return datetime.combine(
            self.today + timedelta(days=offset),
            time(hour, minute),
            tzinfo=TIMEZONE,
        )

    def audit(self) -> dict:
        return {"created_by": self.mentor.id, "updated_by": self.mentor.id}

    async def seed(self) -> None:
        schools: list[School] = []
        teachers: list[Teacher] = []
        classrooms: list[Classroom] = []

        for i in range(1, 21):
            number = f"{i:02d}"
            school = await self.ensure(
                School,
                f"school:{number}",
                name=f"{MARKER} Synthetic School {number}",
                code=f"{MARKER}-S{number}",
                address=f"Fictional demo location {number}; no real street address.",
                district=f"Demo District {((i - 1) % 4) + 1:02d}",
                block=f"Demo Block {((i - 1) % 5) + 1:02d}",
                travel_minutes_from_base=15 + (i % 6) * 10,
                state="Demo State",
                is_active=True,
                **self.audit(),
            )
            schools.append(school)
            await self.ensure(
                MentorSchool,
                f"mentor-school:{number}",
                user_id=self.mentor.id,
                school_id=school.id,
                assigned_from=self.today - timedelta(days=365),
                assigned_until=None,
                is_active=True,
                **self.audit(),
            )

            teacher = await self.ensure(
                Teacher,
                f"teacher:{number}",
                full_name=f"Synthetic Educator {number}",
                employee_code=f"{MARKER}-T{number}",
                email=f"educator{number}@demo.invalid",
                phone=None,
                is_active=True,
                **self.audit(),
            )
            teachers.append(teacher)
            await self.ensure(
                SchoolTeacher,
                f"school-teacher:{number}",
                school_id=school.id,
                teacher_id=teacher.id,
                assigned_from=self.today - timedelta(days=365),
                assigned_until=None,
                is_active=True,
                **self.audit(),
            )

            grade = str(4 + ((i - 1) % 7))
            classroom = await self.ensure(
                Classroom,
                f"classroom:{number}",
                school_id=school.id,
                name=f"Class {grade}-A",
                grade=grade,
                section="A",
                academic_year=f"{self.today.year}-{(self.today.year + 1) % 100:02d}",
                capacity=35 + (i % 6) * 5,
                **self.audit(),
            )
            classrooms.append(classroom)
            for day_index, weekday in enumerate(WEEKDAYS):
                subject = SUBJECTS[(i + day_index - 1) % len(SUBJECTS)]
                await self.ensure(
                    Timetable,
                    f"timetable:{number}:{weekday}",
                    classroom_id=classroom.id,
                    day_of_week=weekday,
                    period_number=1,
                    subject=subject,
                    start_time=time(9, 0),
                    end_time=time(9, 45),
                    teacher_id=teacher.id,
                    **self.audit(),
                )

        visits: list[SchoolVisit] = []
        visit_specs: list[tuple[int, int, str]] = []
        visit_specs.extend((i, -(i % 12 + 1), "completed") for i in range(1, 13))
        visit_specs.extend(((13, 0, "in_progress"), (14, 0, "in_progress")))
        visit_specs.extend(
            (i, (i - 14) * 2, "planned") for i in range(15, 23)
        )
        visit_specs.extend(((23, -2, "cancelled"), (24, -5, "cancelled")))

        for i, offset, status in visit_specs:
            school_index = (i - 1) % 20
            start = self.at(offset, 9 + (i % 5))
            visit_fields = {
                "school_id": schools[school_index].id,
                "mentor_id": self.mentor.id,
                "scheduled_at": start,
                "started_at": start if status in {"in_progress", "completed"} else None,
                "completed_at": start + timedelta(hours=3) if status == "completed" else None,
                "status": status,
                "notes": (
                    f"{MARKER}: synthetic mentoring visit. "
                    "All classroom details are fictional and aggregate-only."
                ),
                **self.audit(),
            }
            visit = await self.ensure(SchoolVisit, f"visit:{i:02d}", **visit_fields)
            visits.append(visit)

            if status != "cancelled":
                if status in {"completed", "in_progress"}:
                    schedule_status = "accepted"
                elif i <= 16:
                    schedule_status = "proposed"
                elif i <= 18:
                    schedule_status = "accepted"
                else:
                    schedule_status = "rejected"
                await self.ensure(
                    Schedule,
                    f"schedule:{i:02d}",
                    school_visit_id=visit.id,
                    school_id=schools[school_index].id,
                    proposed_start_at=start,
                    proposed_end_at=start + timedelta(hours=3),
                    estimated_travel_minutes=schools[school_index].travel_minutes_from_base,
                    estimated_distance_km=None,
                    status=schedule_status,
                    notes=f"{MARKER}: synthetic schedule record.",
                    **self.audit(),
                )

        task_statuses = (
            ["pending"] * 10
            + ["in_progress"] * 6
            + ["completed"] * 6
            + ["cancelled"] * 2
        )
        tasks: list[MentorTask] = []
        categories = (
            "planning",
            "classroom_support",
            "follow_up",
            "travel",
            "reporting",
            "training",
        )
        for i, task_status in enumerate(task_statuses, start=1):
            due_offset = (
                -(i % 7 + 1)
                if task_status == "completed"
                else ((i * 3) % 17) - 5
            )
            due_at = self.at(due_offset, 16)
            task = MentorTask(
                id=stable_id(f"task:{i:02d}"),
                school_id=schools[(i - 1) % 20].id if i % 4 else None,
                mentor_id=self.mentor.id,
                title=f"{MARKER} Mentor task {i:02d}",
                description=(
                    "Synthetic mentor-only task; no real learner data or contact details."
                ),
                category=categories[(i - 1) % len(categories)],
                estimated_minutes=20 + (i % 5) * 15,
                due_at=due_at,
                status=task_status,
                urgency=(i * 13) % 101,
                impact=(i * 17) % 101,
                risk=(i * 7) % 101,
                deadline_proximity=max(0, min(100, 100 - due_offset * 8)),
                workload_dependency=(i * 11) % 101,
                priority_score=0,
                completed_at=due_at - timedelta(hours=2) if task_status == "completed" else None,
                **self.audit(),
            )
            apply_priority(task)
            existing = await self.db.get(MentorTask, task.id)
            if existing is None:
                self.db.add(task)
                await self.db.flush()
                self.created += 1
                tasks.append(task)
            else:
                tasks.append(existing)

        observations: list[Observation] = []
        findings: list[ObservationFinding] = []
        gaps: list[LearningGap] = []
        recommendations: list[Recommendation] = []
        observation_statuses = ("draft", "submitted", "reviewed")
        severities = ("low", "medium", "high", "critical")
        gap_statuses = ("identified", "addressed", "resolved")

        for i in range(1, 13):
            visit = visits[i - 1]
            school_index = (i - 1) % 20
            subject = SUBJECTS[(i - 1) % len(SUBJECTS)]
            observation = await self.ensure(
                Observation,
                f"observation:{i:02d}",
                school_visit_id=visit.id,
                teacher_id=teachers[school_index].id,
                classroom_id=classrooms[school_index].id,
                subject=subject,
                topic=f"{subject} classroom practice {i:02d}",
                notes=(
                    f"{MARKER}: synthetic aggregate observation. "
                    "No learner names, individual profiles, or real classroom records."
                ),
                status=observation_statuses[(i - 1) % len(observation_statuses)],
                **self.audit(),
            )
            observations.append(observation)
            finding = await self.ensure(
                ObservationFinding,
                f"finding:{i:02d}",
                observation_id=observation.id,
                title=f"{MARKER} Teaching practice finding {i:02d}",
                description=(
                    "Synthetic observation finding for demonstration; "
                    "not an AI-generated result."
                ),
                category=("questioning", "student participation", "lesson planning")[
                    (i - 1) % 3
                ],
                status="mentor_approved" if i % 5 else "rejected",
                mentor_comment=f"{MARKER}: synthetic workflow state.",
                **self.audit(),
            )
            findings.append(finding)
            gap = await self.ensure(
                LearningGap,
                f"gap:{i:02d}",
                observation_id=observation.id,
                observation_finding_id=finding.id,
                title=f"{MARKER} Aggregate learning gap {i:02d}",
                description=(
                    "Fictional group-level learning need; no individual learner data."
                ),
                subject=subject,
                grade=classrooms[school_index].grade,
                severity=severities[(i - 1) % len(severities)],
                status=gap_statuses[(i - 1) % len(gap_statuses)],
                **self.audit(),
            )
            gaps.append(gap)
            recommendation = await self.ensure(
                Recommendation,
                f"recommendation:{i:02d}",
                learning_gap_id=gap.id,
                title=f"{MARKER} Mentor recommendation {i:02d}",
                description=(
                    "Synthetic, mentor-entered demonstration recommendation; "
                    "not AI output."
                ),
                rationale=(
                    "Demonstrates the existing recommendation workflow using "
                    "fictional aggregate data."
                ),
                category=("instruction", "assessment", "participation")[(i - 1) % 3],
                status="mentor_approved" if i % 6 else "rejected",
                mentor_comment=f"{MARKER}: synthetic workflow state.",
                **self.audit(),
            )
            recommendations.append(recommendation)

        plan_statuses = (
            "draft",
            "pending_approval",
            "approved",
            "approved",
            "in_progress",
            "completed",
        )
        plans: list[ActionPlan] = []
        for i, plan_status in enumerate(plan_statuses, start=1):
            school_index = (i - 1) % 20
            plan = await self.ensure(
                ActionPlan,
                f"action-plan:{i:02d}",
                recommendation_id=recommendations[i - 1].id,
                title=f"{MARKER} Classroom support plan {i:02d}",
                description=(
                    "Synthetic plan for a fictional classroom; dates and workflow "
                    "state are for demonstration only."
                ),
                responsible_person=f"Synthetic Educator {school_index + 1:02d}",
                start_date=self.today + timedelta(days=min(i - 2, 0)),
                due_date=self.today + timedelta(days=i + 14),
                status=plan_status,
                mentor_comment=f"{MARKER}: synthetic workflow state.",
                **self.audit(),
            )
            plans.append(plan)

        follow_statuses = (
            "pending",
            "teacher_responded",
            "evidence_submitted",
            "mentor_verified",
            "needs_revision",
            "closed",
        )
        followups: list[FollowUp] = []
        for i in range(1, 7):
            plan_index = (i - 1) // 2 + 2
            plan = plans[plan_index]
            school_index = plan_index
            step = await self.ensure(
                ActionPlanStep,
                f"action-plan-step:{i:02d}",
                action_plan_id=plan.id,
                title=f"{MARKER} Practice activity {i:02d}",
                description=(
                    "Synthetic follow-up activity for a fictional teaching practice."
                ),
                responsible_person=f"Synthetic Educator {school_index + 1:02d}",
                due_date=self.today + timedelta(days=i - 3),
                status="pending" if i % 2 else "in_progress",
                completion_notes=None,
                **self.audit(),
            )
            follow_status = follow_statuses[i - 1]
            responded = self.at(-1) if follow_status != "pending" else None
            verified = (
                self.at(0)
                if follow_status in {"mentor_verified", "needs_revision", "closed"}
                else None
            )
            followup = await self.ensure(
                FollowUp,
                f"follow-up:{i:02d}",
                action_plan_step_id=step.id,
                teacher_id=teachers[school_index].id,
                description=f"{MARKER}: synthetic mentor follow-up {i:02d}.",
                status=follow_status,
                teacher_response=(
                    f"{MARKER}: fictional aggregate response."
                    if responded is not None
                    else None
                ),
                mentor_notes=(
                    f"{MARKER}: fictional mentor note."
                    if verified is not None
                    else None
                ),
                responded_at=responded,
                verified_at=verified,
                **self.audit(),
            )
            followups.append(followup)

        notification_specs = (
            ("task_overdue", "mentor_task", tasks[0].id, False),
            ("task_due_soon", "mentor_task", tasks[1].id, False),
            ("visit_upcoming", "school_visit", visits[14].id, False),
            ("step_overdue", "action_plan_step", stable_id("action-plan-step:01"), False),
            ("follow_up_needs_verification", "follow_up", followups[2].id, False),
            ("system", None, None, True),
            ("visit_upcoming", "school_visit", visits[15].id, True),
            ("task_due_soon", "mentor_task", tasks[2].id, True),
        )
        for i, (kind, entity_type, entity_id, is_read) in enumerate(
            notification_specs, start=1
        ):
            await self.ensure(
                Notification,
                f"notification:{i:02d}",
                user_id=self.mentor.id,
                title=f"{MARKER} {kind.replace('_', ' ').title()}",
                message=(
                    "Synthetic notification linked to fictional mentor activity; "
                    "no real person or event is represented."
                ),
                notification_type=kind,
                reference_entity_type=entity_type,
                reference_entity_id=entity_id,
                is_read=is_read,
                read_at=self.at(-1) if is_read else None,
            )


async def find_single_active_mentor(db: AsyncSession) -> User:
    result = await db.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(User.is_active.is_(True), Role.name == "Mentor")
        .distinct()
        .limit(2)
    )
    mentors = result.scalars().all()
    if len(mentors) != 1:
        raise RuntimeError(
            "Refusing to seed: expected exactly one active Mentor account."
        )
    return mentors[0]


async def main(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await db.begin()
            database_name, database_role = (
                await db.execute(
                    text("SELECT current_database(), current_user")
                )
            ).one()
            if database_name != "marg_db" or database_role != "marg_app":
                raise RuntimeError(
                    "Refusing to seed: expected database marg_db and role marg_app."
                )

            mentor = await find_single_active_mentor(db)
            marker_school_ids = (
                await db.execute(
                    select(School.id).where(School.code.like(f"{MARKER}-S%"))
                )
            ).scalars().all()
            expected_school_ids = {
                stable_id(f"school:{i:02d}") for i in range(1, 21)
            }
            if any(record_id not in expected_school_ids for record_id in marker_school_ids):
                raise RuntimeError(
                    "Refusing to seed: a school code uses the demo marker but is not "
                    "owned by this seed script."
                )

            seeder = SyntheticSeeder(db, mentor, date.today())
            await seeder.seed()
            await db.flush()
            if apply:
                await db.commit()
            else:
                await db.rollback()
        except Exception:
            await db.rollback()
            raise

    action = "Inserted" if apply else "Dry run; rolled back"
    print(f"{action}: {seeder.created} synthetic records.")
    if not apply:
        print("No data was retained. Use --apply only after explicit approval.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the synthetic dataset (requires explicit user approval).",
    )
    asyncio.run(main(parser.parse_args().apply))

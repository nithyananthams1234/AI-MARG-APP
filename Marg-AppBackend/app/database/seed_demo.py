"""
MARG demonstration data (fictional, repeatable, idempotent).

Usage (from the backend folder):
    DEMO_PASSWORD='...' python -m app.database.seed_demo            # create missing demo data
    DEMO_PASSWORD='...' python -m app.database.seed_demo --reset    # wipe the DEMO database and re-seed

Safety:
* Only runs against a database whose name ends with "_demo" (e.g. marg_demo),
  so demonstration data never mixes with real data.
* All people, schools and phone numbers are fictional.
* Records use deterministic UUIDs (uuid5), so re-running creates no duplicates.
* Dates are relative to the day the data was (re)seeded, so the demo always
  has past, current and upcoming work. Use --reset to re-anchor dates.
* The demo password is taken from DEMO_PASSWORD; if not set, a random one is
  generated and printed once. Passwords are never stored in source code.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from app.auth.hashing import hash_password
from app.core.config import settings
from app.database.session import AsyncSessionLocal, engine
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
from app.services.notifications import generate_reminders
from app.mentor_tasks.router import apply_priority

NS = uuid.UUID("6f1c2a52-3c6b-4d7e-9b8a-6d6172670000")  # "marg" demo namespace
IST = timezone(timedelta(hours=5, minutes=30))

DEMO_MENTOR_EMAIL = "mentor.demo@marg.example"
DEMO_MENTOR2_EMAIL = "mentor2.demo@marg.example"
DEMO_ADMIN_EMAIL = "admin.demo@marg.example"


def uid(key: str) -> uuid.UUID:
    return uuid.uuid5(NS, key)


class Seeder:
    def __init__(self, db, password: str, today: date, set_password: bool = False):
        self.db = db
        self.set_password = set_password
        self.password_hash = hash_password(password)
        self.today = today
        self.created = 0

    async def ensure(self, model, key: str, **fields):
        obj = await self.db.get(model, uid(key))
        if obj is None:
            obj = model(id=uid(key), **fields)
            self.db.add(obj)
            await self.db.flush()
            self.created += 1
        return obj

    def at(self, day_offset: int, hour: int = 10, minute: int = 0) -> datetime:
        return datetime.combine(self.today + timedelta(days=day_offset), time(hour, minute), tzinfo=IST)

    def d(self, day_offset: int) -> date:
        return self.today + timedelta(days=day_offset)

    # ------------------------------------------------------------------
    async def run(self) -> None:
        db = self.db

        # Roles (shared with seed_roles)
        roles = {}
        for name in ("Mentor", "Supervisor", "Administrator"):
            role = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
            if role is None:
                role = Role(name=name, description=f"{name} role")
                db.add(role)
                await db.flush()
            roles[name] = role

        async def user(key, name, email, role):
            u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if u is None:
                u = await self.ensure(User, key, full_name=name, email=email,
                                      password_hash=self.password_hash, is_active=True)
            elif self.set_password:
                u.password_hash = self.password_hash
            await self.ensure(UserRole, f"{key}:role", user_id=u.id, role_id=roles[role].id)
            return u

        mentor = await user("user:mentor", "Kavya Subramanian", DEMO_MENTOR_EMAIL, "Mentor")
        mentor2 = await user("user:mentor2", "Arjun Natarajan", DEMO_MENTOR2_EMAIL, "Mentor")
        await user("user:admin", "MARG Demo Administrator", DEMO_ADMIN_EMAIL, "Administrator")

        # ---------------- Schools ----------------
        school_specs = [
            ("s1", "Government Middle School, Kalavai Road", "DEMO-GMS-01", "Ranipet", "Arcot", 35, mentor),
            ("s2", "Panchayat Union Primary School, Thiruvalam", "DEMO-PUPS-02", "Vellore", "Katpadi", 50, mentor),
            ("s3", "Government High School, Melpadi", "DEMO-GHS-03", "Vellore", "Katpadi", 65, mentor),
            ("s4", "Government Girls Higher Secondary School, Sholinghur", "DEMO-GGHSS-04", "Ranipet", "Sholinghur", 80, mentor),
            ("s5", "Government High School, Walajah East", "DEMO-GHS-05", "Ranipet", "Walajah", 40, mentor2),
        ]
        schools = {}
        for key, name, code, district, block, travel, owner in school_specs:
            s = await self.ensure(
                School, f"school:{key}", name=name, code=code, district=district, state="Tamil Nadu",
                block=block, travel_minutes_from_base=travel, is_active=True,
                address=f"Demo address, {block} block, {district} district",
            )
            schools[key] = s
            await self.ensure(MentorSchool, f"ms:{key}", user_id=owner.id, school_id=s.id,
                              assigned_from=self.d(-120), is_active=True)

        # ---------------- Teachers ----------------
        teacher_specs = {
            "s1": [("t1", "Meena Krishnan", "Mathematics"), ("t2", "Ravi Shankar", "Science"), ("t3", "Lakshmi Prabhu", "Tamil")],
            "s2": [("t4", "Anitha Selvam", "English"), ("t5", "Gopal Raj", "Mathematics")],
            "s3": [("t6", "Sathya Murugan", "Science"), ("t7", "Divya Ramesh", "Social Science")],
            "s4": [("t8", "Kalpana Devi", "Mathematics"), ("t9", "Nirmala Joseph", "English")],
            "s5": [("t10", "Prakash Kumar", "Science")],
        }
        teachers = {}
        n = 0
        for skey, specs in teacher_specs.items():
            for tkey, name, _subject in specs:
                n += 1
                t = await self.ensure(
                    Teacher, f"teacher:{tkey}", full_name=name, employee_code=f"DEMO-T{n:03d}",
                    email=f"{tkey}.demo@example.org", phone=f"+9190000100{n:02d}", is_active=True,
                )
                teachers[tkey] = t
                await self.ensure(SchoolTeacher, f"st:{skey}:{tkey}", school_id=schools[skey].id,
                                  teacher_id=t.id, assigned_from=self.d(-365), is_active=True)

        # ---------------- Classrooms + timetables ----------------
        classroom_specs = {
            "s1": [("c1", "6", "A"), ("c2", "7", "A"), ("c3", "8", "B")],
            "s2": [("c4", "4", "A"), ("c5", "5", "A")],
            "s3": [("c6", "8", "A"), ("c7", "9", "A")],
            "s4": [("c8", "9", "B"), ("c9", "10", "A")],
            "s5": [("c10", "8", "A")],
        }
        classrooms = {}
        for skey, specs in classroom_specs.items():
            for ckey, grade, section in specs:
                classrooms[ckey] = await self.ensure(
                    Classroom, f"classroom:{ckey}", school_id=schools[skey].id, name=f"Class {grade}-{section}",
                    grade=grade, section=section, academic_year="2026-27", capacity=40,
                )
                staff = teacher_specs[skey]
                for di, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]):
                    for period in range(1, 5):
                        tkey, _name, subject = staff[(di + period) % len(staff)]
                        hour = 9 + period - 1
                        await self.ensure(
                            Timetable, f"tt:{ckey}:{day}:{period}", classroom_id=classrooms[ckey].id,
                            day_of_week=day, period_number=period, subject=subject,
                            start_time=time(hour, 15), end_time=time(hour, 55),
                            teacher_id=teachers[tkey].id,
                        )

        # ---------------- Visits ----------------
        def visit(key, skey, day, status, notes, hour=10, owner=mentor):
            fields = dict(school_id=schools[skey].id, scheduled_at=self.at(day, hour), status=status, notes=notes,
                          mentor_id=owner.id, created_by=owner.id, updated_by=owner.id)
            if status in ("in_progress", "completed"):
                fields["started_at"] = self.at(day, hour, 5)
            if status == "completed":
                fields["completed_at"] = self.at(day, hour + 3)
            return self.ensure(SchoolVisit, f"visit:{key}", **fields)

        v1 = await visit("v1", "s1", -14, "completed", "Grade 6 mathematics: fractions unit review")
        v2 = await visit("v2", "s2", -9, "completed", "Primary English reading routines")
        v3 = await visit("v3", "s3", -4, "completed", "Grade 8 science practical work")
        v4 = await visit("v4", "s1", 0, "in_progress", "Follow-up on fractions action plan; observe Grade 7")
        v5 = await visit("v5", "s2", 1, "planned", "Check read-aloud routine and comprehension questioning")
        v6 = await visit("v6", "s4", 3, "planned", "First visit: meet head teacher, observe Grade 9 mathematics")
        await visit("v7", "s3", 6, "planned", "Follow-up on science practical recommendations")
        await visit("v8", "s4", -6, "cancelled", "Cancelled: school closed for local festival")
        v9 = await visit("v9", "s5", -3, "completed", "Grade 8 science observation", owner=mentor2)

        # ---------------- Observations ----------------
        def observation(key, v, tkey, ckey, subject, topic, notes, status, owner=mentor):
            return self.ensure(
                Observation, f"obs:{key}", school_visit_id=v.id, teacher_id=teachers[tkey].id,
                classroom_id=classrooms[ckey].id, subject=subject, topic=topic, notes=notes, status=status,
                created_by=owner.id, updated_by=owner.id,
            )

        o1 = await observation(
            "o1", v1, "t1", "c1", "Mathematics", "Equivalent fractions",
            "The teacher wrote the rule for equivalent fractions on the board and solved four examples. "
            "Students copied the steps into notebooks. When asked why 2/4 equals 1/2, only 3 of 36 students "
            "could explain; most repeated 'multiply top and bottom'. No concrete materials or diagrams were used. "
            "Questions were mostly closed and answered in chorus. Students sitting at the back were not involved.",
            "reviewed",
        )
        o2 = await observation(
            "o2", v2, "t4", "c4", "English", "Reading a short story",
            "The class followed a strong phonics warm-up and most children decoded simple words accurately. "
            "The teacher read the story aloud once, then asked only recall questions such as 'What is the girl's name?'. "
            "When asked why the girl was sad, very few children answered and none referred to the text. "
            "Children who finished early had no follow-up task.",
            "reviewed",
        )
        await observation(
            "o3", v3, "t6", "c6", "Science", "Separation of mixtures",
            "The teacher demonstrated filtration at the front while students watched from their seats. "
            "Students were not given materials to try the experiment themselves. Many students could name the "
            "method but could not predict which mixtures can be separated by filtration. The textbook questions "
            "were assigned as homework. Group work was planned in the lesson plan but not carried out due to time. "
            "Two students asked thoughtful questions about why salt does not stay on the filter paper.",
            "submitted",
        )
        await observation(
            "o4", v4, "t3", "c2", "Tamil", "Reading comprehension",
            "Observation in progress. Students read a passage in pairs; the teacher is moving between groups.",
            "draft",
        )
        await observation(
            "o5", v9, "t10", "c10", "Science", "Light and shadows",
            "Students made shadow puppets in groups and recorded observations in a table.",
            "submitted", owner=mentor2,
        )

        # ---------------- Findings / gaps / recommendations ----------------
        async def finding(key, o, title, desc, cat, status, comment=None):
            return await self.ensure(ObservationFinding, f"finding:{key}", observation_id=o.id, title=title,
                                     description=desc, category=cat, status=status, mentor_comment=comment,
                                     created_by=mentor.id, updated_by=mentor.id)

        f1 = await finding("f1", o1, "Procedure-focused explanation", "Equivalence was taught as a rule without concrete or visual models.", "Pedagogy", "mentor_approved", "Agreed with teacher during debrief.")
        await finding("f2", o1, "Limited student talk", "Mostly closed questions answered in chorus; back rows not involved.", "Classroom interaction", "mentor_approved")
        await finding("f3", o2, "Effective phonics routine", "Warm-up builds decoding fluency well.", "Literacy", "mentor_approved")
        f4 = await finding("f4", o2, "Few comprehension questions", "Questions were recall-only; no inference or text evidence.", "Literacy", "ai_suggested")

        async def gap(key, o, f, title, desc, subject, grade, severity, status):
            return await self.ensure(LearningGap, f"gap:{key}", observation_id=o.id,
                                     observation_finding_id=f.id if f else None, title=title, description=desc,
                                     subject=subject, grade=grade, severity=severity, status=status,
                                     created_by=mentor.id, updated_by=mentor.id)

        g1 = await gap("g1", o1, f1, "Reasoning about equivalent fractions", "Students apply the rule but cannot explain why fractions are equivalent.", "Mathematics", "6", "high", "addressed")
        g2 = await gap("g2", o1, None, "Explaining mathematical thinking", "Few students can explain their reasoning aloud.", "Mathematics", "6", "medium", "identified")
        g3 = await gap("g3", o2, f4, "Inferential comprehension", "Children cannot answer 'why' questions using evidence from the text.", "English", "4", "high", "identified")
        await gap("g4", o2, None, "Decoding fluency", "A small group still sounds out common words slowly.", "English", "4", "low", "resolved")

        async def rec(key, g, title, desc, rationale, cat, status, comment=None):
            return await self.ensure(Recommendation, f"rec:{key}", learning_gap_id=g.id, title=title,
                                     description=desc, rationale=rationale, category=cat, status=status,
                                     mentor_comment=comment, created_by=mentor.id, updated_by=mentor.id)

        r1 = await rec("r1", g1, "Use fraction strips and number lines", "Students fold paper strips to compare 1/2, 2/4 and 4/8 before writing the rule.", "Concrete and visual models build understanding before symbolic rules.", "Pedagogy", "mentor_approved", "Teacher agreed to try in the next unit.")
        await rec("r2", g2, "Think-pair-share before answering", "Give 30 seconds thinking time and let pairs discuss before calling on students.", "Increases participation and reasoning talk.", "Classroom interaction", "ai_suggested")
        r3 = await rec("r3", g3, "Read-aloud with question stems", "During read-aloud, pause to ask 'How do you know?' and model finding the answer in the text.", "Explicit modelling of inference strategies.", "Literacy", "mentor_approved")
        await rec("r4", g3, "Graphic organisers for every story", "Complete a story map after each reading.", "Supports story structure.", "Literacy", "rejected", "Too time-consuming for this class right now.")

        # ---------------- Action plans / steps / follow-ups ----------------
        p1 = await self.ensure(ActionPlan, "plan:p1", recommendation_id=r1.id, title="Fractions with concrete models",
                               description="Two-week plan to introduce fraction strips and number lines in Class 6-A.",
                               responsible_person="Meena Krishnan", start_date=self.d(-12), due_date=self.d(10),
                               status="in_progress", mentor_comment="Approved after debrief.",
                               created_by=mentor.id, updated_by=mentor.id)
        p2 = await self.ensure(ActionPlan, "plan:p2", recommendation_id=r3.id, title="Daily read-aloud with inference questions",
                               description="Daily 10-minute read-aloud with 'How do you know?' prompts in Class 4-A.",
                               responsible_person="Anitha Selvam", start_date=self.d(-7), due_date=self.d(14),
                               status="approved", created_by=mentor.id, updated_by=mentor.id)
        await self.ensure(ActionPlan, "plan:p3", recommendation_id=r3.id, title="Peer reading circles (draft)",
                          description="Weekly peer reading circles to practise answering why-questions.",
                          responsible_person="Anitha Selvam", start_date=self.d(3), due_date=self.d(30),
                          status="pending_approval", created_by=mentor.id, updated_by=mentor.id)

        async def step(key, p, title, desc, person, due, status, notes=None):
            return await self.ensure(ActionPlanStep, f"step:{key}", action_plan_id=p.id, title=title, description=desc,
                                     responsible_person=person, due_date=self.d(due), status=status,
                                     completion_notes=notes, created_by=mentor.id, updated_by=mentor.id)

        s1 = await step("s1", p1, "Mentor models a fraction-strips lesson", "Demonstration lesson in Class 6-A.", "Kavya Subramanian", -5, "completed", "Demo lesson done; teacher co-taught.")
        s2 = await step("s2", p1, "Teacher runs strip activity independently", "Teacher conducts the activity with all groups.", "Meena Krishnan", 2, "in_progress")
        await step("s3", p1, "Exit-ticket check on equivalence", "Short written check: explain why 3/6 = 1/2.", "Meena Krishnan", 8, "pending")
        s4 = await step("s4", p2, "Start daily read-aloud routine", "10 minutes after lunch with two inference prompts.", "Anitha Selvam", 1, "pending")
        s5 = await step("s5", p2, "Prepare question-stem cards", "Make laminated 'How do you know?' cards.", "Anitha Selvam", -1, "pending")

        async def follow(key, st, tkey, desc, status, response=None, notes=None, responded=None, verified=None):
            return await self.ensure(FollowUp, f"fu:{key}", action_plan_step_id=st.id, teacher_id=teachers[tkey].id,
                                     description=desc, status=status, teacher_response=response, mentor_notes=notes,
                                     responded_at=responded, verified_at=verified, created_by=mentor.id, updated_by=mentor.id)

        await follow("fu1", s1, "t1", "Reflect on the demonstration lesson", "closed", "Students were very engaged with the strips.", "Good reflection.", self.at(-4), self.at(-3))
        await follow("fu2", s2, "t1", "Share photos of student strip work", "evidence_submitted", "Photos of three groups' strips shared.", None, self.at(-1))
        await follow("fu3", s4, "t4", "Confirm read-aloud schedule", "teacher_responded", "Will start after lunch from Monday.", None, self.at(-1))
        await follow("fu4", s5, "t4", "Send a photo of the question cards", "pending")
        await follow("fu5", s2, "t1", "Add one exit question to each lesson", "needs_revision", "Added questions.", "Questions were recall-only; please add one 'explain why' question.", self.at(-2), self.at(-1))

        # ---------------- Mentor tasks ----------------
        task_specs = [
            ("k1", None, "Submit monthly mentoring report to block office", "reporting", 120, -2, "pending", 80, 70, 60),
            ("k2", "s1", "Prepare feedback notes for Meena Krishnan", "feedback", 45, 1, "in_progress", 70, 80, 40),
            ("k3", "s2", "Print question-stem cards for Class 4-A", "preparation", 30, 1, "pending", 60, 60, 30),
            ("k4", "s4", "Call head teacher to confirm first visit", "coordination", 15, 2, "pending", 75, 50, 50),
            ("k5", "s3", "Review science lesson plans before follow-up visit", "preparation", 60, 5, "pending", 40, 70, 30),
            ("k6", None, "Prepare cluster meeting presentation", "meeting", 90, 7, "pending", 30, 60, 20),
            ("k7", "s1", "Upload evidence from fractions demo lesson", "documentation", 20, -6, "completed", 50, 40, 20),
            ("k8", "s2", "Share phonics routine with neighbouring school", "collaboration", 30, 12, "cancelled", 10, 30, 10),
        ]
        for key, skey, title, cat, minutes, due, status, urg, imp, risk in task_specs:
            existing = await self.db.get(MentorTask, uid(f"task:{key}"))
            if existing is not None:
                continue
            t = MentorTask(
                id=uid(f"task:{key}"), school_id=schools[skey].id if skey else None, title=title, category=cat,
                estimated_minutes=minutes, due_at=self.at(due, 17), status=status, urgency=urg, impact=imp, risk=risk,
                deadline_proximity=max(0, min(100, 100 - due * 10)), workload_dependency=30,
                mentor_id=mentor.id, created_by=mentor.id, updated_by=mentor.id,
                completed_at=self.at(due - 1, 16) if status == "completed" else None,
            )
            apply_priority(t)
            self.db.add(t)
            self.created += 1
        await self.db.flush()

        # ---------------- Schedules (visit time proposals) ----------------
        for key, v, skey, status in (("sch1", v5, "s2", "accepted"), ("sch2", v6, "s4", "proposed")):
            await self.ensure(Schedule, f"schedule:{key}", school_visit_id=v.id, school_id=schools[skey].id,
                              proposed_start_at=v.scheduled_at, proposed_end_at=v.scheduled_at + timedelta(hours=3),
                              estimated_travel_minutes=schools[skey].travel_minutes_from_base, status=status,
                              notes="Includes travel from block resource centre.",
                              created_by=mentor.id, updated_by=mentor.id)

        # ---------------- Welcome notification ----------------
        await self.ensure(Notification, "notif:welcome", user_id=mentor.id, title="Welcome to MARG",
                          message="Your demo workspace has 4 assigned schools with visits, observations and action plans.",
                          notification_type="system", is_read=False)

        await db.commit()


async def _reset_demo_db() -> None:
    async with engine.begin() as conn:
        tables = (
            await conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"
            ))
        ).scalars().all()
        await conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))


async def main(reset: bool) -> None:
    db_name = make_url(settings.database_url).database or ""
    if not db_name.endswith("_demo"):
        raise SystemExit(f"Refusing to seed demo data into '{db_name}'. Point DATABASE_URL at a *_demo database.")
    if settings.is_production and os.environ.get("ALLOW_DEMO_SEED_IN_PRODUCTION") != "1":
        raise SystemExit("Refusing to seed demo data with APP_ENV=production (set ALLOW_DEMO_SEED_IN_PRODUCTION=1 for a hosted demo).")

    password = os.environ.get("DEMO_PASSWORD")
    generated = False
    if not password:
        password = secrets.token_urlsafe(12)
        generated = True
    if len(password) < 12:
        raise SystemExit("DEMO_PASSWORD must be at least 12 characters.")

    if reset:
        await _reset_demo_db()
        print(f"Demo database '{db_name}' reset.")

    today = datetime.now(IST).date()
    async with AsyncSessionLocal() as db:
        seeder = Seeder(db, password, today, set_password=not generated)
        await seeder.run()
        reminders = await generate_reminders(db)

    print(f"Demo data ready in '{db_name}': {seeder.created} record(s) created, {reminders} reminder(s).")
    print(f"  Mentor login:       {DEMO_MENTOR_EMAIL}")
    print(f"  Second mentor:      {DEMO_MENTOR2_EMAIL}  (data isolation checks)")
    print(f"  Administrator:      {DEMO_ADMIN_EMAIL}  (school assignments only)")
    if seeder.created and generated:
        print(f"  Generated password: {password}   <- shown once; store it securely")
    elif generated:
        print("  (Existing accounts kept their original password.)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed MARG demonstration data")
    parser.add_argument("--reset", action="store_true", help="Wipe the *_demo database first")
    asyncio.run(main(parser.parse_args().reset))

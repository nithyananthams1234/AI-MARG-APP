"""Replace visible placeholder text on the existing synthetic MARG records.

The script updates only deterministic UUIDs created by seed_synthetic_dataset.
It does not insert or delete rows. By default it verifies rollback; use
``--apply`` to commit the reviewed text changes.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
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
SEED_MARKER = "AIMARG-DEMO-2026-11"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

SCHOOLS = (
    ("Aadhirai Government Higher Secondary School", "AAD-GHSS-GUD", "Vellore", "Gudiyatham"),
    ("Thendral Government Higher Secondary School", "THD-GHSS-ARC", "Ranipet", "Arcot"),
    ("Malarvizhi Government Higher Secondary School", "MLV-GHSS-ARN", "Tiruvannamalai", "Arani"),
    ("Semmozhi Government Higher Secondary School", "SMZ-GHSS-TPT", "Tirupattur", "Tirupattur"),
    ("Pooncholai Government Higher Secondary School", "PNC-GHSS-VPM", "Villupuram", "Villupuram"),
    ("Iniya Government High School", "INI-GHS-RPT", "Ranipet", "Ranipet"),
    ("Arivoli Government High School", "ARV-GHS-AMB", "Tirupattur", "Ambur"),
    ("Nilam Government High School", "NLM-GHS-ATT", "Salem", "Attur"),
    ("Vennila Government High School", "VNL-GHS-ODC", "Dindigul", "Oddanchatram"),
    ("Kayal Government High School", "KYL-GHS-KMB", "Thanjavur", "Kumbakonam"),
    ("Marudham Panchayat Union Middle School", "MRD-PUMS-LGD", "Tiruchirappalli", "Lalgudi"),
    ("Punnagai Panchayat Union Middle School", "PNG-PUMS-MLR", "Madurai", "Melur"),
    ("Kuyil Panchayat Union Middle School", "KYL-PUMS-UTH", "Kancheepuram", "Uthiramerur"),
    ("Paavai Panchayat Union Middle School", "PAV-PUMS-GNJ", "Villupuram", "Gingee"),
    ("Mullai Panchayat Union Middle School", "MLL-PUMS-PRD", "Erode", "Perundurai"),
    ("Vaanavil Matriculation Higher Secondary School", "VNL-MHSS-TCD", "Namakkal", "Tiruchengode"),
    ("Inbam Matriculation Higher Secondary School", "INB-MHSS-BVN", "Erode", "Bhavani"),
    ("Puthuyugam Matriculation Higher Secondary School", "PTY-MHSS-NTM", "Dindigul", "Natham"),
    ("Oviya Matriculation Higher Secondary School", "OVY-MHSS-PTK", "Thanjavur", "Pattukkottai"),
    ("Aruvi Matriculation Higher Secondary School", "ARV-MHSS-TGM", "Madurai", "Thirumangalam"),
)

TEACHERS = (
    ("Kavitha Raman", "kavitha.raman", "Mathematics"),
    ("S. Prabhu", "s.prabhu", "Science"),
    ("Nandhini Selvam", "nandhini.selvam", "Tamil"),
    ("Josephine Mary", "josephine.mary", "English"),
    ("Ramesh Kumar", "ramesh.kumar", "Social Studies"),
    ("Meera Lakshmi", "meera.lakshmi", "Mathematics"),
    ("Karthik Raj", "karthik.raj", "Science"),
    ("Uma Devi", "uma.devi", "English"),
    ("Senthil Nathan", "senthil.nathan", "Tamil"),
    ("Revathi Anand", "revathi.anand", "Mathematics"),
    ("Arunmozhi Vel", "arunmozhi.vel", "Social Studies"),
    ("Farzana Begum", "farzana.begum", "Science"),
    ("Chitra Balan", "chitra.balan", "Tamil"),
    ("Gokul Raj", "gokul.raj", "English"),
    ("Thenmozhi Kannan", "thenmozhi.kannan", "Mathematics"),
    ("Priyanka Moorthy", "priyanka.moorthy", "Science"),
    ("Muthuvel Arasi", "muthuvel.arasi", "Tamil"),
    ("Anandhi Suresh", "anandhi.suresh", "English"),
    ("Balaji Prakash", "balaji.prakash", "Mathematics"),
    ("Yasmin Fathima", "yasmin.fathima", "Social Studies"),
)

TASKS = (
    ("Review Grade 8 mathematics lesson plan", "Check alignment between the lesson objective, worked examples, and independent practice before the next mentoring visit."),
    ("Observe classroom questioning techniques", "Record the balance of recall, reasoning, and open-ended questions using an aggregate tally."),
    ("Follow up on foundational literacy improvement", "Review the teacher's decoding and fluency routine using group-level progress notes only."),
    ("Review aggregate student attendance trends", "Compare class-level weekly attendance totals and prepare discussion prompts; do not record learner identities."),
    ("Discuss formative assessment practices", "Review how short checks for understanding are used to adjust instruction during the lesson."),
    ("Prepare fraction-model teaching materials", "Assemble visual fraction strips and number-line examples for a Grade 6 co-planning session."),
    ("Review participation in group activities", "Check whether group roles and reporting opportunities are distributed across the class."),
    ("Plan a Grade 8 science inquiry lesson", "Review the investigation question, materials, safety steps, and learner prediction prompts."),
    ("Check reading-comprehension action-plan progress", "Review the planned inference questions and aggregate exit-ticket results with the teacher."),
    ("Prepare feedback notes for a classroom observation", "Summarise observed strengths and one actionable next step using evidence from the lesson."),
    ("Review timetable alignment for mentoring visits", "Check proposed visit periods against the recorded class timetable before confirming travel."),
    ("Follow up on inclusive participation strategies", "Review the use of wait time, paired discussion, and varied response formats."),
    ("Compare aggregate formative-check results", "Compare class-level results across two checks and identify concepts needing reteaching."),
    ("Coordinate a teacher peer-learning meeting", "Prepare a short agenda for teachers to exchange one tested classroom strategy."),
    ("Review lesson objectives and success criteria", "Check that learners can understand the objective and how success will be recognised."),
    ("Prepare notes for the next mentor visit", "Review the previous visit actions and prepare focused questions for the follow-up conversation."),
    ("Submit the monthly mentoring summary", "Compile visit, observation, and action-plan progress totals for the monthly review."),
    ("Document the completed fraction-strip activity", "Record the activity completion and aggregate learner response for the action-plan review."),
    ("Review reading-fluency follow-up responses", "Check the teacher's reported routine and note any group-level support needs."),
    ("Update the schedule after an accepted visit proposal", "Confirm the visit date and duration match the accepted schedule record."),
    ("Compile aggregate classroom-participation trends", "Summarise participation tallies without retaining names or individual learner records."),
    ("Share a formative-assessment reflection prompt", "Prepare a discussion prompt on how evidence from a lesson changed the next teaching step."),
    ("Cancel the postponed classroom observation", "Close planning for the postponed visit and retain the existing cancellation status."),
    ("Close the duplicate visit-planning task", "Retain the cancellation record and avoid duplicating the active visit plan."),
)

VISIT_PURPOSES = (
    "Review Grade 4 fraction models and discuss learner explanations with the teacher.",
    "Observe Grade 5 science questioning and plan a short prediction activity.",
    "Review Grade 6 Tamil reading comprehension and discuss text-based responses.",
    "Observe Grade 7 English inference prompts and agree on a follow-up check.",
    "Review Grade 8 map-reading activities and classroom participation routines.",
    "Co-plan Grade 9 mathematics examples and success criteria.",
    "Review Grade 10 science practical preparation and group safety routines.",
    "Observe Grade 4 English decoding practice and differentiated reading support.",
    "Discuss Grade 5 Tamil vocabulary and oral reading routines.",
    "Review Grade 6 mathematics exit checks and common misconceptions.",
    "Observe Grade 7 social studies source interpretation and learner discussion.",
    "Review Grade 8 science predictions and evidence-based explanations.",
    "Follow up on the agreed classroom questioning strategy.",
    "Review class-level attendance trends and barriers to regular participation.",
    "Conduct a mentoring conversation on formative assessment routines.",
    "Observe use of group roles during a collaborative lesson.",
    "Review an action-plan milestone and the next measurable classroom step.",
    "Discuss foundational literacy practice and aggregate progress checks.",
    "Review lesson objectives and learner-friendly success criteria.",
    "Plan a peer-learning discussion on inclusive classroom participation.",
    "Check the implementation of visual models in mathematics lessons.",
    "Review a science inquiry lesson and evidence of learner reasoning.",
    "Visit postponed following a school calendar change; rescheduling required.",
    "Visit cancelled after a duplicate planning entry was identified.",
)

OBSERVATIONS = (
    ("Using visual models for multiplication", "Grade 4 mathematics lesson used arrays and equal groups. Learners completed a short explanation task; an aggregate tally showed that several could calculate but needed prompts to explain the grouping.", "Connect equal groups to multiplication", "A portion of the class calculated correctly but did not yet explain how equal groups represent multiplication.", "Mathematical reasoning", "Use counters and arrays before recording the multiplication sentence.", "Plan two short lessons that move from counters to drawings to equations, then compare aggregate exit-ticket results.", "Build multiplication explanations with concrete models", "Use counters and arrays, then ask learners to describe the relationship between groups and total.", "Concrete-to-representational practice supports explanation before symbol use."),
    ("Questioning during a science investigation", "Grade 5 science discussion introduced shadows and light sources. Questions mostly checked recall; an aggregate observation showed opportunities for learners to predict and explain changes.", "Develop prediction and explanation", "Learners named the observed change but needed structured prompts to explain how the light source affected the shadow.", "Science inquiry", "Ask learners to predict, observe, and explain one change in shadow length.", "Use a predict-observe-explain routine and review a class-level response tally after the next investigation.", "Use predict-observe-explain prompts", "Pause before the demonstration for predictions and revisit the explanation after observation.", "Structured inquiry prompts make reasoning visible during practical learning."),
    ("Reading for meaning in Tamil", "Grade 6 Tamil reading included fluent shared reading. Follow-up questions focused mainly on word recall; learners needed more opportunities to cite a detail from the passage.", "Support text-based comprehension", "Some learners recalled details but needed prompts to connect an answer to evidence in the passage.", "Language and literacy", "Model one answer that points to a phrase in the text, then use paired discussion.", "Add two evidence-based questions to the next reading lesson and review an anonymised response tally.", "Model answers using passage evidence", "Think aloud while locating a phrase that supports an answer, then invite paired practice.", "Explicit modelling and paired rehearsal support comprehension."),
    ("Inference prompts in an English lesson", "Grade 7 English lesson included a clear read-aloud and vocabulary check. Learners had limited wait time before answers were supplied.", "Increase inference and wait time", "Learners need additional think time and prompts to infer meaning from clues in the text.", "English comprehension", "Use a 'What makes you think that?' prompt and allow silent thinking before responses.", "Use three inference prompts in the next lesson and record aggregate participation totals.", "Use inference prompts with planned wait time", "Ask learners to cite a clue and provide quiet thinking time before discussion.", "Wait time and evidence prompts encourage independent reasoning."),
    ("Interpreting maps in social studies", "Grade 8 social studies lesson used a wall map. Most learners followed the teacher explanation; small-group map interpretation would create more active practice.", "Strengthen independent map interpretation", "Learners need guided practice using map symbols and scale rather than relying only on teacher explanation.", "Social studies", "Set a short pair task to locate a feature and explain which map key supports the answer.", "Use a map-key task in two lessons and review a class-level completion tally.", "Add paired map-key interpretation", "Provide a simple map task and ask each pair to justify one location using the key.", "Guided peer practice supports transfer from demonstration to independent use."),
    ("Checking understanding in mathematics", "Grade 9 mathematics lesson showed clear worked examples. The class check at the end did not distinguish procedural accuracy from conceptual understanding.", "Check reasoning as well as accuracy", "Learners need a brief explanation prompt alongside the numerical answer to reveal conceptual understanding.", "Mathematical assessment", "Add one 'explain why' item to the exit check and review responses by misconception category.", "Use a two-part exit check for three lessons and compare aggregate response patterns.", "Add reasoning to the exit check", "Pair one calculation item with a short explanation prompt and use results to plan reteaching.", "A two-part check distinguishes calculation fluency from reasoning."),
    ("Participation in a science practical", "Grade 10 science practical was demonstrated clearly at the front. Rotating roles and shared materials could widen hands-on participation.", "Broaden practical participation", "Practical work would benefit from structured roles so more groups handle materials and explain observations.", "Practical science", "Assign rotating observer, materials, and reporter roles during the next investigation.", "Use role rotation in the next practical and collect an aggregate group-participation tally.", "Rotate roles in practical groups", "Plan roles before the practical and rotate them at the next investigation.", "Defined rotating roles create more opportunities for active participation."),
    ("Foundational decoding practice", "Grade 4 English warm-up included sound review. A short teacher-led segment can be balanced with paired practice and a brief fluency check.", "Build repeated reading fluency", "Some learners need more opportunities to practise familiar text with supportive feedback.", "Foundational literacy", "Add a short paired rereading routine and track only group-level fluency bands.", "Use paired rereading twice weekly and compare aggregate fluency checks after two weeks.", "Add paired rereading practice", "Use a familiar short passage, partner turns, and supportive correction.", "Repeated supported practice builds confidence and automaticity."),
    ("Vocabulary and oral reading in Tamil", "Grade 5 Tamil lesson introduced new vocabulary before reading. Learners would benefit from using selected words in oral summaries.", "Use new vocabulary in context", "Learners recognised several new words but need practice using them to summarise the passage.", "Tamil literacy", "Select three words for a paired oral summary after reading.", "Use a short vocabulary summary task and review aggregate completion after the next reading cycle.", "Practise vocabulary in oral summaries", "Invite pairs to use target words while summarising a short passage.", "Applying vocabulary in context reinforces meaning and oral language."),
    ("Fraction reasoning and exit tickets", "Grade 6 mathematics lesson used fraction strips. A class-level check suggested some learners still relied on the procedure without comparing equivalent lengths.", "Explain equivalent fractions visually", "Learners need repeated opportunities to connect equivalent fractions to equal lengths on a model.", "Fractions", "Compare two equivalent strips and ask learners to justify the match.", "Use fraction strips in three lessons and review an anonymised exit-ticket tally.", "Use fraction strips to justify equivalence", "Move from matching strips to drawing and explaining equivalent fractions.", "Visual comparison supports conceptual understanding of equivalence."),
    ("Evidence in social studies discussion", "Grade 7 social studies discussion included multiple viewpoints. Learners need a routine for supporting an opinion with a source detail.", "Support claims with source evidence", "Learners expressed opinions but did not consistently refer to evidence in the source.", "Social studies reasoning", "Use a claim-evidence sentence frame during paired discussion.", "Apply the sentence frame in two discussions and record an aggregate evidence-use tally.", "Use a claim-and-evidence discussion frame", "Model a claim supported by one source detail before paired discussion.", "Sentence frames scaffold evidence-based explanations."),
    ("Explaining results in science", "Grade 8 science activity included a prediction stage. The class debrief can make links between prediction, observation, and evidence more explicit.", "Connect observations to explanations", "Learners recorded observations but need support using them to justify a conclusion.", "Scientific reasoning", "Ask groups to cite one observation that supports their conclusion.", "Use a brief evidence-based conclusion prompt and review group-level responses.", "Require evidence in science conclusions", "Provide a conclusion frame that links claim, observation, and explanation.", "Explicit links between evidence and claims strengthen scientific reasoning."),
)

PLANS = (
    ("Explain multiplication through arrays", "Over three weeks, build Grade 4 understanding from equal groups to arrays and equations; review an aggregate exit-check tally at the end of each week.", "Model arrays across three lessons", "Use counters, draw arrays, and ask learners to explain how rows and columns represent equal groups."),
    ("Strengthen science prediction and explanation", "Over two weeks, use predict-observe-explain prompts in Grade 5 science and review aggregate participation after each investigation.", "Use a prediction prompt in two investigations", "Ask learners to make a prediction, record an observation, and explain one change."),
    ("Build evidence-based Tamil comprehension", "Across four reading lessons, model text evidence and use paired discussion before collecting an anonymised response tally.", "Add evidence questions to four readings", "Ask one inference question and one text-evidence question during each reading lesson."),
    ("Increase reasoning in English discussions", "Across three Grade 7 lessons, add planned wait time and evidence prompts; review aggregate participation at the end of the sequence.", "Use three inference prompts with wait time", "Provide silent thinking time and invite learners to cite a text clue."),
    ("Develop independent map interpretation", "Within three weeks, use paired map-key tasks and record class-level completion and explanation totals.", "Use paired map tasks twice weekly", "Ask pairs to locate a feature and justify the answer using a map key."),
    ("Check mathematical reasoning with exit tickets", "For three weeks, pair calculation checks with a short explanation item and use aggregate results to plan responsive teaching.", "Add an explanation item to three exit checks", "Review the calculation and explanation separately, then group common misconceptions."),
)

FOLLOWUP_ACTIONS = (
    ("Share the class-level explanation tally after the array lessons.", "Teacher reports that array drawings were used in three lessons; the class-level exit-check tally is ready for review.", "Review the aggregate tally together and agree on the next example."),
    ("Describe how prediction prompts were used in the science lesson.", "Teacher reports using a prediction question before the demonstration and collecting group explanations.", "Discuss which prompt helped learners connect observation and explanation."),
    ("Record the aggregate response pattern for the Tamil reading questions.", "Teacher reports that paired discussion was followed by a text-evidence question; responses were reviewed as a class-level tally.", "Select one anonymised response pattern for the next planning conversation."),
    ("Review the next inference discussion using the planned wait time.", "Teacher reports allowing silent thinking time before inviting learners to cite a text clue.", "Review participation totals and decide whether the wait time should be adjusted."),
    ("Share the map-task completion tally after paired practice.", "Teacher reports that pairs used the map key and explained one location choice.", "Identify any map symbol that needs another modelled example."),
    ("Review aggregate exit-check results for calculation and explanation.", "Teacher reports using a two-part exit check and grouping common misconceptions without recording learner names.", "Agree on one targeted example for the next mathematics lesson."),
)

NOTIFICATIONS = (
    ("Review mathematics lesson plan", "The Grade 8 mathematics lesson-plan review is due. Check that the objective, examples, and independent practice align."),
    ("Classroom questioning follow-up", "Review the aggregate questioning tally and agree on one reasoning prompt for the next lesson."),
    ("Foundational literacy follow-up", "Check the paired-reading routine and discuss the group-level fluency check."),
    ("Attendance trend review", "Prepare the class-level attendance summary for the next mentoring conversation."),
    ("Action-plan evidence to review", "A teacher response is ready for mentor review. Discuss the evidence and decide the next support step."),
    ("Mentoring workspace ready", "Your assigned schools and current mentoring activities are available in the workspace."),
    ("Upcoming visit preparation", "Review the accepted visit schedule and prepare the classroom observation focus."),
    ("Formative assessment task due", "Review the two-part exit-check results and identify any aggregate misconception pattern."),
)


def stable_id(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


async def one(db: AsyncSession, model: type, key: str, mentor_id: uuid.UUID):
    obj = await db.get(model, stable_id(key))
    if obj is None:
        raise RuntimeError(f"Expected seeded record is missing: {model.__tablename__}.")
    if model is Notification:
        if obj.user_id != mentor_id:
            raise RuntimeError("Seed notification owner did not match the active Mentor.")
    elif getattr(obj, "created_by", None) != mentor_id:
        raise RuntimeError(f"Seed ownership check failed for {model.__tablename__}.")
    return obj


async def all_records(db: AsyncSession, mentor: User) -> dict[str, list[Any]]:
    records: dict[str, list[Any]] = {}
    groups = (
        ("schools", School, [f"school:{i:02d}" for i in range(1, 21)]),
        ("assignments", MentorSchool, [f"mentor-school:{i:02d}" for i in range(1, 21)]),
        ("teachers", Teacher, [f"teacher:{i:02d}" for i in range(1, 21)]),
        ("school_teachers", SchoolTeacher, [f"school-teacher:{i:02d}" for i in range(1, 21)]),
        ("classrooms", Classroom, [f"classroom:{i:02d}" for i in range(1, 21)]),
        ("timetables", Timetable, [f"timetable:{i:02d}:{day}" for i in range(1, 21) for day in WEEKDAYS]),
        ("visits", SchoolVisit, [f"visit:{i:02d}" for i in range(1, 25)]),
        ("schedules", Schedule, [f"schedule:{i:02d}" for i in range(1, 23)]),
        ("tasks", MentorTask, [f"task:{i:02d}" for i in range(1, 25)]),
        ("observations", Observation, [f"observation:{i:02d}" for i in range(1, 13)]),
        ("findings", ObservationFinding, [f"finding:{i:02d}" for i in range(1, 13)]),
        ("gaps", LearningGap, [f"gap:{i:02d}" for i in range(1, 13)]),
        ("recommendations", Recommendation, [f"recommendation:{i:02d}" for i in range(1, 13)]),
        ("plans", ActionPlan, [f"action-plan:{i:02d}" for i in range(1, 7)]),
        ("steps", ActionPlanStep, [f"action-plan-step:{i:02d}" for i in range(1, 7)]),
        ("followups", FollowUp, [f"follow-up:{i:02d}" for i in range(1, 7)]),
        ("notifications", Notification, [f"notification:{i:02d}" for i in range(1, 9)]),
    )
    for label, model, keys in groups:
        records[label] = [
            await one(db, model, key, mentor.id) for key in keys
        ]
    return records


def set_fields(
    obj: Any,
    values: dict[str, Any],
    before: list[tuple[type, uuid.UUID, str, Any]],
) -> None:
    for field, value in values.items():
        before.append((type(obj), obj.id, field, getattr(obj, field)))
        setattr(obj, field, value)


def build_updates(records: dict[str, list[Any]]) -> list[tuple[Any, dict[str, Any]]]:
    updates: list[tuple[Any, dict[str, Any]]] = []
    schools = records["schools"]
    teachers = records["teachers"]
    classrooms = records["classrooms"]
    visits = records["visits"]
    observations = records["observations"]
    findings = records["findings"]
    gaps = records["gaps"]
    recommendations = records["recommendations"]
    plans = records["plans"]
    steps = records["steps"]
    followups = records["followups"]

    for i, (name, code, district, town) in enumerate(SCHOOLS, start=1):
        updates.append((schools[i - 1], {
            "name": name,
            "code": code,
            "address": f"{town} town",
            "district": district,
            "block": town,
            "state": "Tamil Nadu",
        }))

    for i, (name, email_slug, subject) in enumerate(TEACHERS, start=1):
        school_code = SCHOOLS[i - 1][1]
        short_code = school_code.split("-")[0]
        updates.append((teachers[i - 1], {
            "full_name": name,
            "employee_code": f"EDU-{short_code}-{i:02d}",
            "email": f"{email_slug}@fictional.invalid",
            "phone": None,
        }))
        for day in WEEKDAYS:
            timetable = next(
                row for row in records["timetables"]
                if row.classroom_id == classrooms[i - 1].id and row.day_of_week == day
            )
            updates.append((timetable, {"subject": subject}))

    for i, purpose in enumerate(VISIT_PURPOSES, start=1):
        updates.append((visits[i - 1], {"notes": purpose}))

    schedules_by_visit = {row.school_visit_id: row for row in records["schedules"]}
    for index, visit in enumerate(visits):
        schedule = schedules_by_visit.get(visit.id)
        if schedule is not None:
            updates.append((schedule, {
                "notes": f"Mentoring proposal: {VISIT_PURPOSES[index]}",
            }))

    for i, (title, description) in enumerate(TASKS, start=1):
        updates.append((records["tasks"][i - 1], {
            "title": title,
            "description": description,
        }))

    for i, data in enumerate(OBSERVATIONS, start=1):
        (
            topic, notes, finding_title, finding_description, finding_category,
            gap_title, gap_description, recommendation_title,
            recommendation_description, rationale,
        ) = data
        recommendation_category = finding_category
        observation = observations[i - 1]
        teacher_index = i - 1
        updates.append((observation, {
            "subject": TEACHERS[teacher_index][2],
            "topic": topic,
            "notes": notes,
        }))
        finding = findings[i - 1]
        updates.append((finding, {
            "title": finding_title,
            "description": finding_description,
            "category": finding_category,
            "mentor_comment": "Discussed as a coaching focus during the mentoring conversation.",
        }))
        gap = gaps[i - 1]
        updates.append((gap, {
            "title": gap_title,
            "description": gap_description,
            "subject": TEACHERS[teacher_index][2],
            "grade": classrooms[teacher_index].grade,
        }))
        recommendation = recommendations[i - 1]
        updates.append((recommendation, {
            "title": recommendation_title,
            "description": recommendation_description,
            "rationale": rationale,
            "category": recommendation_category,
            "mentor_comment": "Agreed next step for the mentoring cycle.",
        }))

    for i, (title, description, step_title, step_description) in enumerate(PLANS, start=1):
        plan = plans[i - 1]
        teacher_index = i - 1
        updates.append((plan, {
            "title": title,
            "description": description,
            "responsible_person": TEACHERS[teacher_index][0],
            "mentor_comment": "Progress will be reviewed against the agreed classroom evidence.",
        }))

        # Existing seed relationships attach two steps to plans 3, 4 and 5.
        if i in (3, 4, 5):
            step_indices = (i - 3) * 2
            for offset in range(2):
                step_index = step_indices + offset
                step = steps[step_index]
                updates.append((step, {
                    "title": step_title if offset == 0 else f"Review progress: {step_title}",
                    "description": step_description,
                    "responsible_person": TEACHERS[teacher_index][0],
                    "completion_notes": (
                        "Completed using an aggregate class-level review."
                        if step.status == "completed"
                        else None
                    ),
                }))
                followup = followups[step_index]
                follow_description, teacher_response, mentor_notes = FOLLOWUP_ACTIONS[step_index]
                updates.append((followup, {
                    "description": follow_description,
                    "teacher_response": (
                        teacher_response
                        if followup.teacher_response is not None
                        else None
                    ),
                    "mentor_notes": (
                        mentor_notes
                        if followup.mentor_notes is not None
                        else None
                    ),
                }))

    for i, (title, message) in enumerate(NOTIFICATIONS, start=1):
        updates.append((records["notifications"][i - 1], {
            "title": title,
            "message": message,
        }))

    return updates


def validate_relations(records: dict[str, list[Any]]) -> None:
    expected_school_ids = {row.id for row in records["schools"]}
    expected_teacher_ids = {row.id for row in records["teachers"]}
    expected_classroom_ids = {row.id for row in records["classrooms"]}
    expected_visit_ids = {row.id for row in records["visits"]}
    expected_observation_ids = {row.id for row in records["observations"]}
    expected_finding_ids = {row.id for row in records["findings"]}
    expected_gap_ids = {row.id for row in records["gaps"]}
    expected_recommendation_ids = {row.id for row in records["recommendations"]}
    expected_plan_ids = {row.id for row in records["plans"]}
    expected_step_ids = {row.id for row in records["steps"]}

    if any(row.school_id not in expected_school_ids for row in records["assignments"]):
        raise RuntimeError("Seed assignment points outside the deterministic school set.")
    if any(row.user_id != records["assignments"][0].user_id for row in records["assignments"]):
        raise RuntimeError("Seed assignments do not have a consistent Mentor.")
    if any(row.school_id not in expected_school_ids or row.teacher_id not in expected_teacher_ids
           for row in records["school_teachers"]):
        raise RuntimeError("Seed school-teacher link points outside the deterministic set.")
    if any(row.school_id not in expected_school_ids for row in records["classrooms"]):
        raise RuntimeError("Seed classroom points outside the deterministic school set.")
    if any(row.classroom_id not in expected_classroom_ids for row in records["timetables"]):
        raise RuntimeError("Seed timetable points outside the deterministic classroom set.")
    if any(row.school_id not in expected_school_ids for row in records["visits"]):
        raise RuntimeError("Seed visit points outside the deterministic school set.")
    if any(row.school_id not in expected_school_ids or row.school_visit_id not in expected_visit_ids
           for row in records["schedules"]):
        raise RuntimeError("Seed schedule points outside the deterministic visit/school set.")
    if any(row.school_visit_id not in expected_visit_ids or row.teacher_id not in expected_teacher_ids
           or row.classroom_id not in expected_classroom_ids for row in records["observations"]):
        raise RuntimeError("Seed observation points outside the deterministic parent set.")
    if any(row.observation_id not in expected_observation_ids for row in records["findings"]):
        raise RuntimeError("Seed finding points outside the deterministic observation set.")
    if any(row.observation_id not in expected_observation_ids
           or row.observation_finding_id not in expected_finding_ids for row in records["gaps"]):
        raise RuntimeError("Seed gap points outside the deterministic observation/finding set.")
    if any(row.learning_gap_id not in expected_gap_ids for row in records["recommendations"]):
        raise RuntimeError("Seed recommendation points outside the deterministic gap set.")
    if any(row.recommendation_id not in expected_recommendation_ids for row in records["plans"]):
        raise RuntimeError("Seed action plan points outside the deterministic recommendation set.")
    if any(row.action_plan_id not in expected_plan_ids for row in records["steps"]):
        raise RuntimeError("Seed step points outside the deterministic plan set.")
    if any(row.action_plan_step_id not in expected_step_ids or row.teacher_id not in expected_teacher_ids
           for row in records["followups"]):
        raise RuntimeError("Seed follow-up points outside the deterministic step/teacher set.")
    visits_by_id = {row.id: row for row in records["visits"]}
    for schedule in records["schedules"]:
        visit = visits_by_id[schedule.school_visit_id]
        if (
            schedule.school_id != visit.school_id
            or schedule.proposed_start_at != visit.scheduled_at
            or schedule.proposed_end_at <= schedule.proposed_start_at
        ):
            raise RuntimeError("Seed schedule and visit relationship/date check failed.")


async def active_mentor(db: AsyncSession) -> User:
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
        raise RuntimeError("Refusing to update: expected exactly one active Mentor.")
    return mentors[0]


async def verify_school_codes_unused(
    db: AsyncSession, schools: list[School]
) -> None:
    target_ids = {row.id for row in schools}
    proposed_codes = [entry[1] for entry in SCHOOLS]
    if len(set(proposed_codes)) != len(proposed_codes):
        raise RuntimeError("Proposed school codes are not unique.")
    conflicts = (
        await db.execute(
            select(School.id).where(
                School.code.in_(proposed_codes),
                School.id.not_in(target_ids),
            )
        )
    ).scalars().all()
    if conflicts:
        raise RuntimeError("A proposed school code belongs to a non-seeded record.")


async def update_existing(
    db: AsyncSession,
) -> tuple[int, list[tuple[type, uuid.UUID, str, Any]]]:
    database_name, database_role = (
        await db.execute(text("SELECT current_database(), current_user"))
    ).one()
    if database_name != "marg_db" or database_role != "marg_app":
        raise RuntimeError("Refusing to update: expected marg_db as marg_app.")

    mentor = await active_mentor(db)
    records = await all_records(db, mentor)
    validate_relations(records)
    if any(row.user_id != mentor.id for row in records["assignments"]):
        raise RuntimeError("Seed assignment ownership did not match the active Mentor.")
    await verify_school_codes_unused(db, records["schools"])

    if len(records["schools"]) != 20 or len(records["tasks"]) != 24:
        raise RuntimeError("Seed record count preflight failed.")
    for index, (school, (_, target_code, district, _)) in enumerate(
        zip(records["schools"], SCHOOLS), start=1
    ):
        old_code = f"{SEED_MARKER}-S{index:02d}"
        if school.code not in (old_code, target_code):
            raise RuntimeError("School seed marker/code check failed.")
        old_district = f"Demo District {((index - 1) % 4) + 1:02d}"
        if school.district not in (old_district, district):
            raise RuntimeError("School ownership/location marker check failed.")
    for index, teacher in enumerate(records["teachers"], start=1):
        if teacher.employee_code not in (
            f"{SEED_MARKER}-T{index:02d}",
            f"EDU-{SCHOOLS[index - 1][1].split('-')[0]}-{index:02d}",
        ):
            raise RuntimeError("Teacher seed marker/code check failed.")
    for index, task in enumerate(records["tasks"], start=1):
        if task.title not in (
            f"{SEED_MARKER} Mentor task {index:02d}",
            TASKS[index - 1][0],
        ):
            raise RuntimeError("Task seed marker/title check failed.")

    before: list[tuple[type, uuid.UUID, str, Any]] = []
    updates = build_updates(records)
    for obj, values in updates:
        set_fields(obj, values, before)
    await db.flush()
    return len(updates), before


async def verify_rollback() -> None:
    before: list[tuple[type, uuid.UUID, str, Any]] = []
    count = 0
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                count, before = await update_existing(db)
                raise RuntimeError("Intentional rollback verification.")
    except RuntimeError as exc:
        if str(exc) != "Intentional rollback verification.":
            raise

    async with AsyncSessionLocal() as db:
        for model, record_id, field, old_value in before:
            stored = await db.get(model, record_id)
            if stored is None or getattr(stored, field) != old_value:
                raise RuntimeError("Rollback verification failed; a field changed.")
    print(f"Rollback verified: {count} field updates reverted; database unchanged.")


async def apply_updates() -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            count, _ = await update_existing(db)
    print(f"Committed {count} text-field updates to existing synthetic records.")


async def update_derived_reminders(db: AsyncSession) -> list[tuple[type, uuid.UUID, str, Any]]:
    database_name, database_role = (
        await db.execute(text("SELECT current_database(), current_user"))
    ).one()
    if database_name != "marg_db" or database_role != "marg_app":
        raise RuntimeError("Refusing to update reminders outside marg_db as marg_app.")

    mentor = await active_mentor(db)
    tasks = {
        row.id: row
        for row in [
            await one(db, MentorTask, f"task:{i:02d}", mentor.id)
            for i in range(1, 25)
        ]
    }
    steps = {
        row.id: row
        for row in [
            await one(db, ActionPlanStep, f"action-plan-step:{i:02d}", mentor.id)
            for i in range(1, 7)
        ]
    }
    plans = {
        row.id: row
        for row in [
            await one(db, ActionPlan, f"action-plan:{i:02d}", mentor.id)
            for i in range(1, 7)
        ]
    }
    task_ids = list(tasks)
    step_ids = list(steps)
    seeded_notification_ids = [
        stable_id(f"notification:{i:02d}") for i in range(1, 9)
    ]
    reminders = (
        await db.execute(
            select(Notification).where(
                Notification.user_id == mentor.id,
                Notification.reference_entity_id.in_(task_ids + step_ids),
                Notification.id.not_in(seeded_notification_ids),
                or_(
                    Notification.title.ilike(f"%{SEED_MARKER}%"),
                    Notification.message.ilike(f"%{SEED_MARKER}%"),
                ),
            )
        )
    ).scalars().all()
    if len(reminders) != 8:
        raise RuntimeError(
            "Refusing reminder update: expected exactly eight marker-containing "
            "system reminders linked to seeded tasks or steps."
        )

    before: list[tuple[type, uuid.UUID, str, Any]] = []
    for reminder in reminders:
        if reminder.reference_entity_type == "mentor_task" and reminder.reference_entity_id in tasks:
            task = tasks[reminder.reference_entity_id]
            due_at = task.due_at
            if due_at is None:
                raise RuntimeError("A linked seeded task has no due date.")
            if reminder.notification_type == "task_overdue":
                message = f"'{task.title}' was due on {due_at:%d %b %Y, %H:%M} UTC."
            elif reminder.notification_type == "task_due_soon":
                message = f"'{task.title}' is due on {due_at:%d %b %Y, %H:%M} UTC."
            else:
                raise RuntimeError("Unexpected reminder type for a seeded task.")
        elif (
            reminder.reference_entity_type == "action_plan_step"
            and reminder.reference_entity_id in steps
        ):
            step = steps[reminder.reference_entity_id]
            plan = plans.get(step.action_plan_id)
            if plan is None:
                raise RuntimeError("A seeded action-plan step has an unexpected parent.")
            message = (
                f"Step '{step.title}' of plan '{plan.title}' is due on "
                f"{step.due_date:%d %b %Y}."
            )
        else:
            raise RuntimeError("A stale reminder does not reference a seeded task or step.")

        before.append((Notification, reminder.id, "message", reminder.message))
        reminder.message = message

    await db.flush()
    return before


async def apply_derived_reminders() -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            before = await update_derived_reminders(db)
    print(f"Updated {len(before)} derived reminder messages.")


async def verify_derived_reminder_rollback() -> None:
    before: list[tuple[type, uuid.UUID, str, Any]] = []
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                before = await update_derived_reminders(db)
                raise RuntimeError("Intentional derived-reminder rollback verification.")
    except RuntimeError as exc:
        if str(exc) != "Intentional derived-reminder rollback verification.":
            raise

    async with AsyncSessionLocal() as db:
        for model, record_id, field, old_value in before:
            stored = await db.get(model, record_id)
            if stored is None or getattr(stored, field) != old_value:
                raise RuntimeError("Derived reminder rollback verification failed.")
    print(f"Rollback verified: {len(before)} derived reminder updates reverted.")


async def main(
    apply: bool,
    test_rollback: bool,
    refresh_derived_reminders: bool,
    verify_derived_rollback: bool,
) -> None:
    selected_modes = sum(
        (apply, test_rollback, refresh_derived_reminders, verify_derived_rollback)
    )
    if selected_modes > 1:
        raise SystemExit("Choose only one update or rollback-verification option.")
    if apply:
        await apply_updates()
    elif refresh_derived_reminders:
        await apply_derived_reminders()
    elif verify_derived_rollback:
        await verify_derived_reminder_rollback()
    elif test_rollback:
        await verify_rollback()
    else:
        await verify_rollback()
        print("No changes were retained. Use --apply to commit the seed-record updates.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true", help="Commit the existing-record updates.")
    group.add_argument(
        "--verify-rollback",
        action="store_true",
        help="Exercise the update transaction and verify all changes roll back.",
    )
    group.add_argument(
        "--refresh-derived-reminders",
        action="store_true",
        help="Update only approved marker-containing reminder snapshots linked to seeded tasks/steps.",
    )
    group.add_argument(
        "--verify-derived-rollback",
        action="store_true",
        help="Exercise and roll back the approved derived-reminder update.",
    )
    args = parser.parse_args()
    asyncio.run(main(
        args.apply,
        args.verify_rollback,
        args.refresh_derived_reminders,
        args.verify_derived_rollback,
    ))

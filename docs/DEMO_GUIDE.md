# MARG – Evaluator demo guide

MARG is used by **mentors** who support government-school teachers to improve
classroom teaching. All data in the demo is **fictional**.

## Access

| | |
|---|---|
| Web app | *(public URL, added after deployment is approved)* |
| Local run | see the root `README.md` → "Run locally" |
| Mentor account | `mentor.demo@marg.example` |
| Second mentor (data isolation) | `mentor2.demo@marg.example` |
| Administrator (school assignments only, API) | `admin.demo@marg.example` |
| Password | provided separately to evaluators (never stored in the repository) |

Demo workspace for the main mentor (Kavya Subramanian):

- 4 assigned schools in Ranipet and Vellore districts, with teachers, classrooms and weekly timetables.
- Visits: 3 completed, 1 in progress today, 3 planned (tomorrow, +3 days, +6 days) and 1 cancelled.
- Observations: Grade 6 Maths (fractions), Grade 4 English (reading), Grade 8 Science (filtration, **ready for AI analysis**), Grade 7 Tamil (draft).
- Findings, learning gaps, recommendations (approved, awaiting review and rejected), 3 action plans with steps, 5 follow-ups at different stages, 8 tasks (1 overdue) and reminders.

Dates are relative to the day the demo was seeded, so there is always past, current and upcoming work.

---

## Scenario 1 – Secure login and the mentor's day (2 min)

1. Open the app and sign in as the mentor. With a wrong password the app shows *"Incorrect email or password."*
2. **Dashboard:** greeting with the mentor's name, then live counts for assigned schools, upcoming visits, open and overdue tasks, follow-ups to verify, learning gaps and action plans. Every number is computed from database records.
3. Tap the bell to open **Notifications**: real reminders such as an overdue task, a visit tomorrow, a plan step due and a follow-up awaiting verification. Tap one to mark it read and jump to the record.
4. **Schools** → *Government Middle School, Kalavai Road*: teachers, classrooms, and a classroom's weekly timetable.

*Expected:* only the mentor's 4 schools are visible. The second mentor's school
(*Walajah East*) never appears; that is the school-level access control.

## Scenario 2 – Observation → AI analysis → approved improvement plan (4 min)

1. **Observations** → open the *Science · Separation of mixtures* observation (status *submitted*).
2. Tap **Analyse with Classroom Coach**. The local LLM and RAG take about 20–60 s.
   Review the summary, findings (with the supporting quote from the notes),
   learning gaps and recommendations, plus the **knowledge-base sources** (document title + page).
3. Tick one finding, one learning gap and one recommendation linked to that gap, then
   choose **Add selected as suggestions**. *Expected:* the records appear marked **AI suggested**.
   Nothing is official yet.
4. **Approve** the recommendation as the mentor.
5. **Action plans** → **New plan** → pick the approved recommendation, fill in the dates,
   then *Submit for approval* → *Approve* → add a step.
   *Expected:* plans can only be created from mentor-approved recommendations.

## Scenario 3 – Follow-up with evidence (2 min)

1. **Follow-ups** → *Share photos of student strip work* (status *evidence submitted*).
2. Upload a photo as evidence. *Expected:* the file is stored and listed (JPEG/PNG,
   up to 10 MB; a file whose content does not match its type is rejected).
3. **Verify** (or *Request revision* with a note), then **Close**.
4. The dashboard's "follow-ups to verify" count goes down.

## Scenario 4 – Classroom Coach (educational chatbot) (2 min)

1. **Coach** tab. Ask: *"How can a teacher check whether students understand equivalent fractions during a lesson?"*
   *Expected:* practical steps with **[S1]…** citations and a source list (real document titles and pages from the 167-document knowledge base).
2. Optionally pick an observation as context; the answer adapts to its subject and grade.
3. Ask something off-topic: *"What is the best chocolate cake recipe?"*
   *Expected:* the Coach says no relevant knowledge was found, and does not invent an answer.

## Scenario 5 – Mentor AI Assistant with human approval (3 min)

1. **Mentor AI** → run **Daily plan** and **Prioritise tasks**.
   *Expected:* computed results (time blocks, ranked tasks with scores and the formula).
   When Claude is enabled, an AI narrative appears and is labelled as AI.
2. Run **Visit planning** or **Schedule check**. The assistant creates **proposals**,
   for example "schedule a visit to … tomorrow 09:45".
3. **Approve** a proposal. *Expected:* the visit is created or moved in MARG
   (check **Visits**) and a notification confirms it. **Reject** another one;
   nothing changes.
4. **Teacher message draft** for a follow-up → approve → open WhatsApp with the
   drafted text → report the outcome.

## Scenario 6 – Offline-first (optional, 2 min)

1. Sign in, open **Tasks** and **Visits** (the data is cached on the device).
2. Turn off the network (browser DevTools → *Offline*, or airplane mode).
3. Create a task and start a planned visit. *Expected:* "Saved offline, will sync",
   and a banner shows the pending changes.
4. Reconnect. *Expected:* changes sync automatically and the banner clears.
   If the same record was changed elsewhere meanwhile, the **Sync** screen shows a
   **conflict**. The newer server data is never silently overwritten.

---

## What is real vs. planned

| Implemented and tested | Planned (labelled in the app/docs) |
|---|---|
| Real authentication, school-scoped data, all workflows persisted in PostgreSQL | WhatsApp provider API (today: approved drafts sent through a WhatsApp link) |
| Classroom Coach: local Qwen 2.5 3B + RAG over 33,624 chunks | Push notifications (in-app only today) |
| Mentor AI Assistant: 10 agents, proposals, approvals, audit | Supervisor dashboards |
| Offline outbox and sync with conflict detection | Knowledge-base re-ingestion with OCR |

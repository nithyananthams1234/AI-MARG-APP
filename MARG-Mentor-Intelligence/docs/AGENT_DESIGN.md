# MARG Mentor Intelligence Engine — Agent Design

| | |
|---|---|
| Status | Phase 0 — design baseline (no agent implemented yet) |
| Last updated | 2026-10-31 |
| Related | [ARCHITECTURE.md](ARCHITECTURE.md) §5 (pipeline), §6 (approval) |

---

## 1. Shared agent model

### 1.1 BaseAgent contract

Every agent is an independent module implementing the same interface:

```python
class BaseAgent(ABC, Generic[InputT, OutputT]):
    agent_id: ClassVar[str]              # e.g. "task_intelligence"
    version: ClassVar[str]               # semver of agent logic
    prompt_version: ClassVar[str | None] # e.g. "task_intelligence/v1"
    input_schema: ClassVar[type[InputT]]
    output_schema: ClassVar[type[OutputT]]   # subclass of AgentResult
    allowed_tools: ClassVar[frozenset[str]]
    required_permissions: ClassVar[frozenset[Permission]]
    handles_events: ClassVar[frozenset[EventType]]

    async def run(self, ctx: AgentContext, data: InputT) -> OutputT:
        """Template method. Subclasses implement the hooks below."""

    # hooks
    async def analyse(self, ctx, data) -> DeterministicFindings: ...   # services only
    def needs_llm(self, ctx, findings) -> bool: ...                     # cost gate
    async def reason(self, ctx, findings) -> LLMOutput | None: ...      # provider call
    def assemble(self, findings, llm_output) -> OutputT: ...            # build result
```

`run()` is implemented once in the base class. It enforces:

1. Input validation against `input_schema`.
2. `analyse()`, deterministic and always executed.
3. `needs_llm()` plus a budget check. If either says no, `reason()` is skipped and the result says so.
4. `reason()` output validated against the agent's LLM schema. Invalid output gets **one** repair attempt, then falls back to a deterministic-only result.
5. `assemble()` output validated against `output_schema`.
6. Any `proposed_actions` whose tool is not in `allowed_tools` are rejected and logged as policy violations.
7. Step logging under the execution ID.

Agents receive an `AgentContext`: principal, mentor preferences, a read-only tool facade, provider handle, clock and execution ID. They have **no** direct access to the adapter, the database session or the network.

### 1.2 Common output (`AgentResult`)

| Field | Content |
|---|---|
| `agent_id`, `agent_version`, `prompt_version` | traceability |
| `findings` | deterministic facts with `source_refs` (entity IDs) |
| `recommendations[]` | `{text, rationale, source: deterministic \| ai_generated}` |
| `proposed_actions[]` | `{tool_name, arguments, rationale}` (never executed by the agent) |
| `notifications[]` | notification intents |
| `missing_data[]` | what was unavailable and how it limited the result |
| `llm_used`, `llm_usage_id` | whether Claude was called |
| `data_source` | `mock` or `marg` (propagated from the adapter) |

### 1.3 Rules that apply to all agents

- Never invent schools, teachers, visits, travel times, statistics or working hours. If something is absent, it goes in `missing_data`.
- Deterministic values (scores, indexes, counts, dates) are computed in `services/`. Claude may reference and explain them, and the assembled result always uses the service value even if Claude restates it differently.
- Never produce clinical, psychological or ability judgements about teachers or students.
- Preserve the follow-up distinction: *teacher-reported* ≠ *evidence submitted* ≠ *mentor-verified*.
- Label all AI-generated text as AI-generated.

### 1.4 LLM usage and complexity hints

**Owner decision (2026-10-31): one configurable model.** Every Claude call uses `ANTHROPIC_MODEL`. No model ID appears in code.

Each agent call still declares a **complexity hint**. Today the hint is recorded only for analysis; the single-model router ignores it. The hint lets future routing be added by configuration without touching agents (TECHNICAL_DECISIONS TD-07).

| Hint | Typical use |
|---|---|
| `none` | pure deterministic results (no Claude call) |
| `light` | short summaries, short drafts |
| `standard` | daily plans, follow-up suggestions, reports |
| `complex` | weekly planning, multi-constraint rescheduling |

The per-agent "tier" mentions in §3 refer to these hints.

---

## 2. Deterministic formulas (shared services)

### 2.1 Task priority (`services/task_service.py`)

```
score = 0.30·urgency + 0.25·impact + 0.20·risk
      + 0.15·deadline_proximity + 0.10·workload_dependency
```

- Every factor is validated to `[0, 100]`, and out-of-range input is rejected rather than clamped. The weights live in configuration, and their sum is validated to equal 1.0.
- Classification uses lower-bound-inclusive cutoffs on the unrounded score: `<25 low`, `<50 medium`, `<75 high`, `≥75 critical`. The 0–24 / 25–49 / … table in the brief is read this way for fractional scores. **Confirm with backend.**
- **Factor sourcing (owner decision 2026-10-31: verified values only, no assumed defaults):**
  - `urgency`, `impact`, `risk`: used **only** when a verified value is supplied by MARG (or, in development, by the labelled mock dataset). A missing value is never replaced by 50 or any other default. It is reported in `missing_factors`. Claude never supplies these numbers.
  - `deadline_proximity`: computed from the task's deadline. 100 if overdue, linear decay to 0 at a configurable horizon (default 14 days). A task with **no deadline** gets 0, because "no deadline" is a verified fact, not missing data. A task whose deadline field is **unavailable** has this factor flagged as missing.
  - `workload_dependency`: computed from the dependency graph and workload index. If either input is unavailable (for example, working hours not configured), the factor is flagged as missing.
- **Result when factors are missing:**

  ```
  PriorityResult
    status:          complete | incomplete
    score:           float | None      # only when status == complete
    priority:        Priority | None   # only when status == complete
    factors:         {name: value | None}
    missing_factors: [names]
    score_bounds:    (min, max)        # deterministic range if the missing factors were 0 or 100
  ```

  `score_bounds` is informational only. It shows how far the missing data could move the score, but it **does not assign a priority**. Ordering of incomplete tasks (Phase 3) uses only verified facts (overdue first, then deadline) and is labelled as such.
- Output always includes the per-factor breakdown so explanations are traceable.

### 2.2 Workload index (`services/workload_service.py`)

```
workload_index = estimated_workload_hours / available_working_hours × 100
```

- `available_working_hours` comes from mentor preferences or authorised configuration, never assumed. If it is unknown or 0, the index is `None` with a `missing_data` entry.
- Thresholds are configurable. Proposed defaults: `<80 normal`, `80–100 high`, `>100 overloaded`.
- Task effort estimates come from MARG when available. Otherwise, per-activity estimates are used **only if the owner has configured them** (none are configured by default), and they are reported as estimates. With neither, the item's effort is flagged as missing, and the index is reported as a lower bound or as `None`.
- Always labelled as an administrative planning metric.

### 2.3 Other deterministic services

| Service | Functions |
|---|---|
| `datetime_utils` | UTC ⇄ local, working-day calendars, horizon windows |
| `schedule_service` | interval overlap/conflict detection, free-slot computation within working hours, buffer insertion when reliable travel data exists |
| `followup_service` | overdue detection, allowed status transitions, evidence-gap detection |
| `visit_service` | days since last visit, attention score (pending plans, overdue follow-ups, time since visit) |
| `planning_service` | candidate-plan construction (greedy fit of prioritised items into free slots) |

---

## 3. Agent specifications

Each agent below lists: **triggers → deterministic analysis → LLM gate → output → tools → autonomy**.

### 3.1 Task Intelligence Agent — `task_intelligence`

- **Triggers:** `TASK_CREATED`, `TASK_UPDATED`, `TASK_OVERDUE`, `DEADLINE_APPROACHING`, called by daily planning.
- **Deterministic:** priority score and class per task. Overdue, due-soon and neglected detection (no update in N days, configurable). Dependency graph and cycle detection. Recommended order (priority, then deadline, then dependency).
- **LLM gate:** only when (a) a task description is ambiguous and needs interpretation, (b) a natural-language explanation of competing priorities is requested, or (c) the daily task summary is generated. Never for single-event score updates.
- **Claude does:** explain ordering, suggest next actions, suggest deadline adjustments (as proposals).
- **Output:** prioritised task list with breakdowns, next actions, neglected tasks, deadline-change proposals.
- **Tools:** `get_tasks`, `get_overdue_tasks`, `calculate_task_priority`, `create_notification`, `propose_task_update` (L2), `propose_task_creation` (L2).
- **Autonomy:** L1 for analysis and notifications. Deadline changes and new tasks are L2.

### 3.2 Time Management Agent — `time_management`

- **Triggers:** daily planning, `SCHEDULE_CONFLICT_DETECTED`, preference changes.
- **Deterministic:** available hours per day from working hours minus committed events. Committed vs. free time. Overloaded days.
- **LLM gate:** only to phrase improvement suggestions for overloaded days (light tier).
- **Output:** daily time summary, allocation suggestions, overloaded days.
- **Tools:** `get_mentor_schedule`, `get_mentor_preferences`, `calculate_workload_index`.
- **Autonomy:** L1 only (advisory).
- **Rule:** if working hours are not configured, return `missing_data` and no allocation.

### 3.3 Schedule Intelligence Agent — `schedule_intelligence`

- **Triggers:** `SCHOOL_VISIT_CREATED`, `SCHOOL_VISIT_RESCHEDULED`, `TASK_UPDATED` with a time change, daily planning.
- **Deterministic:** hard-constraint checks (overlaps, outside working hours, visit duration). Free slots. Travel buffers **only** when reliable travel data exists; otherwise this is flagged.
- **LLM gate:** complex re-planning when ≥2 conflicts or soft-constraint trade-offs exist. Claude proposes; the deterministic validator re-checks every proposed slot against hard constraints, and invalid slots are discarded.
- **Output:** conflicts, unallocated time, proposed schedule changes.
- **Tools:** `get_mentor_schedule`, `get_school_visit_history`, `create_schedule_suggestion` (L1, internal), `propose_schedule_change` (L2; L3 when marked important by policy).
- **Emits:** `SCHEDULE_CONFLICT_DETECTED`.

### 3.4 Workload Management Agent — `workload_management`

- **Triggers:** `WORKLOAD_THRESHOLD_EXCEEDED`, daily and weekly planning, bulk task or visit changes.
- **Deterministic:** workload index per day and per week. Counts of tasks, follow-ups and visits. Imbalance detection (variance across days). Threshold classification.
- **LLM gate:** redistribution recommendations when overloaded (standard tier).
- **Output:** workload report, overloaded days, redistribution/rescheduling proposals.
- **Tools:** `get_tasks`, `get_followups`, `get_mentor_schedule`, `calculate_workload_index`, `create_notification`, `propose_schedule_change` (L2).
- **Emits:** `WORKLOAD_THRESHOLD_EXCEEDED`.
- **Rule:** wording stays administrative ("schedule is over capacity"), never wellbeing or stress language.

### 3.5 Follow-up Management Agent — `followup_management`

- **Triggers:** `FOLLOWUP_CREATED`, `FOLLOWUP_OVERDUE`, `TEACHER_RESPONSE_RECEIVED`, `EVIDENCE_SUBMITTED`, `VERIFICATION_REQUIRED`.
- **Deterministic:** overdue detection. Status-transition validation. Evidence-gap detection (responded but no evidence). Verification-pending queue.
- **LLM gate:** suggesting next follow-up actions, summarising teacher responses (light/standard tier). The teacher's response text is untrusted input (§security).
- **Output:** follow-up summary, verification reminders, next-action suggestions, revision flags.
- **Tools:** `get_followups`, `create_notification`, `propose_followup_update` (L2), hand-off request to the communication agent for reminders.
- **Hard rule:** no tool can set `mentor_verified`. That is a mentor action in MARG, outside this engine. The agent can only remind the mentor to verify.

### 3.6 School Visit Planning Agent — `school_visit_planning`

- **Triggers:** weekly planning, `SCHOOL_VISIT_COMPLETED`, `FOLLOWUP_OVERDUE` for a school, on request.
- **Deterministic:** attention score per school (days since last visit, pending action plans, overdue follow-ups, all configurable weights). Candidate visit slots from the schedule service.
- **LLM gate:** pre-visit summary and checklist generation (standard tier), using only recorded data for that school.
- **Output:** ranked schools needing attention, suggested visit slots, pre-visit summary, checklist.
- **Tools:** `get_school_details`, `get_school_visit_history`, `get_followups`, `get_mentor_schedule`, `propose_visit_schedule` (L2).
- **Rule:** never invent school details or history. A school with no visit history is reported as "no recorded visits", not "never visited".

### 3.7 Automated Reporting Agent — `reporting`

- **Triggers:** end of day (configurable), weekly planning, on request.
- **Deterministic:** all counts and statistics (completed, pending, overdue, visits, follow-up status distribution, workload trend) computed in Python from records in the reporting window.
- **LLM gate:** narrative summary and "important issues" highlighting (standard tier). Claude receives only the computed aggregates. Post-validation checks that every number in the narrative appears in the aggregate set, and fails the narrative otherwise.
- **Output:** daily or weekly report (structured + narrative), explicit missing-data section.
- **Tools:** `get_tasks`, `get_followups`, `get_school_visit_history`, `generate_daily_report`, `generate_weekly_report` (L1, internal storage), `create_notification`.

### 3.8 Teacher Communication Agent — `teacher_communication`

- **Triggers:** hand-off from the follow-up or visit agents, or a mentor request.
- **Deterministic:** recipient resolution, language choice (teacher or mentor preference), template selection, length limits.
- **LLM:** drafts concise, respectful messages in **English or Tamil** (light/standard tier). Names are pseudonymised in the prompt and re-inserted locally after generation.
- **Output:** `MessageDraft` (language, body, purpose, related entity, `status: draft`).
- **Tools:** `create_teacher_message_draft` (L1, internal only).
- **Hard rule:** no send tool is registered in the initial phases. Sending is a future L3 operation that requires explicit mentor approval **and** a separately authorised integration module.

### 3.9 Daily Planning Agent — `daily_planning`

- **Triggers:** `DAILY_PLANNING_TRIGGERED` at the mentor's configured local planning time (planning tick), or on request.
- **Composition:** calls the task, time, schedule, workload and follow-up agents' **deterministic** analyses in-process (no extra LLM calls from sub-agents), then makes **one** LLM call to compose the plan.
- **Deterministic:** candidate plan (greedy fit of prioritised work into free slots), critical items, conflicts.
- **LLM gate:** compose the narrative plan and rationale (standard tier). Skipped if there is nothing to plan.
- **Output:** `DailyPlan` stored in `plans`, plus a "Daily plan ready" notification.
- **Idempotency:** `daily_plan:{mentor_ref}:{local_date}` (a re-run creates a new version only when explicitly requested).

### 3.10 Weekly Planning Agent — `weekly_planning`

- **Triggers:** `WEEKLY_PLANNING_TRIGGERED` (configurable day and time).
- **Composition:** previous-week report aggregates (reporting service), unfinished tasks, upcoming visits (visit-planning analysis), deadlines, pending follow-ups, workload distribution.
- **LLM gate:** weekly recommendations and operational summary (complex tier).
- **Output:** `WeeklyPlan` plus a weekly summary, with schedule or visit proposals as L2 items.
- **Idempotency:** `weekly_plan:{mentor_ref}:{iso_year}-W{iso_week}`.

---

## 4. Event → agent routing (initial)

| Event | Primary agent | Secondary |
|---|---|---|
| TASK_CREATED / TASK_UPDATED | task_intelligence | schedule_intelligence (if time changed) |
| TASK_COMPLETED | — (memory update only) | reporting (aggregates) |
| TASK_OVERDUE / DEADLINE_APPROACHING | task_intelligence | — |
| SCHOOL_VISIT_CREATED / _RESCHEDULED | schedule_intelligence | workload_management |
| SCHOOL_VISIT_COMPLETED | school_visit_planning | followup_management |
| FOLLOWUP_CREATED / _OVERDUE | followup_management | teacher_communication (draft) |
| TEACHER_RESPONSE_RECEIVED / EVIDENCE_SUBMITTED / VERIFICATION_REQUIRED | followup_management | — |
| SCHEDULE_CONFLICT_DETECTED | schedule_intelligence | time_management |
| WORKLOAD_THRESHOLD_EXCEEDED | workload_management | — |
| DAILY_PLANNING_TRIGGERED | daily_planning | — |
| WEEKLY_PLANNING_TRIGGERED | weekly_planning | reporting |

Routing lives in the agent registry, built from each agent's `handles_events`. Secondary agents run as separate executions linked by `correlation_id`.

---

## 5. Tool catalogue (conceptual, mock-backed initially)

| Tool | Side effect | Level | Idempotency key |
|---|---|---|---|
| `get_tasks`, `get_overdue_tasks`, `get_followups`, `get_mentor_schedule`, `get_school_details`, `get_school_visit_history`, `get_mentor_preferences` | none (read) | 1 | n/a |
| `calculate_task_priority`, `calculate_workload_index` | none (compute) | 1 | n/a |
| `create_notification` | engine-internal write | 1 | `(mentor, type, entity, local_date)` |
| `create_schedule_suggestion`, `generate_daily_report`, `generate_weekly_report`, `create_teacher_message_draft` | engine-internal write | 1 | content hash + trigger |
| `propose_task_creation`, `propose_task_update`, `propose_followup_update`, `propose_schedule_change`, `propose_visit_schedule` | creates a Proposal; MARG change only after approval | 2 (3 by policy) | payload hash |
| *(future)* `send_teacher_message` | external | 3 | draft id |

These names are conceptual. They do not imply that any MARG endpoint exists.

---

## 6. Testing expectations per agent

Each agent ships with:
- unit tests for its deterministic analysis (no LLM),
- tests with a fake `LLMProvider` returning valid, invalid and refusal responses,
- a policy test proving it cannot emit actions outside `allowed_tools`,
- a mock-data scenario test (see ROADMAP Phase 7 E2E scenarios).

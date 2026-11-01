# MARG Mentor Intelligence Engine — Architecture

| | |
|---|---|
| Status | Phase 0 baseline + owner decisions of 2026-10-31 (nothing implemented yet) |
| Last updated | 2026-10-31 |
| Related | [AGENT_DESIGN.md](AGENT_DESIGN.md), [TECHNICAL_DECISIONS.md](TECHNICAL_DECISIONS.md), [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) |

---

## 1. Purpose and scope

The Mentor Intelligence Engine ("the engine") is an event-driven, autonomous assistant for MARG mentors (CRPs, academic mentors, supervisors). It monitors tasks, schedules, follow-ups, school visits and workload, and produces plans, summaries, notifications, proposals and message drafts.

### In scope
Task, time, schedule, workload, follow-up, school-visit, reporting, communication-draft, daily and weekly planning intelligence, plus the orchestration, approval, memory, audit and provider layers that support it.

### Out of scope (explicitly)
- **Classroom Intelligence Engine (System 1)**: RAG, the educational knowledge base, pedagogy reasoning, classroom observation analysis and the teacher chatbot. The engine never imports, calls or duplicates System 1 code. Both systems will talk only through the MARG backend.
- **The MARG FastAPI backend**: never modified by this project.
- **Direct database access to MARG**: never done. All MARG data flows through the backend adapter (§10).
- **Sending external messages** (WhatsApp, SMS, email): not built in the initial phases. Drafts only.

---

## 2. Architectural principles

1. **Deterministic first, LLM second.** Python owns every calculation, rule, status transition, permission check and constraint. Claude handles reasoning, summarisation, explanation and drafting, and only when a deterministic gate decides an LLM call is worth it.
2. **Claude proposes, the engine decides, humans approve.** Claude output is untrusted. It is validated against Pydantic schemas, then by the policy engine, then by the approval engine. Claude never executes tools directly and never approves anything.
3. **Ports and adapters.** Business logic depends on interfaces (`LLMProvider`, `MARGBackendAdapter`, `JobQueue`, `NotificationChannel`), never on concrete vendors.
4. **The engine owns only its own data.** Its database holds operational memory, executions, approvals, proposals, notifications and usage. MARG remains the system of record for tasks, visits, follow-ups and schools.
5. **Idempotent by default.** Every event, job, tool call and approval execution has an idempotency key.
6. **Fail closed.** Missing configuration, missing auth or an unknown permission means the operation is refused, not degraded. There is no silent fallback to mock mode.
7. **Modular monolith.** One deployable codebase with two process types (API and worker). No microservices.

---

## 3. System context

```
                ┌─────────────────────────────┐
                │  MARG Frontend / Mobile App │   (existing, not ours)
                └──────────────┬──────────────┘
                               │
                ┌──────────────▼──────────────┐
                │    MARG FastAPI Backend     │   (existing, not modified)
                │  system of record: tasks,   │
                │  visits, follow-ups, schools│
                └───────┬──────────────┬──────┘
          documented    │              │   documented
          APIs only     │              │   APIs only
     ┌──────────────────▼───┐      ┌───▼─────────────────────────┐
     │ Mentor Intelligence  │      │ Classroom Intelligence      │
     │ Engine (THIS SYSTEM) │      │ Engine (System 1, separate) │
     └───┬──────────┬───────┘      └─────────────────────────────┘
         │          │
   ┌─────▼───┐  ┌───▼──────────────┐
   │ Engine  │  │ Anthropic Claude │
   │ DB+Redis│  │ API              │
   └─────────┘  └──────────────────┘
```

During independent development, the `MockBackendAdapter` replaces the MARG backend. It is clearly labelled as development-only.

---

## 4. Component architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ API layer (FastAPI)          app/main.py, app/api/                   │
│  health · approvals · proposals · plans · notifications · usage      │
└───────────────┬──────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│ Event layer                  app/events/, app/core/event_bus.py      │
│  event models · inbox (dedupe) · dispatcher · scheduled triggers     │
└───────────────┬──────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│ Orchestration core           app/core/                               │
│  Orchestrator → ContextBuilder → AgentRegistry → Agent.run()         │
│  → PolicyEngine → ApprovalEngine → ExecutionEngine → ToolRegistry    │
└──────┬─────────────────┬─────────────────┬───────────────────────────┘
       │                 │                 │
┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────────────────────────┐
│ Agents      │   │ Services    │   │ Providers (LLM)                 │
│ app/agents/ │──▶│ (pure,      │   │ app/providers/                  │
│             │   │ deterministic)  │ LLMProvider · AnthropicProvider │
│             │──────────────────▶  │ model_factory · usage_tracker   │
└──────┬──────┘   └─────────────┘   └─────────────────────────────────┘
       │ (only via registered tools)
┌──────▼──────────────────────────────────────────────────────────────┐
│ Tools                        app/tools/  (registry + typed tools)   │
└──────┬───────────────────────────────┬──────────────────────────────┘
       │                               │
┌──────▼─────────────────────┐  ┌──────▼──────────────────────────────┐
│ Integrations               │  │ Engine persistence                  │
│ app/integrations/          │  │ app/models/ (SQLAlchemy), app/memory│
│  base_adapter (port)       │  │ executions · approvals · proposals  │
│  mock/  (DEV ONLY)         │  │ memory · notifications · usage ·    │
│  marg_backend/ (BLOCKED    │  │ event inbox · audit log             │
│   until OpenAPI audit)     │  └─────────────────────────────────────┘
└────────────────────────────┘
Cross-cutting: app/security/ · app/monitoring/ · app/config.py · app/utils/
```

### 4.1 Layer responsibilities

| Layer | Responsibility | Must NOT |
|---|---|---|
| `api/` | HTTP surface for the engine's own resources, auth context extraction | contain business logic |
| `events/` | Event schemas, validation, dedupe, mapping event type → handler | call Claude directly |
| `core/orchestrator` | Run the 14-step pipeline for one event or trigger | know agent internals |
| `core/context_builder` | Fetch the *minimum* authorised data for an agent (via tools/adapter), redact it, build a typed context | fetch data for other mentors |
| `agents/` | Combine deterministic service output and optional Claude reasoning into a typed `AgentResult` | perform side effects; access the adapter directly |
| `services/` | Pure deterministic logic: priority, workload, conflicts, deadlines, status rules | do I/O or call the LLM |
| `providers/` | Vendor-specific LLM calls, retries, structured output, usage capture | contain business rules |
| `tools/` | Typed, permissioned, side-effect-classified operations | be callable outside the registry |
| `integrations/` | Translate between engine schemas and backend payloads | leak backend payload shapes into agents |
| `memory/` | Persistent, mentor-scoped preferences and operational memory | serve as a cache of MARG records of truth |
| `security/` | Permissions, secret handling, redaction/pseudonymisation | — |
| `monitoring/` | Audit log, metrics, health | log secrets or raw PII |

---

## 5. Processing pipeline

Every unit of autonomous work runs this lifecycle under a single `execution_id`:

| # | Step | Owner | Deterministic? |
|---|---|---|---|
| 1 | Event detection (backend event, scheduled trigger, API request) | `events/`, `jobs/` | yes |
| 2 | Validation + classification + dedupe (`event_id` unique in inbox) | `events/event_processor` | yes |
| 3 | Context collection (authorised, minimised, redacted) | `core/context_builder` | yes |
| 4 | Agent selection (event type → agent(s) via registry) | `core/agent_registry` | yes |
| 5 | Business-rule processing (priority, workload, conflicts…) | `services/` | yes |
| 6 | Claude reasoning, only if the agent's `needs_llm()` gate returns true | `providers/` | no |
| 7 | Structured output generation (`AgentResult`) | agent | — |
| 8 | Pydantic validation of LLM and agent output | agent + `schemas/` | yes |
| 9 | Permission and policy validation | `core/policy_engine` | yes |
| 10 | Approval evaluation (Level 1/2/3) | `core/approval_engine` | yes |
| 11 | Controlled tool execution (Level 1 now; Level 2/3 after approval) | `core/execution_engine` + `tools/` | yes |
| 12 | Execution logging (every step transition) | `monitoring/audit_logger` | yes |
| 13 | Result monitoring (confirm side effect, mark completed only then) | `core/execution_engine` | yes |
| 14 | Notification generation | `services/notification_service` | yes |

```
event ─▶ inbox(dedupe) ─▶ orchestrator ─▶ context ─▶ agent
                                                    │
                    deterministic services ◀────────┤
                    Claude (gated)        ◀─────────┘
                                                    ▼
                                      AgentResult (validated)
                                                    ▼
                                   policy check ─── reject ─▶ log + stop
                                                    ▼
                         ┌──── Level 1 ────┬──── Level 2/3 ─────┐
                         ▼                 ▼                    │
                   execute tool     create Proposal ─▶ approval queue
                         ▼                               (mentor decides)
                   confirm + log                              ▼
                         ▼                        approved ─▶ execute ─▶ confirm + log
                   notification                   rejected ─▶ log
```

### 5.1 Agent output contract

Agents never mutate state. An agent returns an `AgentResult` containing:

- `findings`: deterministic facts such as scores, overdue items and conflicts, with source references.
- `recommendations`: human-readable suggestions, labelled `source: deterministic | ai_generated`.
- `proposed_actions`: a list of `{tool_name, arguments, rationale}`. Each `tool_name` must be in the agent's `allowed_tools`.
- `notifications`: notification intents.
- `missing_data`: explicit list of data the agent needed but could not obtain.
- `llm_usage`: reference to the usage record, if Claude was called.

The policy engine strips or rejects any proposed action that is not allowed. The approval engine assigns each surviving action an autonomy level from the **tool's declared classification**, not from anything Claude says.

### 5.2 How Claude is called

The default pattern is **single-shot structured output**, not an open-ended tool loop:

1. The agent gathers context deterministically.
2. The agent sends one request with a versioned system prompt and the minimised context in delimited data blocks, constrained to a Pydantic response schema.
3. The response is validated. Then `stop_reason` is checked (`refusal`, `max_tokens`), then business validation runs.

Read-only Claude tool use (Claude requests extra context through registered read tools) is a possible later extension for complex planning. It is off by default and limited to Level-1 read tools.

---

## 6. Autonomy and approval

| Level | Meaning | Examples | Execution |
|---|---|---|---|
| 1 — automatic | Read-only or engine-internal, non-consequential | read tasks, compute workload, internal summary, internal notification | immediate |
| 2 — proposed | Would change MARG records | create task, reschedule visit, change follow-up | `Proposal` → mentor approval → execute |
| 3 — explicit | External or sensitive | send message, close an important record, major schedule change | `Proposal` → explicit approval with confirmation → separately authorised integration |

Rules:
- The level comes from the tool definition plus policy overrides, and can only be raised by configuration, never lowered at runtime.
- The approver must be a human principal with the right role. A system principal or agent principal cannot approve.
- An approval binds to a hash of the exact proposal payload. Editing the proposal invalidates the approval.
- Proposals expire after a configurable TTL.
- Each approval records: approver, timestamp, approved operation, original proposal, result and execution status.
- **Never auto-verify:** no tool exists that sets a follow-up to `mentor_verified` without a human approval record.

---

## 7. Engine-owned data model (development database)

| Table | Purpose |
|---|---|
| `events` (inbox) | received events, unique `event_id`, processing status, attempts |
| `executions` | one per pipeline run: agent, trigger, status, timings, error |
| `execution_steps` | step-level audit trail for an execution |
| `tool_invocations` | tool name, input hash, idempotency key, side-effect class, result, status |
| `proposals` | Level 2/3 actions awaiting decision, payload + hash, expiry |
| `approvals` | decision records bound to proposal hash |
| `notifications` | internal notifications (§9 fields) |
| `message_drafts` | teacher communication drafts (never auto-sent) |
| `plans` | generated daily/weekly plans and reports (versioned) |
| `mentor_preferences` | working hours, timezone, language, planning time, notification prefs |
| `memory_entries` | operational memory / activity context, typed, with retention expiry |
| `llm_usage` | per-call model, tokens (incl. cache), cost, prompt version, latency, request id |
| `audit_log` | append-only security-relevant events |
| `dead_letters` | permanently failed jobs/events for inspection and replay |

Every row that contains mentor data carries `tenant_ref` and `mentor_ref`. Repository methods require them and filter by them (§11).

**Identifier rule:** engine-generated identifiers (executions, events, proposals, notifications…) are UUIDs. Identifiers that come from MARG (tenant, mentor, task, school, teacher…) are stored as **opaque strings** (`*_ref`) until the backend audit confirms their format. The engine never assumes MARG IDs are UUIDs.

All engine tables live in a dedicated PostgreSQL schema (`DB_SCHEMA`, default `mie`) inside the `marg_mentor_intelligence` database.

MARG entities (tasks, visits, follow-ups, schools, teachers) are **not** persisted here except as short-lived, minimised snapshots inside `executions` or `plans` for audit and reproducibility.

---

## 8. Canonical status contracts

These values are fixed by the project brief and must not be renamed:

| Entity | Values |
|---|---|
| Visit | `planned`, `in_progress`, `completed`, `cancelled` |
| Task | `pending`, `in_progress`, `completed`, `cancelled` |
| Follow-up | `pending`, `teacher_responded`, `evidence_submitted`, `mentor_verified`, `needs_revision`, `closed` |
| Action plan | `draft`, `pending_approval`, `approved`, `in_progress`, `completed`, `overdue`, `cancelled` |
| Priority | `low`, `medium`, `high`, `critical` |
| AI job | `queued`, `processing`, `completed`, `failed`, `cancelled` |

**Engine-internal statuses (approved by the owner on 2026-10-31).** These are kept separate from the canonical business statuses and never reuse or rename them:

| Entity | Values | Note |
|---|---|---|
| Execution / event processing | reuse **AI job** statuses | no new names |
| Proposal | `pending`, `approved`, `rejected`, `expired`, `executed`, `execution_failed` | separate `ProposalStatus` enum |
| Notification | `is_read: bool` + `read_at: datetime \| None` | not a status enum |

All timestamps are timezone-aware, stored in UTC and rendered in the mentor's configured timezone. All identifiers are UUIDs.

---

## 9. Events and scheduling

Event envelope: `event_id (UUID)`, `event_type`, `occurred_at`, `received_at`, `tenant_ref`, `mentor_ref` (opaque strings), `entity_ref {type, ref}`, `payload` (typed per event), `source` (`marg_backend | scheduler | api | mock`), `schema_version`, `correlation_id`.

Event types are listed in the brief (TASK_*, SCHOOL_VISIT_*, FOLLOWUP_*, TEACHER_RESPONSE_RECEIVED, EVIDENCE_SUBMITTED, VERIFICATION_REQUIRED, SCHEDULE_CONFLICT_DETECTED, WORKLOAD_THRESHOLD_EXCEEDED, DAILY/WEEKLY_PLANNING_TRIGGERED).

Event sources:
1. **Polling monitors** (scheduled jobs) read through the adapter and *derive* events: `TASK_OVERDUE`, `DEADLINE_APPROACHING`, `FOLLOWUP_OVERDUE`. This works without any backend push support.
2. **Inbound webhook endpoint**, if MARG can push events. Whether it can is unknown and listed in the missing-API requirements.
3. **Planning ticks**: a periodic job, every 15 minutes by default, enqueues daily/weekly planning for mentors whose *local* planning time has arrived. The idempotency key is `daily_plan:{mentor_ref}:{local_date}`.

Derived events are deduplicated with deterministic IDs, for example UUIDv5 of `TASK_OVERDUE:{task_id}:{local_date}`, so repeated polls never re-trigger work.

No infinite loops: all periodic work is driven by bounded cron schedules, and each run processes a bounded batch.

---

## 10. Backend integration boundary

```
agents/tools ──▶ MARGBackendAdapter (abstract port, engine schemas only)
                     ├── MockBackendAdapter      BACKEND_MODE=mock   (DEV ONLY)
                     └── HttpMARGBackendAdapter  BACKEND_MODE=marg   (BLOCKED)
                            ├── client.py            httpx, timeouts, retries
                            ├── auth.py              configurable auth scheme
                            ├── endpoint_registry.py endpoint map from config, empty by default
                            └── mapping.py           backend payload ⇄ engine schema
```

- The adapter interface uses **engine schemas**. Mapping to real backend payloads lives only in `mapping.py`.
- `endpoint_registry` starts empty. **No endpoint paths are invented.** Calling an unmapped operation in `marg` mode raises `BackendOperationNotMapped`.
- `BACKEND_MODE=marg` with missing base URL or credentials fails at startup.
- If the backend errors, the request fails. The engine never silently falls back to mock.
- Every mock response carries `data_source: "mock"`, and API responses built from mock data are flagged accordingly.

---

## 11. Security and privacy architecture

- **Identity and RBAC:** each request and job carries a `Principal` (`user_ref`, `tenant_ref`, `roles`, `kind: human|system`). The engine defines its own fine-grained **permissions** (capabilities such as `proposal.approve`, `plan.read`). The **mapping from roles to permissions is configuration**, not code: `config/rbac.dev.toml` in development. **Role names and tenant structure are provisional placeholders.** No final MARG roles are invented. The real mapping will be built from the MARG OpenAPI specification and compatibility audit. How MARG authenticates users is also pending that audit. Until then a dev-only header-based principal is used in mock mode, and it cannot be enabled when `BACKEND_MODE=marg`.
- **Isolation:** every repository query requires `tenant_ref` and `mentor_ref`. Cross-mentor access requires an explicit permission granted through the RBAC config and is audited.
- **Secrets:** loaded through pydantic-settings as `SecretStr`. Never logged or returned. Diagnostic endpoints show "configured: yes/no" only.
- **LLM data minimisation:** the context builder pseudonymises teacher and school names to stable tokens (`T-3f2a`) by default. Real names are re-inserted locally *after* generation, for message drafts only. No student-level personal data is sent to Claude.
- **Prompt injection:** all MARG-sourced or user-written text goes into clearly delimited data sections, and the system prompt states that this content is data, not instructions. Output is schema-constrained. Actions are limited to allow-listed tools and gated by the approval level, so injected text cannot cause a consequential action without a human.
- **Content rules:** no clinical or psychological assessments of teachers or students. Workload Index is labelled an administrative planning metric. Original mentor observations are preserved verbatim, and AI suggestions are always labelled as AI-generated.
- **Audit:** an append-only audit log records approvals, permission denials, cross-mentor access, configuration errors and policy rejections.

---

## 12. Reliability

- Event inbox with unique `event_id` gives at-least-once delivery with exactly-once *effects*, via idempotency keys.
- Retries: exponential backoff with jitter for transient errors only (timeouts, 429, 5xx). There are no retries for validation, permission or 4xx errors.
- Dead-letter table after max attempts. Failures are never dropped silently.
- An action is marked `completed` only after its side effect is confirmed (adapter response validated).
- Graceful shutdown: workers finish or requeue in-flight jobs. API and worker both expose health checks.
- LLM budget guard: per-mentor and global daily token budgets. When a budget is exceeded, agents return deterministic-only results and say so.

---

## 13. Runtime topology

| Process | Command (planned) | Role |
|---|---|---|
| API | `uvicorn app.main:app` | engine REST API, health, approvals |
| Worker | `arq app.jobs.worker.WorkerSettings` | event processing, agent runs, cron monitors |
| PostgreSQL | existing local PostgreSQL 18.6 service (`postgresql-x64-18`), database `marg_mentor_intelligence`, schema `mie` | engine DB |
| Redis | not needed until Phase 5. Recommended: Redis in WSL2 (see TECHNICAL_DECISIONS TD-05) | job broker |

The `marg_db` database on the same PostgreSQL server belongs to MARG. The engine never connects to it. A startup guard refuses any `DB_NAME` in `DB_FORBIDDEN_NAMES` and verifies `current_database()` after connecting.

Cron jobs run inside the worker. Duplicate cron firing across multiple workers is made harmless by idempotency keys.

---

## 14. Refinements to the brief's directory structure

| Change | Reason |
|---|---|
| Added `app/agents/weekly_planning_agent.py` | Section 8.10 defines it, but the tree omitted it |
| Added `app/core/tool_registry.py` | Part 11 requires a tool registry; the tree had none |
| Added `app/api/` (routers) | keeps `main.py` thin |
| Added `app/schemas/event_schemas.py`, `approval_schemas.py`, `notification_schemas.py` | shared contracts |
| Added `app/prompts/` (versioned prompt files) | prompt versioning (Part 7.12) |
| Added `app/db/` (engine, session, base) | SQLAlchemy setup separated from models |
| Added `app/jobs/worker.py` | ARQ worker settings + cron registration |
| Tests split into `unit/`, `integration/`, `safety/`, `e2e/` | matches Part 18 categories |
| Root is the current directory (`D:\MARG-Mentor-Intelligence`) | no nested `marg-mentor-intelligence/` folder |

---

## 15. Decisions and open questions

### 15.1 Resolved by the owner (2026-10-31)

| Topic | Decision |
|---|---|
| Database | Existing local PostgreSQL 18.6, database `marg_mentor_intelligence` only. `marg_db` must never be used or modified. SQLite for isolated unit tests. Credentials in environment variables only. |
| Redis | Undecided. Recommendation in TD-05: WSL2 Redis, no Docker required, needed from Phase 5. |
| Proposal / notification statuses | Approved as in §8 |
| Tenancy and roles | Configurable and provisional. Final values only after the MARG OpenAPI audit. |
| Timezone | `Asia/Kolkata` as the development default, configurable |
| Claude model | One configurable model (`ANTHROPIC_MODEL`), no model IDs hardcoded. The router interface is kept for future routing. |
| Priority factors | Use verified values only. Missing factors are flagged; no default values are assumed (AGENT_DESIGN §2.1). |

### 15.2 Still open (pending the MARG backend audit or owner input)

1. **Tenancy model**: what is a tenant in MARG (state, district, block, organisation)?
2. **Roles**: exact MARG role names, and who may approve which Level-2/3 operations?
3. **Supervisor access**: may supervisors view their mentors' engine data (plans, workload)?
4. **Working hours**: where are they authoritatively stored, MARG or engine preferences?
5. **Event delivery**: can MARG push events (webhooks), or must the engine poll?
6. **Travel data**: does MARG hold school geolocation or travel-time data?
7. **Retention periods** for memory, plans, drafts, usage and audit records.
8. **Tamil support**: Tamil script output for drafts, or also transliteration?
9. **Data residency / ZDR** requirements for sending data to the Claude API.
10. **MARG identifier formats** (UUID, integer, string?). Stored as opaque strings until known.

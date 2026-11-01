# Mentor Intelligence Engine — API Reference (v1, prototype)

Interactive OpenAPI documentation: `http://127.0.0.1:8000/docs` (schema at `/openapi.json`).

## Conventions

| Item | Rule |
|---|---|
| Base path | `/api/v1` (health endpoints at `/health/*`) |
| Identity (dev only) | `X-Actor-Ref: <user ref>` required. Optional `X-Actor-Role: dev_supervisor`, `X-Actor-Kind: system`. Provisional until the MARG audit. |
| API key | `X-API-Key` required only when `ENGINE_API_KEY` is configured |
| Idempotency | Optional `Idempotency-Key` header on agent endpoints. Without it, identical requests on unchanged data return the same execution (`meta.replayed=true`). |
| Envelope | `{"schema_version":"v1","success":bool,"data":...,"error":{"code","message",...},"meta":{}}` |
| Times | ISO 8601 with offset; stored in UTC, shown in the mentor's timezone (Asia/Kolkata in the demo) |
| Errors | 401 auth, 403 `permission_denied`, 404 `not_found`, 409 duplicate/state conflict, 422 `validation_error` / `invalid_request` (with `execution_id`), 500 `internal_error` (no internals exposed) |

## Agent endpoints (all `POST`, body always includes `mentor_ref`; `use_ai` defaults to `true`)

| Endpoint | Agent | Extra body fields | Proposals it can create |
|---|---|---|---|
| `/tasks/prioritise` | Task Intelligence | `include_closed` | — |
| `/time/analysis` | Time Management | `start_date`, `days` (1-14) | — |
| `/schedule/analysis` | Schedule Intelligence | `start_date`, `days` (1-21) | `reschedule_visit` (L2) |
| `/workload/analysis` | Workload Intelligence | `start_date`, `days` (1-31) | — |
| `/followups/analysis` | Follow-up Management | — | — |
| `/school-visits/plan` | School Visit Planning | `start_date`, `days`, `max_schools` | `schedule_visit` (L2) |
| `/plans/daily` | Daily Planning | `date` | — |
| `/plans/weekly` | Weekly Planning | `week_start` | — |
| `/reports` | Reporting | `period` (`daily`/`weekly`), `end_date` | — |
| `/communications/drafts` | Teacher Communication | `followup_ref` or `teacher_ref`, `purpose` (`reminder`/`feedback`/`followup`), `language` (`en`/`ta`), `mentor_note` | `send_teacher_message` (L3) |

Each returns an **execution**:

```json
{
  "schema_version": "v1", "success": true, "meta": {"replayed": false},
  "data": {
    "execution_id": "5b96e516-…", "agent_id": "daily_planning", "mentor_ref": "MEN-001",
    "status": "completed", "ai_status": "generated", "attempts": 1, "trigger": "api",
    "result": {
      "data_source": "demo", "is_demo_data": true,
      "facts":        { "…": "deterministic results computed from records" },
      "ai_status":    "generated",
      "ai_insights":  { "label": "AI-generated suggestions based on the records below. Not records, not decisions.",
                        "content": { "…": "validated Claude output" } },
      "ai_meta":      { "model": "<configured model>", "prompt": "daily_planning/v1", "input_tokens": 2683, "output_tokens": 1454 },
      "missing_data": [ { "entity_type": "task", "entity_ref": "TSK-008", "field": "estimated_minutes", "impact": "…" } ],
      "proposals":    [ ],
      "drafts":       [ ]
    },
    "steps": [ {"step": "context_loaded"}, {"step": "deterministic_analysis"}, {"step": "ai_reasoning"},
               {"step": "policy_checked"}, {"step": "completed"} ]
  }
}
```

`ai_status` values: `generated`, `not_needed`, `disabled`, `unavailable`, `invalid_output` (discarded after one repair attempt), `refused`, `budget_exceeded`. **Facts are always returned**, even when Claude is unavailable.

### Example: task prioritisation (actual demo output, AI disabled)

```
POST /api/v1/tasks/prioritise   {"mentor_ref": "MEN-001"}

rank task_ref priority score  missing                     next_action
1    TSK-001  high     68.26                              Schedule time to start
2    TSK-005  high     66.5                               Overdue - complete it or agree a revised deadline
4    TSK-003  high     64.62                              Complete dependency first: TSK-004
…    TSK-006  (none)   (none) urgency,risk                score not assigned - inputs missing
…    TSK-007  (none)   (none) deadline_proximity          due date not recorded
```

Formula (deterministic): `0.30·urgency + 0.25·impact + 0.20·risk + 0.15·deadline_proximity + 0.10·workload_dependency`. Bands: 0–24 low, 25–49 medium, 50–74 high, 75–100 critical. With any input missing, `status="incomplete"`, `score=null`, `priority=null` and `score_bounds` shows the possible range.

### Example: communication draft (actual live Claude output, Tamil)

```
POST /api/v1/communications/drafts  {"mentor_ref":"MEN-001","followup_ref":"FU-001","language":"ta"}

facts.draft.generated_by = "ai"
facts.draft.body = "வணக்கம் Selvi Murugesan அவர்களே, Panchayat Union Primary School, Kalliyur (DEMO) பள்ளியில் 1 முதல் 3
                    வகுப்புகளுக்கான "தினசரி ஒலிப்பு (phonics) பயிற்சி" செயல் திட்டம் தொடர்பாக ஒரு சிறிய நினைவூட்டல். …"
facts.delivery   = "NOT SENT - requires explicit mentor approval and delivery by the MARG application"
proposals[0]     = {"action_type": "send_teacher_message", "autonomy_level": "L3_explicit_approval", "status": "pending"}
```

Names are not sent to Claude. The model writes `{{teacher_name}}`, `{{school_name}}` and `{{mentor_name}}`, and the engine fills them in locally. If Claude is unavailable, a fixed template is used (`generated_by="template"`).

## Executions

| Method & path | Purpose |
|---|---|
| `GET /executions/{id}` | Status, result and step trail |
| `GET /executions?mentor_ref=MEN-001` | Recent executions |
| `POST /executions/{id}/retry` | Retry a **failed** execution (same idempotency key; `attempts` increments) |

## Approval workflow

Proposal statuses: `pending`, `approved`, `rejected`, `expired`, `executed`, `execution_failed`.

| Method & path | Purpose |
|---|---|
| `GET /proposals?mentor_ref=MEN-001&status=pending` | List proposals |
| `GET /proposals/{id}` | Detail with decision history |
| `POST /proposals/{id}/approve` `{"note": "..."}` | Approve (owning mentor or `dev_supervisor` role; human only) |
| `POST /proposals/{id}/reject` `{"note": "..."}` | Reject |
| `POST /proposals/{id}/external-result` `{"success": true, "detail": "..."}` | MARG app reports delivery of an approved external action |

- **L2 internal actions** (`reschedule_visit`, `schedule_visit`, `update_task_due_date`) are executed through the data adapter after approval and become `executed` only when the change is confirmed. A failure becomes `execution_failed`.
- **L3 external actions** (`send_teacher_message`) stay `approved` after approval. The engine never sends. The MARG application delivers the message and reports the result.
- Approvals are bound to a SHA-256 hash of the payload, so a modified payload is refused. Pending proposals expire after `PROPOSAL_TTL_HOURS`.

## Events

`POST /events`. Events are processed idempotently by `event_id`: the same `event_id` returns the same execution.

```json
{"event_id": "7f3c…", "event_type": "FOLLOWUP_OVERDUE", "mentor_ref": "MEN-001",
 "occurred_at": "2026-11-02T08:00:00+05:30", "entity_type": "followup", "entity_ref": "FU-001"}
```

Routing: TASK_* / DEADLINE_APPROACHING → task_intelligence · SCHOOL_VISIT_CREATED/RESCHEDULED, SCHEDULE_CONFLICT_DETECTED → schedule_intelligence · SCHOOL_VISIT_COMPLETED → school_visit_planning · FOLLOWUP_*, TEACHER_RESPONSE_RECEIVED, EVIDENCE_SUBMITTED, VERIFICATION_REQUIRED → followup_management · WORKLOAD_THRESHOLD_EXCEEDED → workload_intelligence · TASK_COMPLETED → reporting · DAILY/WEEKLY_PLANNING_TRIGGERED → daily/weekly_planning. Background events run without Claude, to control cost. Planning triggers may use Claude.

## Other endpoints

| Path | Purpose |
|---|---|
| `GET /plans?mentor_ref=…&plan_type=daily_plan` · `GET /plans/{id}` | Stored daily/weekly plans and reports |
| `GET /mentors` · `GET /mentors/{ref}/records` | DEMO DATA browsing |
| `GET /demo/info` | Anchor date of the seeded demo data |
| `GET /usage` | Claude token usage by model/outcome (cost only if `LLM_PRICING` is configured) |
| `GET /agents` | Registered agents with input JSON schemas |
| `GET /health/live` · `GET /health/ready` | Liveness; readiness (DB guard check, AI/backend mode; no secrets) |

## Demo walkthrough

`scripts/demo.ps1` runs these steps against a running server and prints the key results:

| Step | Expected result with the seeded DEMO DATA |
|---|---|
| 1 Health | `status=ready`, backend `demo`, database verified |
| 2 Task prioritisation | TSK-001 ranked first (high, ≈68); TSK-003/TSK-010 blocked by dependencies; TSK-006 and TSK-007 have incomplete scores with the missing inputs named |
| 3 Daily plan | Fixed meetings/visit kept; EMIS data entry and TSK-005 placed in free time; TSK-001 and others listed as **"Not enough free working time today"**; TSK-008/WLA-007 "Time estimate not recorded" |
| 4 Workload | Index ≈97% (`high`), flagged as a lower bound; the full-day training day is `overloaded` |
| 5 Schedule | Overlaps VIS-009↔SCH-ITM-03, SCH-ITM-03↔SCH-ITM-02, VIS-011↔full-day training; a `reschedule_visit` proposal for VIS-009 at a verified free slot |
| 6 Follow-ups | 12 total, 4 overdue, 3 awaiting mentor verification, 2 with evidence missing |
| 7 School visits | Schools ranked by attention score; slots suggested only where travel time and availability are recorded |
| 8 Communication | Tamil reminder draft for FU-001 (template when AI is off, Claude when on), **not sent**; L3 proposal `pending` |
| 9 Weekly plan / report | Week's deadlines listed; report counts come from records |
| 10 Approvals | Reschedule → `executed` (visit moved); message → `approved` (awaiting MARG delivery) |
| 11 Duplicates | Second identical request: `replayed=True`, same execution ID |
| 12 Isolation | MEN-001 requesting MEN-002's data → HTTP 403 |

Exact scores and dates depend on the day the demo data was seeded (dates are relative to the anchor date shown in step 1).

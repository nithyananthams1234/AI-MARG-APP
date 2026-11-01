# Prototype Status — 31 October 2026

Working prototype for the 1 November 2026 submission. Everything below was built and tested in this repository. Statements about verification describe what was actually run.

## Verification performed

| Check | Result |
|---|---|
| Automated test suite (`uv run pytest`) | **89 passed**: unit, API, orchestration, approval workflow, mock-Claude, structured-output validation, demo-data tests. No network. |
| Live Claude integration (`-m live_llm`, run once with `ANTHROPIC_MODEL=claude-opus-5-5`, refusal fallback on) | **1 passed.** Daily plan narrative and a Tamil teacher message generated and validated. A separate 4-call sample used ≈5.3k input / 3.0k output tokens. |
| End-to-end demo (`scripts/demo.ps1`) against a running server | All 12 steps completed (run on the SQLite fallback, AI off) |
| Lint (`ruff check app tests`) | Clean |
| Migration `0001` upgrade → downgrade → upgrade | Verified on SQLite |
| **PostgreSQL tests (`-m postgres`)** | **Not yet run.** The `marg_mie_app` role and `mie`/`mie_test` schemas must first be created by the owner (README, Option A). PostgreSQL code paths are implemented but **not yet verified against PostgreSQL 18.6.** |
| Secret exposure | Server log, `/health/ready` and error responses checked: no API key or other secret values |

## Completed (working and tested)

| Area | What works |
|---|---|
| FastAPI application | 28 documented endpoints, versioned `v1` envelope, OpenAPI docs, UTF-8 JSON (Tamil-safe), request IDs, safe error handling |
| Claude provider | Official Anthropic SDK; one model from `ANTHROPIC_MODEL` (none hardcoded); structured outputs from Pydantic schemas; stop-reason checks (refusal, truncation); error mapping (transient vs permanent); SDK retries; optional server-side refusal fallback; prompt caching on the system prompt; versioned prompt files; token usage persisted per call |
| Orchestrator | Validation → permission check → context via adapter → idempotency (input+data hash or `Idempotency-Key`) → agent → policy check on proposals → persistence → step-level execution log; failure recording and retry of failed executions |
| Agent framework | Shared `BaseAgent` template: deterministic analysis always runs; Claude only when useful; one repair attempt for invalid output; graceful fallback (facts always returned); AI output labelled and kept separate from records |
| Agents (10) | Task Intelligence, Time Management, Schedule Intelligence, Workload Intelligence, Follow-up Management, School Visit Planning, Daily Planning, Weekly Planning, Reporting, Teacher Communication. All functional and reachable through the API. |
| Priority calculation | Approved formula in Python; verified inputs only; missing inputs named, no score assigned, bounds shown; bands 0–24/25–49/50–74/75–100 |
| Approval controls | Proposal statuses exactly `pending/approved/rejected/expired/executed/execution_failed`; human-only decisions (owner or provisional supervisor role); payload-hash binding; expiry; internal execution only after approval and only marked `executed` when confirmed; teacher messages never sent by the engine; audit log |
| Safety | Prompt-injection isolation of record text (tested with an injected instruction in the demo data); names withheld from Claude for drafts; report narratives rejected if they contain numbers not in the records; follow-ups never auto-verified; cross-mentor access denied |
| Persistence | SQLAlchemy 2 models + Alembic migration for 18 tables (DEMO DATA tables + executions, steps, proposals, approvals, plans, drafts, LLM usage, audit log) |
| Database safety | Forbidden-name guard (`marg_db`, `postgres`, …), `current_database()`/schema verification at startup, in Alembic, in scripts; application role, never superuser |
| Demo data | 2 mentors, 12 schools, 12 teachers, 16 tasks, 13 visits, 10 observations, 10 action plans, 12 follow-ups, 11 schedule items, 11 workload activities. All fictional, labelled DEMO DATA, dates relative to the seed day. Includes deliberate gaps (missing estimates, missing travel time, a mentor without working hours). |
| Events | `POST /events` routes 17 event types to agents, idempotent by `event_id` |

## Partial

| Area | Limitation |
|---|---|
| PostgreSQL | Implemented and guarded, but not yet run against the local PostgreSQL 18.6 (waiting for role/schema setup). asyncpg compatibility with PostgreSQL 18 still to be confirmed by `pytest -m postgres`. |
| Identity & roles | Development headers (`X-Actor-Ref`, `X-Actor-Role`) and a placeholder `dev_supervisor` role. Real authentication and MARG roles come after the backend audit. Optional `ENGINE_API_KEY` for service-to-service calls. |
| Tamil | Claude drafts in Tamil worked in the live test. The **fallback templates** in Tamil should be reviewed by a native speaker. |
| Cost reporting | Token counts recorded per call. USD cost only if `LLM_PRICING` is configured; cache-token pricing is approximated at the input rate. |
| Daily planning algorithm | Greedy, no task splitting across slots; plans the full working day (not "from now"). |
| Travel time | Only base-to-school travel is modelled; school-to-school travel is reported as unverifiable. |
| Visit attention score | Documented fixed weights in code (not yet configurable). |

## Deferred (not implemented today, by design or instruction)

- Redis, background workers and scheduled jobs (daily/weekly planning runs on request or via events, not automatically on a timer).
- Real MARG backend adapter. `BACKEND_MODE=marg` is refused, and the placeholder adapter raises `BackendIntegrationNotAuthorised`. No MARG endpoints were invented.
- Backend compatibility documents (`BACKEND_COMPATIBILITY_REPORT.md`, `API_MAPPING.md`, …), Phase 8.
- External messaging (WhatsApp/SMS). Never sent by the engine.
- Persistent mentor-preference editing API and long-term memory/retention policies.
- Duplicate-LLM-call cache across different executions (repeat requests are already deduplicated by the orchestrator).
- Production deployment guide, rate limiting at the API edge, OpenTelemetry.

## Deviations from the Phase 0 design (deliberate, for the prototype)

| Phase 0 plan | Prototype | Reason |
|---|---|---|
| Mock backend adapter with in-memory data | `DemoDataAdapter` reading **DEMO DATA tables in the engine database** | The brief asked for persistent storage of tasks and seed data; the adapter interface is unchanged, so the MARG adapter can replace it |
| `BACKEND_MODE=mock` | `BACKEND_MODE=demo` | Matches the "DEMO DATA" labelling |
| `messages.parse` helper | `messages.create` + `output_config.format` built with the SDK's `transform_schema`, then Pydantic validation | `parse` raises before the stop reason can be checked, which hid refusals; this keeps the same structured-output guarantee |
| TOML RBAC file | Provisional supervisor roles via `DEV_SUPERVISOR_ROLES` | Simpler; roles remain provisional until the MARG audit |
| ARQ/Redis worker | Not built | Instructed to defer Redis |
| Anthropic SDK 1.x expected | Installed SDK is **2.3.0** (uses `httpx2`) | Latest available; verified against the installed API |

# MARG Mentor Intelligence Engine — Development Roadmap

| | |
|---|---|
| Last updated | 2026-10-31 |
| Current phase | **Working prototype delivered 31 Oct 2026** (owner-authorised acceleration of Phases 1–4). See [PROTOTYPE_STATUS.md](PROTOTYPE_STATUS.md). |

Status legend: ✅ done · 🟡 in progress · ⬜ not started · ⛔ blocked

Every phase ends with: a summary of what was built, the files changed, test results, remaining work, and **owner approval before the next phase**.

---

## Phase 0 — Inspection and planning ✅
- ✅ Inspected the environment (directory was empty; Python 3.12/3.14, uv, git present; Docker/PostgreSQL/Redis absent)
- ✅ `docs/ARCHITECTURE.md`, `docs/AGENT_DESIGN.md`, `docs/TECHNICAL_DECISIONS.md`, `docs/DEVELOPMENT_ROADMAP.md`
- ✅ Initial folder structure (packages only, no implementation)
- ✅ `.env.example`, `.gitignore`, `README.md`

**Exit criteria:** owner reviews docs and answers the blocking open questions. ✅ Committed as `38bd36d`. Owner decisions recorded 2026-10-31 (ARCHITECTURE §15.1).

---

## Phase 1 — Foundation ⬜ (detailed plan: [PHASE_1_PLAN.md](PHASE_1_PLAN.md))
| Item | Deliverable | Tests |
|---|---|---|
| Project config | `pyproject.toml`, `uv.lock`, `requirements.txt` export, ruff/mypy config | — |
| Settings | `app/config.py` (pydantic-settings, `SecretStr`, startup validation, mode rules) | missing key, invalid mode, marg-mode without URL |
| Logging | JSON logging + redaction filter + context vars | secrets never appear in logs |
| Schemas | `schemas/common.py` (canonical status enums, UUID, aware datetimes), task/schedule/followup/visit/execution schemas | enum values match brief exactly |
| DB | `app/db/`, base models for executions, events, usage. Alembic init + first migration | migration up/down on SQLite; Postgres marker |
| Provider | `LLMProvider` port, `AnthropicProvider`, `model_factory`, `usage_tracker`, prompt loader | mocked API: success, invalid JSON, refusal, max_tokens, 429, timeout, auth error |
| Health | `/health/live`, `/health/ready` | no secret leakage |
| Mock backend | `MARGBackendAdapter` port + `MockBackendAdapter` + labelled mock dataset | data_source flag, tenant isolation in mock |
| BaseAgent | template `run()`, `AgentContext`, `AgentResult` | validation, tool allow-list enforcement, LLM gate, budget fallback |

**Milestone M1:** `pytest` green with no external services. App boots in mock mode.

## Phase 2 — Core orchestration ⬜
Agent registry · event models + inbox + processor · context builder (minimisation, pseudonymisation) · orchestrator · tool registry · policy engine · approval engine (proposals, hash-bound approvals, TTL) · execution engine (step logging, confirmation, idempotency).

**Milestone M2:** a synthetic event flows through all 14 pipeline steps with a dummy agent and fake LLM, including a Level-2 proposal → approval → execution path.

## Phase 3 — First operational agents ⬜
1. Task Intelligence (+ priority service)
2. Time Management
3. Workload Management (+ workload service)
4. Follow-up Management
5. Schedule Intelligence (+ conflict/free-slot service)

**Milestone M3:** each agent passes its unit, fake-LLM, policy and mock-scenario tests.

## Phase 4 — Advanced agents ⬜
1. School Visit Planning
2. Daily Planning
3. Weekly Planning
4. Automated Reporting (number-consistency validator)
5. Teacher Communication (English + Tamil drafts, no send tool)

**Milestone M4:** daily plan and weekly report generated end-to-end from mock data.

## Phase 5 — Autonomous operation ⬜
ARQ worker · cron monitors (deadline, overdue, follow-up) · planning tick · derived-event dedupe · notification generation · dead-letter + reconciliation job · graceful shutdown.

Needs Redis (TD-04/TD-05).

**Milestone M5:** worker runs unattended against mock data for a simulated week without duplicate effects.

## Phase 6 — Security and reliability ⬜
Permission enforcement audit · approval enforcement · cross-mentor isolation tests · prompt-injection test suite · rate-limit and budget behaviour · audit log completeness · failure recovery drills.

**Milestone M6:** safety test suite green.

## Phase 7 — Complete independent testing ⬜
All unit/integration/safety/E2E tests. E2E scenarios from the brief:
1. deadline approaching → priority → notification → execution record
2. overloaded schedule → workload index → revised schedule proposal
3. teacher non-response → overdue follow-up → reminder draft for approval
4. new day → daily plan
5. end of week → weekly summary

Deliverables: test execution report, Claude usage and cost report, known-limitations list.

**Milestone M7:** independent development complete (mock-backed).

## Phase 8 — Backend compatibility preparation ⛔ (partly)
- ⬜ `docs/BACKEND_COMPATIBILITY_REPORT.md`, `API_MAPPING.md`, `MISSING_API_REQUIREMENTS.md`, `DATA_SCHEMA_MAPPING.md`, `SECURITY_MAPPING.md`, `INTEGRATION_TEST_PLAN.md`, `BACKEND_INTEGRATION_GUIDE.md`
- ⛔ `HttpMARGBackendAdapter` implementation: **blocked** until the real MARG OpenAPI spec and compatibility audit are provided and the work is authorised.
- ⬜ Production deployment guide, security documentation, API docs export.

---

## Decisions log (2026-10-31)

| # | Question | Decision |
|---|---|---|
| 1 | Database / Redis | Existing PostgreSQL 18.6, DB `marg_mentor_intelligence` only. SQLite for unit tests. Redis: undecided; WSL2 recommended, needed in Phase 5 |
| 2 | Proposal / notification statuses | Approved (ARCHITECTURE §8) |
| 3 | Tenancy and roles | Configurable and provisional until the MARG OpenAPI audit |
| 4 | Timezone | `Asia/Kolkata` development default, configurable |
| 5 | Claude model | One configurable model, no hardcoded IDs, router kept for the future |
| 6 | Priority factors | Verified values only; missing factors flagged, never defaulted |

### Still open
- Redis option (needed before Phase 5).
- ARCHITECTURE §15.2 items. These are tracked as `missing_data` behaviour in the meantime.

---

## Risks

| Risk | Mitigation |
|---|---|
| Real MARG API differs from assumptions | adapter port uses engine schemas; mapping isolated; no invented endpoints |
| MARG cannot push events | polling monitors derive events (designed in from the start) |
| LLM cost growth | gating, budgets, caching, usage reporting; model routing ready if needed |
| ARQ maintenance status | `JobQueue` port; swap confined to `app/jobs/` |
| Prompt injection via teacher responses | data-block isolation, schema output, allow-listed tools, human approval for consequential actions |
| Accidental use of `marg_db` (same PostgreSQL server) | forbidden-name guard, `current_database()` check, dedicated role without grants on `marg_db` (TD-18) |
| asyncpg on PostgreSQL 18 | verified in Phase 1; psycopg 3 fallback confined to `app/db/` |
| ARQ worker on native Windows | verified in Phase 5; fallback: run the worker in WSL2 |

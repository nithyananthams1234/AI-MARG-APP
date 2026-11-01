# MARG – Testing

The results below are the **pre-NVIDIA migration baseline**, run on the
development machine on 31 Oct 2026: Windows 11, Python 3.12, Node 24,
PostgreSQL 18, Ollama 0.40 with qwen2.5:3b on an RTX 2050. They do not verify
the NVIDIA provider changes.

## Summary

| Suite | Command | Result |
|---|---|---|
| Backend (FastAPI + real PostgreSQL `marg_test`) | `pytest -p anyio tests` | **49 passed** |
| Classroom Coach, offline (fakes) | `pytest tests` | **8 passed** |
| Classroom Coach, live (real KB + local LLM) | `RUN_LIVE_COACH_TESTS=1 pytest tests/test_live.py` | **2 passed** |
| Mentor Intelligence (providers mocked) | `pytest` | **130 passed** (3 opt-in live/postgres tests deselected) |
| Frontend unit + screen workflow (Jest, RNTL, expo-router) | `npx jest` | **9 passed** |
| Frontend static checks | `npx tsc --noEmit`, `npx expo lint` | 0 errors (lint: 1 minor warning) |
| Frontend production build | `npx expo export --platform web` | success |
| Browser end-to-end (Playwright, Chrome, Pixel 7 viewport, full stack) | `npx playwright test` | **4 passed** |
| Live integration scripts (backend ↔ Coach ↔ Mentor Intelligence) | `.scratch/e2e_coach.py`, `.scratch/e2e_mentor_ai.py` | passed (outputs summarised below) |

## What the tests cover

### Backend (`Marg-AppBackend/tests`)
- **Authentication:** login, case-insensitive email, identical response for a wrong password and an unknown email, non-login roles refused, refresh-token rotation, reuse detection that revokes the token family, logout, rate limiting (429 + Retry-After), invalid and missing tokens.
- **Authorisation and isolation:** schools, teachers, classrooms, visits, observations, tasks, reports and evidence downloads are invisible across mentors (404). Mentors cannot assign schools or create schools. An admin assignment grants access, and deactivating it removes access.
- **Full mentor workflow:** visit → observation → evidence → finding → gap → recommendation (an action plan is blocked until approval) → approval → plan → step → follow-up lifecycle → visit completion. Dashboard, school, learning-gap and activity reports are checked against the created records, along with automatic version increments.
- **Offline sync:** client-generated IDs; ordered chains; idempotent re-push (no duplicates); stale updates become conflicts and server data wins; partial failure; writes to an unassigned school are rejected; keys reused by another user are rejected; pull pagination with no duplicates; tombstones; tasks without a school are synced.
- **AI integration (fake Coach):** analysis input is built server-side with no names; job completion notification; apply produces `ai_suggested` records and works only once; a short-notes guard; another mentor's observation gives 404; Coach outage gives a safe failure; retry re-runs the job; grounded chat.
- **Mentor Intelligence service API:** service key required (a user JWT is rejected); fails closed when not configured; scoped snapshot; approved actions follow business rules and scope; the proxy always asserts the authenticated mentor's identity; unknown agents give 404.
- **Storage:** disguised files are rejected (magic bytes); cross-mentor download gives 404; S3 round trip with a stub client; production configuration guards; path-traversal keys are rejected.
- **Reminders:** generated once (idempotent) and visible only to the owner.
- **Errors:** unhandled exceptions never leak details.

### Classroom Coach (`Marg-LLM/tests`)
- **Service key auth:** required on every protected endpoint.
- **Grounded answers:** sources carry real titles, and citations to sources that weren't retrieved are removed.
- **No knowledge found:** reported honestly, without calling the LLM.
- **Validation:** inputs are validated, and the analysis output matches the backend contract.
- **Failure handling:** LLM outage gives 503 with no internals, and unexpected errors don't leak.
- **Live tests:**
  - On-topic retrieval scores at cosine distance below 0.45, and off-topic questions retrieve nothing.
  - Results are de-duplicated.
  - A real chat answer and a schema-valid observation analysis were both produced (about 32 s).

### Mentor Intelligence (`MARG-Mentor-Intelligence/tests`)
- The existing 115 tests cover agents, orchestration, approvals, provider error mapping and more.
- New tests:
  - The real MARG HTTP adapter against a mocked transport: endpoint mapping, service key, error mapping, no silent demo fallback, invalid snapshot detection.
  - Trusted-gateway identity: the key is required, and a mentor cannot act for another mentor.
  - The `marg` mode configuration rules.
  - NVIDIA provider request construction, JSON validation and usage tracking (mocked; no network).

### Frontend (`Marg-AppFrontend/src/**/__tests__`)
- **API layer:**
  - Backend error messages are surfaced, and validation errors are formatted.
  - Network errors are flagged as offline.
  - Form-encoded login stores the tokens.
  - A single shared refresh happens for concurrent 401s, with retry.
- **Offline queue:**
  - The outbox is used only for network failures (never for business errors) and is persisted.
  - Flushing keeps operation order, removes synced items, and keeps conflicts and failures with their reasons.
  - Retrying a conflict uses the server version.
- **Screen workflow:** the root layout's route guard redirects to login; a wrong password shows an error; login lands on a dashboard populated from the API.

### Browser E2E (`e2e/tests/mentor-app.spec.ts`), against the running stack and demo data
1. A protected route redirects to login, and a wrong password is rejected.
2. **All 14 mentor screens** (dashboard, schools, visits, observations, action plans, follow-ups, tasks, schedule, notifications, reports, Classroom Coach, Mentor AI, profile, sync) render the expected seeded records with **no page errors, console errors or HTTP 5xx**.
3. The mentor creates a task through the UI, and it is still there after a full reload (persisted in PostgreSQL).
4. The Classroom Coach answers a real question in the browser with `[S1]`-style knowledge-base citations (local LLM).

## Live integration results (31 Oct 2026)

**Classroom Coach** (via the backend, as the demo mentor):
- Coach status: available, qwen2.5:3b, MiniLM-L6-v2, 33,624 chunks.
- Chat about equivalent fractions: grounded, 5 sources, about 7 s. An off-topic question returned `grounded=false`.
- AI analysis of the seeded Grade 8 science observation: completed in 18 s with 2 findings, 3 gaps and 3 recommendations, all consistent with the notes, plus sources.
- Applied suggestions were created as `ai_suggested`, pending mentor approval.

**Mentor Intelligence** (`BACKEND_MODE=marg`, Claude disabled for the test):
- 6 agents ran on real backend data: task prioritisation, daily plan, follow-up analysis, workload, visit planning and schedule analysis.
- Proposals referenced real backend records.
- Approving a `schedule_visit` proposal executed it through the backend service API: the visit count went from 8 to 9, and a notification was created.
- Later, a `reschedule_visit` approval also executed correctly.

## Historical live Claude test – Mentor AI Assistant (`claude-opus-5`, 31 Oct 2026)

- **Model:** availability was verified first through the Models API (`claude-opus-5`, 1M context, 128K output). It is configured only in Mentor Intelligence (`ANTHROPIC_MODEL`).
- **Budget:** 40,000 tokens, enforced by Mentor Intelligence's token-budget check plus a guard in the test script. Used: **15,541 tokens**, no budget stop.
- **Path:** demo mentor → backend `/mentor-ai/*` → Mentor Intelligence (`BACKEND_MODE=marg`) → Claude. Snapshot data comes from the backend service API.

| Agent | HTTP | Latency | `ai_status` | Structured output (validated) | Proposals |
|---|---|---|---|---|---|
| task_prioritisation | 200 | 25.5 s | generated | summary, next_actions, cautions | – |
| daily_plan | 200 | 15.7 s | generated | overview, item_explanations, advice | – |
| visit_planning | 200 | 21.1 s | generated | summary, schools | schedule_visit |
| followup_analysis | 200 | 13.7 s | generated | summary, next_steps | – |
| teacher_message_draft | 200 | 5.2 s | generated | body (teacher/school names as placeholders) | send_teacher_message |

All 5 calls: `model_served = claude-opus-5`, `stop_reason = end_turn`, first attempt, no repair, no API errors.

**Usage:** 5,281 input + 5,158 output (includes adaptive thinking) + 5,102 cache-write tokens.
**Cost:** Mentor Intelligence's recorded estimate is $0.181; it prices cache writes at the input rate. At Anthropic's rates ($5 / $25 per MTok, cache write 1.25× input) the cost is **≈ $0.19**.

**Approval safeguards (verified live):**
- After the agents ran and created proposals, visits and tasks were **unchanged**.
- Mentor B tried to approve mentor A's proposal: **403**, records unchanged.
- Rejecting a proposal: status `rejected`, records unchanged.
- Approving `schedule_visit`: status `executed`; the visit was created through the backend service API (8 → 9 visits).
- Approving `send_teacher_message`: status `approved` (needs external delivery by the mentor); **no official record changed**.

**Tool calls:** Mentor Intelligence does not use Claude tool use. Claude only produces validated, schema-constrained insights. All actions are proposals, executed deterministically by the engine after mentor approval.

## Refusal fallback (`ANTHROPIC_REFUSAL_FALLBACK=default`, 31 Oct 2026)

- **Mechanism:** server-side fallback, beta header `server-side-fallback-2026-07-01`, with `fallbacks: "default"`. Anthropic routes declined requests by refusal category.
- **Exact fallback model:** `allowed_fallback_models` for `claude-opus-5` on this account (Models API) is **`["claude-opus-4-8"]`**. Same provider (Anthropic) and same key.
- **Cost:** extra cost only when a request is refused. The fallback attempt is billed at `claude-opus-4-8` rates, the same $5 / $25 per MTok as `claude-opus-5`. A mid-output decline is billed at normal rates; whether a decline before any output is billed depends on the category. Mentor Intelligence now sums `usage.iterations`, so all attempts count toward its token budgets and cost records.
- **Mocked tests:** synthetic fallback responses (declined, then served by `claude-opus-4-8`, plus whole-chain refusal): passed.
- **Live check:** one normal request with fallback enabled. HTTP 200, 6.5 s, **served by `claude-opus-5`** (no fallback), 1,238 tokens, ≈ $0.012.
- **Not done:** a live refusal was **not** provoked on purpose; that would mean sending policy-violating content. The fallback-served path is verified with the mocked responses above.

## Not yet tested (honest gaps)

- **Production Docker images and the compose stack.** Docker is not installed on the
  development machine, so the images have not been built yet. Do this on the server
  before go-live (DEPLOYMENT.md §6–7).
- **Native Android/iOS builds.** The tests ran on web (mobile viewport) and with the Jest
  native preset. No device or emulator run yet.
- **Offline behaviour in a real browser.** Covered by unit and backend tests, but there is
  no Playwright offline scenario yet.
- **PostgreSQL integration tests of Mentor Intelligence** (`-m postgres`). Not run.

## Running the browser tests

```powershell
# backend :8000, Coach :8001, Mentor Intelligence :8002 and Expo web :8082 must be running
cd e2e; npm install; npx playwright install chromium    # or use installed Chrome: $env:E2E_CHANNEL="chrome"
$env:E2E_PASSWORD="<demo password>"; npx playwright test
```

If Expo web shows stale screens or "Unable to resolve module" after many file
changes, restart it with `npx expo start --web --clear`.

# MARG – System architecture

MARG is a **mentor-focused** classroom-improvement platform. The only application
users are **mentors**, plus an Administrator role used for system administration
(school assignments). Teachers and students do not have accounts. Teachers are
the subjects of mentoring, and student learning appears only as aggregated
observations and learning gaps.

## Components

| Component | Folder | Technology | Responsibility |
|---|---|---|---|
| MARG Frontend | `Marg-AppFrontend` | Expo SDK 58, React Native + web, expo-router, React Query, zustand | Mentor app (Android/iOS/web); offline-first |
| MARG Backend | `Marg-AppBackend` | FastAPI, async SQLAlchemy 2, PostgreSQL, Alembic | Authoritative business data, auth, access control, sync, AI orchestration |
| Classroom Coach | `Marg-LLM` | FastAPI, Ollama (Qwen 2.5 3B), sentence-transformers MiniLM-L6-v2, ChromaDB | Educational intelligence: RAG Q&A, observation analysis |
| Mentor AI Assistant | `MARG-Mentor-Intelligence` | FastAPI, Anthropic Claude API, PostgreSQL (own DB) | Mentor workflow intelligence: priorities, plans, workload, visit planning, follow-ups, reports, message drafts |

```
 Mentor (phone / browser)
        │  HTTPS, JWT (access + rotating refresh token)
        ▼
 MARG Backend (FastAPI) ── PostgreSQL marg_db  (authoritative business data)
   │   ├── row-level school scoping on every query
   │   ├── offline sync (push/pull), notifications, reports, evidence (S3)
   │   │
   │   ├──► Classroom Coach API      (X-API-Key)      ──► Ollama Qwen 2.5 3B
   │   │       /api/v1/chat                              ChromaDB (33,624 chunks,
   │   │       /api/v1/analyze/observation               167 educational PDFs)
   │   │
   │   └──► Mentor Intelligence API  (X-API-Key + asserted mentor identity)
   │           agents, proposals, approvals ──► Anthropic Claude API
   │                      │
   └◄──── service API ────┘ (X-Service-Key, scoped to one mentor):
          snapshot + 3 approved actions (schedule/reschedule visit, task due date)
```

**Boundaries enforced in code:**

- The frontend talks **only** to the backend. AI service URLs and keys are never sent to the client.
- The two AI systems are independent. Each has its own data store: ChromaDB for the
  Coach, and the `marg_mentor_intelligence` database (schema `mie`) for Mentor
  Intelligence. Neither reads the other's data.
- Mentor Intelligence never touches the MARG database. It reads a per-mentor snapshot
  and executes approved actions through backend APIs that apply the normal business rules.

## Backend

### Security

- **Passwords:** Argon2 hashing (pwdlib). Login is timing-safe, so it does not reveal whether an account exists.
- **Login rate limiting:** 10 attempts per 5 minutes per IP and email.
- **Tokens:** typed JWT access tokens lasting 30 minutes, plus refresh tokens stored
  as hashes. Refresh tokens rotate on every use. Reusing a rotated token revokes the
  whole token family. Logout revokes the refresh token (or all of the mentor's sessions).
- **School-level access control** (`app/auth/access.py`): a single SQLAlchemy
  `do_orm_execute` hook adds the mentor's scope to **every** ORM query on 21
  entities. Scope means the actively assigned schools, or records the mentor owns
  (tasks, AI jobs, notifications, sync operations). Request sessions are
  deny-by-default, and out-of-scope records return 404. This closes the cross-school
  IDOR that existed before the integration.
- **Administrator role:** school assignments and school creation require the
  existing Administrator role. Previously mentors could assign themselves to any school.
- **Uploads:** checked against the declared type and the file signature, size-limited,
  and checksummed. Downloads always pass through the scoped endpoint, never public URLs.
- **Production guards:** S3 storage required, a strong JWT secret, https-only CORS,
  no debug output, and interactive API docs disabled.
- **Errors:** 500 responses never contain internal details. Every request has an ID for log correlation.

### Data model (main chain)

`School → SchoolVisit → Observation → ObservationFinding / LearningGap → Recommendation → ActionPlan → ActionPlanStep → FollowUp`
plus `Teacher`, `Classroom`, `Timetable`, `Evidence`, `MentorTask`, `Schedule`,
`Notification`, `AIJob`, `SyncOperation`, `RefreshToken` and `MentorSchool` (assignments).
Primary keys are UUIDs. Records are soft-deleted (`deleted_at`) and carry a
`version` that is incremented automatically on every update.

### Approval rules (human in the loop)

- Findings and recommendations created by AI, or recorded from AI suggestions, start as
  `ai_suggested`. They become official only after an explicit mentor decision
  (`mentor_approved`).
- Action plans can only be created from **mentor-approved** recommendations, and pass
  through `pending_approval → approved`.
- Mentor Intelligence actions (visit scheduling and rescheduling, task due-date
  changes, teacher messages) are **proposals**. They execute only after the owning
  mentor approves them, and execution is audited.

### Offline-first synchronisation

- **Push** (`/sync/push`): operations are stored idempotently (globally unique keys)
  and applied **through the same route handlers as the online API**, inside the
  mentor's scope.
  - Creates use client-generated UUIDs.
  - Updates and deletes carry `client_version`. If the server version is different, the
    operation becomes `conflict` and is not applied, so newer data is never silently overwritten.
  - Each operation reports `synced`, `conflict` or `failed`.
- **Pull** (`/sync/pull`): composite cursor `(updated_at, entity_type, id)`, with
  tombstones for deleted records, scoped to the mentor.
- **Frontend:** a persisted outbox, automatic flush when the device reconnects, a
  Sync screen for reviewing and resolving conflicts, and a persisted query cache
  for reading offline.

## Classroom Coach

- **Models (preserved):** the Qwen 2.5 3B LLM and the MiniLM-L6-v2 embedding model
  (384 dimensions, normalised), plus the existing ChromaDB collection, used with no re-ingestion.
- **Retrieval:**
  - Over-fetch 30 candidates.
  - De-duplicate, including duplicated PDFs such as "(1)" copies.
  - Keep at most 2 passages per document.
  - Apply a relevance cutoff at cosine distance 0.60. This was calibrated on this
    corpus: on-topic queries score 0.18–0.40, off-topic ones 0.75 or more.
  - Use real titles from the ingestion mapping.
- **Grounding:**
  - If nothing relevant is retrieved, the LLM is not called and the answer is marked `grounded=false`.
  - Citations `[S n]` that point to sources that were not provided are removed.
  - The prompt delimits untrusted text and tells the model to ignore instructions inside it.
- **Structured analysis:** Ollama's JSON-schema mode plus Pydantic validation, with
  one repair attempt. The output matches the backend's `AIAnalysisResponse`.
- **Privacy:** the backend sends only educational context (subject, grade, topic, notes),
  never teacher or student names.

## Mentor Intelligence

- 10 agents. Each first runs a deterministic analysis (priority formula, workload
  index, schedule conflicts, follow-up layers), then optionally makes one Claude call
  that produces **validated insights only**. If the AI is unavailable, the
  deterministic result is still returned (`ai_status`).
- Structured outputs (`output_config.format` JSON schema), Pydantic validation,
  stop-reason checks, transient/permanent error mapping, SDK retries, timeouts.
- Idempotent executions, an audit log, per-mentor and global daily token budgets, and usage/cost records.
- Teacher names are replaced with placeholders before any Claude call.

## Frontend

- One API layer (`src/lib/api`). Types are generated from the backend OpenAPI schema
  (`scripts/generate_ts_types.py`), so the frontend and backend contracts cannot drift.
- React Query hooks (`src/hooks/api.ts`). Loading, error, empty and saved-data states are handled consistently.
- Token storage: SecureStore on native, sessionStorage on web.

## Planned (not implemented)

- Real WhatsApp provider integration. Today mentors send messages through a `wa.me`
  deep link after approving the draft; the backend queue table exists, but no provider is connected.
- Push notifications. Notifications are in-app only.
- Supervisor dashboards and approvals. The role exists but has no workflows, and none
  were added without approval.
- Re-ingestion of the knowledge base with OCR and de-duplicated source PDFs.
- Multi-instance deployments: the login rate limiter is in-process and would need Redis.

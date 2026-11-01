# MARG – Mentoring, Action, Reflection, Growth

MARG is a **mentor-focused classroom-improvement platform** for school mentors in
India. Mentors plan school visits, observe classrooms, identify learning gaps,
agree improvement plans with teachers and follow them up with evidence. Two
independent AI assistants support them:

- **Classroom Coach:** educational intelligence. An NVIDIA-hosted LLM with
  retrieval over a 167-document educational knowledge base (NCF, NEP, CCE,
  mentoring and observation manuals). It answers teaching questions and analyses
  classroom observations, citing its sources.
- **Mentor AI Assistant:** workflow intelligence powered by an NVIDIA-hosted LLM.
  Daily and weekly plans, task prioritisation, workload, visit planning, follow-up
  monitoring, reports and teacher message drafts. Every consequential action
  needs the mentor's approval.

Mentors are the only users. Teachers and students do not have accounts, and all demo data is fictional.

## Repository layout

| Folder | What it is |
|---|---|
| `Marg-AppFrontend/` | Expo (React Native + web) mentor app |
| `Marg-AppBackend/` | FastAPI + PostgreSQL backend (authoritative data, auth, sync, AI orchestration) |
| `Marg-LLM/` | Classroom Coach service (NVIDIA-hosted LLM + ChromaDB RAG) |
| `MARG-Mentor-Intelligence/` | Mentor Intelligence Engine (NVIDIA-hosted agents, approvals) |
| `deploy/` | Production Docker Compose, Caddy (HTTPS), backups |
| `e2e/` | Playwright browser end-to-end tests |
| `docs/` | Architecture, deployment, testing, demo guide, submission material |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design, the security
model and the human-in-the-loop rules.

## Technologies

- **Frontend:** Expo SDK 58, React Native 0.88, expo-router, TanStack Query, zustand, axios, Jest + RNTL
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic, PyJWT, Argon2 (pwdlib), boto3
- **Database:** PostgreSQL 17/18
- **Classroom Coach:** NVIDIA-hosted chat completions (`NVIDIA_MODEL`), sentence-transformers **all-MiniLM-L6-v2**, ChromaDB
- **Mentor Intelligence:** NVIDIA-hosted OpenAI-compatible chat completions (`NVIDIA_MODEL`), structured outputs validated by Pydantic
- **Deployment:** Docker Compose, Caddy (Let's Encrypt), S3-compatible object storage (e.g. Cloudflare R2)

### External AI models and services

| Service | Used by | Data sent |
|---|---|---|
| NVIDIA API Catalog (hosted) | Classroom Coach | Question / observation notes, subject, grade (no names) |
| sentence-transformers MiniLM-L6-v2 (self-hosted) | Classroom Coach | Same as above (embeddings) |
| NVIDIA API Catalog (hosted) | Mentor AI Assistant | Mentor workflow facts; teacher names replaced by placeholders |

## Run locally (Windows, development)

Prerequisites: Python 3.12, Node 22+, PostgreSQL 17+, an NVIDIA API key, and the knowledge base in `Marg-LLM/data/chroma_db`
(not in git, about 360 MB).

```powershell
# 1. Backend
cd Marg-AppBackend
py -3.12 -m venv .venv; .venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env        # set DATABASE_URL (a *_demo database), JWT_SECRET_KEY, service keys
.venv\Scripts\python -m alembic upgrade head
$env:DEMO_PASSWORD="<choose a password>"; .venv\Scripts\python -m app.database.seed_demo
.venv\Scripts\uvicorn app.main:app --port 8000

# 2. Classroom Coach
cd ..\Marg-LLM
py -3.12 -m venv .venv; .venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # set NVIDIA_API_KEY and COACH_API_KEY = backend CLASSROOM_COACH_API_KEY
.venv\Scripts\uvicorn app.main:app --port 8001

# 3. Mentor Intelligence
cd ..\MARG-Mentor-Intelligence
# see its README for the database role; then in .env:
#   BACKEND_MODE=marg, MARG_BACKEND_URL=http://localhost:8000, MARG_BACKEND_SERVICE_KEY=<backend MENTOR_INTELLIGENCE_SERVICE_KEY>
#   ENGINE_API_KEY=<backend MENTOR_INTELLIGENCE_API_KEY>, NVIDIA_API_KEY, NVIDIA_MODEL
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\uvicorn app.main:app --port 8002

# 4. Frontend (web)
cd ..\Marg-AppFrontend
npm ci
copy .env.example .env        # EXPO_PUBLIC_API_URL=http://localhost:8000/api/v1
npx expo start --web
```

For the local development stack, both `Marg-LLM/.env` and
`MARG-Mentor-Intelligence/.env` must contain the NVIDIA API key and a model ID.
The key is server-side only; do not add it to the frontend `.env`.

On a phone with Expo Go, set `EXPO_PUBLIC_API_URL=http://<your-PC-LAN-IP>:8000/api/v1`
and add that origin to the backend's `CORS_ORIGINS` (web only).

## Environment variables

Every variable is documented in each service's `.env.example`:
[backend](Marg-AppBackend/.env.example), [Coach](Marg-LLM/.env.example),
[Mentor Intelligence](MARG-Mentor-Intelligence/.env.example),
[frontend](Marg-AppFrontend/.env.example) and [production](deploy/.env.example).
Real `.env` files are git-ignored and must never be committed.

## Sample data

`python -m app.database.seed_demo` creates a complete fictional workspace:
3 users, 5 schools, 10 teachers, 10 classrooms with timetables, visits,
observations, findings, gaps, recommendations, plans, steps, follow-ups, tasks,
schedules and notifications.

- **Idempotent:** deterministic UUIDs, so re-running never duplicates anything.
- **Isolated:** it only runs against a database whose name ends in `_demo`.
- **Reset:** `--reset` rebuilds the demo database only.

Evaluation scenarios: [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md).

## Tests

See [docs/TESTING.md](docs/TESTING.md). In short:

```powershell
cd Marg-AppBackend; .venv\Scripts\python -m pytest -p anyio tests          # needs PostgreSQL (marg_test DB)
cd Marg-LLM; .venv\Scripts\python -m pytest tests                          # + RUN_LIVE_COACH_TESTS=1 for live model
cd MARG-Mentor-Intelligence; .venv\Scripts\python -m pytest                # providers mocked; RUN_LIVE_LLM_TESTS=1 for live
cd Marg-AppFrontend; npx jest; npx tsc --noEmit; npx expo lint
cd e2e; $env:E2E_PASSWORD="..."; npx playwright test                       # full stack running
```

## Deployment

Production deployment (single VM with Docker Compose, HTTPS, backups, rollback,
and cost estimates): [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

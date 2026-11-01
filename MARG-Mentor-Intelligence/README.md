# MARG – Mentor Intelligence Engine

A planning and coordination engine for education mentors and Cluster Resource Persons (CRPs). It prioritises tasks, plans days and weeks, analyses workload and schedules, tracks teacher follow-ups, plans school visits, drafts teacher messages (English/Tamil) and produces activity reports.

- **Deterministic Python** calculates priorities, deadlines, workload, conflicts and status, using only verified inputs. Missing inputs are reported, never assumed.
- **NVIDIA-hosted model** (one configurable model) explains, summarises and drafts. Its output is schema-validated, labelled as AI-generated, and never changes a calculated value. Anthropic and OpenRouter remain optional providers.
- **Human approval** is required for every consequential action. The engine never sends messages to teachers.

> **Prototype status:** working end-to-end with **DEMO DATA**. Integration with the main MARG backend is pending its OpenAPI compatibility audit. Identity headers are development-only. Not production-ready. See [docs/PROTOTYPE_STATUS.md](docs/PROTOTYPE_STATUS.md).

## Quick start (Windows PowerShell)

```powershell
cd D:\AI-MARG\MARG-Mentor-Intelligence
uv sync                                   # install dependencies (Python 3.12 venv)
Copy-Item .env.example .env               # then edit .env (see below)
```

Edit `.env` and set `NVIDIA_API_KEY`, `NVIDIA_MODEL`, `PSEUDONYMISATION_KEY` and `DB_PASSWORD`. Keep the NVIDIA key only in this server-side environment file. The default model ID is `nvidia/nemotron-3.5-lightning-30b-a3b`; verify the live model response with your own education and Tamil-language test prompts before relying on it.

### Option A: PostgreSQL (`marg_mentor_intelligence`, schema `mie`)

One-time setup of the application role and schemas (as the postgres superuser; touches no other database):

```powershell
& "D:\postgre\bin\psql.exe" -U postgres -h localhost -p 5432 -d marg_mentor_intelligence -f scripts\setup_db_role.sql
& "D:\postgre\bin\psql.exe" -U postgres -h localhost -p 5432 -d marg_mentor_intelligence -c "\password marg_mie_app"
```

Put the password you chose into `DB_PASSWORD` in `.env`. Then:

```powershell
uv run python scripts\verify_db.py        # guard check: database/schema/user (no secrets printed)
uv run alembic upgrade head               # create tables in schema mie
uv run python scripts\seed_demo.py        # load DEMO DATA (re-run on the demo day for current dates)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8002
```

### Option B: local SQLite fallback (no PostgreSQL needed)

```powershell
$env:DB_BACKEND = "sqlite"
uv run python scripts\seed_demo.py
uv run uvicorn app.main:app --host 127.0.0.1 --port 8002
```

### Use it
- Interactive API docs: http://127.0.0.1:8002/docs
- Full demonstration (in a second PowerShell window): `powershell -ExecutionPolicy Bypass -File .\scripts\demo.ps1`
- Integrated calls are proxied by the MARG backend; standalone development calls use the identity header `X-Actor-Ref: MEN-001`.

## Tests

```powershell
uv run pytest                              # unit, API, orchestration, approvals, mocked providers (no network)
uv run pytest -m postgres                  # PostgreSQL tests in schema mie_test (needs Option A setup)
$env:RUN_LIVE_LLM_TESTS="1"; uv run pytest -m live_llm; Remove-Item Env:RUN_LIVE_LLM_TESTS   # real NVIDIA inference (may incur cost)
uv run ruff check app tests
```

## Documentation
- [Prototype status: completed / partial / deferred](docs/PROTOTYPE_STATUS.md)
- [API reference and demo walkthrough](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md) · [Agent design](docs/AGENT_DESIGN.md) · [Technical decisions](docs/TECHNICAL_DECISIONS.md) · [Roadmap](docs/DEVELOPMENT_ROADMAP.md)

## Boundaries
- No Classroom Intelligence functionality (RAG, pedagogy analysis, teacher chatbot). Observation records are operational context only.
- No changes to, or connections with, the MARG backend or the `marg_db` database. A guard refuses forbidden database names.
- No external messages are ever sent. Drafts require mentor approval, and delivery is the MARG application's job.

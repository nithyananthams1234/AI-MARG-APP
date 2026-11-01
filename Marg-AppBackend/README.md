# MARG Backend

Initial project foundation for MARG, following the supplied MARG Master System Contract.

## Requirements
- Python 3.12+
- PostgreSQL 16+ (with pgvector available when the knowledge module is introduced)

## Windows setup
```powershell
cd D:\
mkdir Marg-AppBackend
# Extract this starter archive into D:\Marg-AppBackend
cd D:\Marg-AppBackend

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Open:
- API health: http://127.0.0.1:8000/health
- OpenAPI UI: http://127.0.0.1:8000/docs

## Important
This is Stage 1 only: application foundation and configuration. It does not yet create business tables,
authentication, or production endpoints. Those will be added in controlled stages with Alembic migrations
and tests. Never commit `.env` or real credentials.

## Contract
- API prefix: `/api/v1`
- PostgreSQL is the authoritative server database.
- SQLite remains the mobile app's local offline database; the backend does not replace it.
- Standard API success/error envelopes will be used by business endpoints.
- Canonical entity names and statuses are defined by the MARG Master System Contract.

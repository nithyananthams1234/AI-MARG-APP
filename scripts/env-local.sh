#!/usr/bin/env bash
# Loads local integration settings for running all MARG services on one machine.
# Secrets come from .scratch/local-integration.env and each service's own .env;
# nothing is printed.
ROOT="/d/AI-MARG"
set -a; . "$ROOT/.scratch/local-integration.env"; set +a
mi_engine_key="$(cd "$ROOT/MARG-Mentor-Intelligence" && .venv/Scripts/python.exe -c 'from app.config import Settings; k=Settings().engine_api_key; print(k.get_secret_value() if k else "")')"

# Backend (port 8000, demo database)
export BACKEND_DATABASE_URL="$("$ROOT/Marg-AppBackend/.venv/Scripts/python.exe" "$ROOT/scripts/dburl.py" marg_demo)"
export MENTOR_INTELLIGENCE_URL="http://127.0.0.1:8002"
export MENTOR_INTELLIGENCE_API_KEY="$mi_engine_key"
export MENTOR_INTELLIGENCE_SERVICE_KEY="$MI_SERVICE_KEY"
export CLASSROOM_COACH_URL="http://127.0.0.1:8001"
export CLASSROOM_COACH_API_KEY="$COACH_API_KEY"
export CORS_ORIGINS="http://localhost:8081,http://localhost:19006,http://localhost:8082"

"""Engine API key authentication: server checks, configuration parsing and the demo script.

All keys here are fake test values. Real keys are never used or printed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.config import ENV_FILE, PROJECT_ROOT, Settings
from app.db.session import Database
from app.dependencies import Container
from app.main import create_app
from app.seed.demo_data import demo_anchor_date, seed_demo_data
from tests.conftest import HEADERS, build_container, make_settings

TEST_KEY = "test-engine-key-7f3a9c2e5b1d"
WRONG_KEY = "wrong-engine-key-000000000"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
SCRIPTS = PROJECT_ROOT / "scripts"


# ----------------------------------------------------------------------------- server-side checks
@pytest.fixture
async def keyed_client(db):
    c = build_container(make_settings(engine_api_key=TEST_KEY), db)
    app = create_app(c)
    app.state.container = c
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        yield client


async def test_correct_key_accepted(keyed_client):
    r = await keyed_client.get("/api/v1/mentors", headers=HEADERS | {"X-API-Key": TEST_KEY})
    assert r.status_code == 200
    r = await keyed_client.post(
        "/api/v1/tasks/prioritise", json={"mentor_ref": "MEN-001"}, headers=HEADERS | {"X-API-Key": TEST_KEY}
    )
    assert r.status_code == 200 and r.json()["success"]


async def test_missing_key_rejected(keyed_client):
    r = await keyed_client.get("/api/v1/mentors", headers=HEADERS)
    assert r.status_code == 401
    assert r.json()["error"] == {"code": "http_error", "message": "Invalid or missing API key"}


@pytest.mark.parametrize("supplied", [WRONG_KEY, "", "   ", TEST_KEY[:-1], TEST_KEY.upper()])
async def test_incorrect_key_rejected(keyed_client, supplied):
    r = await keyed_client.get("/api/v1/mentors", headers=HEADERS | {"X-API-Key": supplied})
    assert r.status_code == 401


async def test_no_secret_in_error_responses_or_logs(keyed_client, caplog):
    caplog.set_level(logging.DEBUG)
    r = await keyed_client.get("/api/v1/mentors", headers=HEADERS | {"X-API-Key": WRONG_KEY})
    ready = await keyed_client.get("/health/ready")
    for text in (r.text, ready.text, caplog.text):
        assert TEST_KEY not in text
        assert WRONG_KEY not in text
    assert ready.json()["checks"]["configuration"]["engine_api_key"] == "configured"


# ----------------------------------------------------------------------------- configuration
@pytest.fixture
def no_env_key(monkeypatch):
    monkeypatch.delenv("ENGINE_API_KEY", raising=False)


@pytest.mark.parametrize(
    "line",
    [
        "ENGINE_API_KEY=",
        "ENGINE_API_KEY=   ",
        "ENGINE_API_KEY=                     # optional: if set, /api/v1 requires header X-API-Key",
    ],
)
def test_empty_key_in_env_file_fails_closed(tmp_path, no_env_key, line):
    env = tmp_path / ".env"
    env.write_text(f"APP_ENV=test\nAI_ENABLED=false\n{line}\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="ENGINE_API_KEY is present but empty") as info:
        Settings(_env_file=env)
    assert "optional" not in str(info.value)  # the raw value is not echoed


@pytest.mark.parametrize(
    "line",
    [
        f"ENGINE_API_KEY={TEST_KEY}",
        f"ENGINE_API_KEY={TEST_KEY}   # trailing comment",
        f'ENGINE_API_KEY="{TEST_KEY}"',
        f"ENGINE_API_KEY='{TEST_KEY}'",
        f"ENGINE_API_KEY=  {TEST_KEY}  ",
    ],
)
def test_key_parsed_from_env_file(tmp_path, no_env_key, line):
    env = tmp_path / ".env"
    env.write_bytes(f"APP_ENV=test\r\nAI_ENABLED=false\r\n{line}\r\n".encode("utf-8-sig"))  # BOM + CRLF
    assert Settings(_env_file=env).engine_api_key.get_secret_value() == TEST_KEY


def test_absent_key_means_not_configured(tmp_path, no_env_key):
    env = tmp_path / ".env"
    env.write_text("APP_ENV=test\nAI_ENABLED=false\n# ENGINE_API_KEY=\n", encoding="utf-8")
    assert Settings(_env_file=env).engine_api_key is None


def test_environment_variable_overrides_env_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(f"APP_ENV=test\nAI_ENABLED=false\nENGINE_API_KEY={WRONG_KEY}\n", encoding="utf-8")
    monkeypatch.setenv("ENGINE_API_KEY", TEST_KEY)
    assert Settings(_env_file=env).engine_api_key.get_secret_value() == TEST_KEY


def test_env_file_is_anchored_to_project_root():
    assert ENV_FILE == PROJECT_ROOT / ".env"
    assert Path(Settings.model_config["env_file"]) == ENV_FILE


# ----------------------------------------------------------------------------- demo script (PowerShell)
needs_powershell = pytest.mark.skipif(POWERSHELL is None, reason="PowerShell not available")


def _ps(command: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "ENGINE_API_KEY"}
    env.update(extra_env or {})
    return subprocess.run(  # noqa: S603
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )


def _resolve(env_file: Path, explicit: str = "", extra_env: dict[str, str] | None = None) -> dict:
    lib = SCRIPTS / "lib" / "DemoAuth.ps1"
    cmd = (
        f". '{lib}'; $a = Resolve-EngineApiKey -ExplicitKey '{explicit}' -EnvFile '{env_file}'; "
        "$h = New-DemoHeaders -ActorRef 'MEN-001' -ApiKey $a.Key; "
        "@{ source = $a.Source; header = $h['X-API-Key']; actor = $h['X-Actor-Ref'] } | ConvertTo-Json -Compress"
    )
    result = _ps(cmd, extra_env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip())


@needs_powershell
@pytest.mark.parametrize(
    "content,encoding",
    [
        (f"ENGINE_API_KEY={TEST_KEY}\n", "utf-8"),
        (f"APP_ENV=development\r\nENGINE_API_KEY={TEST_KEY}   # comment\r\n", "utf-8-sig"),
        (f'export ENGINE_API_KEY="{TEST_KEY}"\n', "utf-8"),
        (f"# ENGINE_API_KEY=old\nENGINE_API_KEY=  '{TEST_KEY}'  \n", "utf-8"),
    ],
)
def test_demo_reads_key_from_env_file(tmp_path, content, encoding):
    env = tmp_path / ".env"
    env.write_bytes(content.encode(encoding))
    out = _resolve(env)
    assert out == {"source": ".env file", "header": TEST_KEY, "actor": "MEN-001"}


@needs_powershell
def test_demo_sends_no_key_when_env_file_has_only_a_comment(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ENGINE_API_KEY=                     # optional: if set, /api/v1 requires header\n")
    out = _resolve(env)
    assert out["source"] == "none configured" and out["header"] is None


@needs_powershell
def test_demo_key_precedence(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"ENGINE_API_KEY={WRONG_KEY}\n")
    assert _resolve(env, explicit=TEST_KEY)["source"] == "-ApiKey parameter"
    out = _resolve(env, extra_env={"ENGINE_API_KEY": TEST_KEY})
    assert out == {"source": "ENGINE_API_KEY environment variable", "header": TEST_KEY, "actor": "MEN-001"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_server(tmp_path):
    """Real HTTP server (uvicorn in a thread) with API key auth and seeded DEMO DATA."""
    import uvicorn

    db_url = f"sqlite+aiosqlite:///{(tmp_path / 'demo.sqlite3').as_posix()}"

    async def prepare():
        seed_db = Database.sqlite(db_url)
        await seed_db.create_all()
        from app.utils.datetime_utils import local_date, utcnow

        await seed_demo_data(seed_db, demo_anchor_date(local_date(utcnow(), make_settings().tz)))
        await seed_db.dispose()

    asyncio.run(prepare())
    # Real clock (not the fixed test clock): demo data is seeded relative to today.
    container = Container.build(make_settings(engine_api_key=TEST_KEY), db=Database.sqlite(db_url))
    app = create_app(container)
    app.state.container = container
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@needs_powershell
def test_demo_script_end_to_end_with_key_from_env_file(tmp_path, live_server):
    env = tmp_path / "project.env"
    env.write_text(f"APP_ENV=development\nENGINE_API_KEY={TEST_KEY}   # demo key\n", encoding="utf-8")
    result = _ps(f"& '{SCRIPTS / 'demo.ps1'}' -BaseUrl '{live_server}' -EnvFile '{env}'")
    output = result.stdout + result.stderr
    assert result.returncode == 0, output[-3000:]
    assert "API key: sent in X-API-Key (source: .env file)" in output
    assert "Demo complete" in output
    assert TEST_KEY not in output


@needs_powershell
def test_demo_script_reports_wrong_key_without_revealing_it(tmp_path, live_server):
    env = tmp_path / "project.env"
    env.write_text(f"ENGINE_API_KEY={WRONG_KEY}\n", encoding="utf-8")
    result = _ps(f"& '{SCRIPTS / 'demo.ps1'}' -BaseUrl '{live_server}' -EnvFile '{env}'")
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "HTTP 401" in output and "restart the server" in output
    assert WRONG_KEY not in output and TEST_KEY not in output

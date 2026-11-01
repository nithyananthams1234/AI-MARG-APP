"""Trusted-gateway identity: the MARG backend asserts the mentor identity.

Identity headers are only honoured together with a valid ENGINE_API_KEY; with
dev headers disabled (production-like), requests without the key fail closed.
"""

from __future__ import annotations

import httpx
import pytest

from app.main import create_app
from tests.conftest import build_container, make_settings

KEY = "gateway-engine-key-1a2b3c4d5e"


@pytest.fixture
async def gateway_client(db):
    c = build_container(
        make_settings(engine_api_key=KEY, dev_auth_header_enabled=False, trusted_gateway_identity=True), db
    )
    app = create_app(c)
    app.state.container = c
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        yield client


async def test_gateway_identity_with_key_is_accepted(gateway_client):
    r = await gateway_client.post(
        "/api/v1/tasks/prioritise",
        json={"mentor_ref": "MEN-001", "use_ai": False},
        headers={"X-API-Key": KEY, "X-Actor-Ref": "MEN-001"},
    )
    assert r.status_code == 200, r.text


async def test_gateway_identity_without_key_is_rejected(gateway_client):
    r = await gateway_client.post(
        "/api/v1/tasks/prioritise", json={"mentor_ref": "MEN-001"}, headers={"X-Actor-Ref": "MEN-001"}
    )
    assert r.status_code == 401


async def test_gateway_cannot_act_for_another_mentor(gateway_client):
    r = await gateway_client.post(
        "/api/v1/tasks/prioritise",
        json={"mentor_ref": "MEN-002", "use_ai": False},
        headers={"X-API-Key": KEY, "X-Actor-Ref": "MEN-001"},
    )
    assert r.status_code == 403


async def test_production_like_without_gateway_fails_closed(db):
    c = build_container(make_settings(engine_api_key=KEY, dev_auth_header_enabled=False), db)
    app = create_app(c)
    app.state.container = c
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/api/v1/mentors", headers={"X-API-Key": KEY, "X-Actor-Ref": "MEN-001"})
    assert r.status_code == 401

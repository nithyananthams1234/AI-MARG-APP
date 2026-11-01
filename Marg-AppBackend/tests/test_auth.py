import pytest

from tests.conftest import PASSWORD, auth_headers, login

pytestmark = pytest.mark.anyio


async def test_login_success_returns_access_and_refresh(world, client):
    tokens = await login(client, "mentor.a@test.marg")
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["expires_in"] > 0 and tokens["refresh_expires_in"] > 0


async def test_login_wrong_password_and_unknown_email_are_indistinguishable(world, client):
    r1 = await client.post("/api/v1/auth/login", data={"username": "mentor.a@test.marg", "password": "wrong-password"})
    r2 = await client.post("/api/v1/auth/login", data={"username": "nobody@test.marg", "password": "wrong-password"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


async def test_login_email_is_case_insensitive(world, client):
    await login(client, "MENTOR.A@test.marg")


async def test_user_without_login_role_cannot_log_in(world, client):
    r = await client.post("/api/v1/auth/login", data={"username": "sup@test.marg", "password": PASSWORD})
    assert r.status_code == 401


async def test_me_returns_only_assigned_schools(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    r = await client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "mentor.a@test.marg"
    assert body["role"] == "Mentor"
    assert [s["code"] for s in body["assigned_schools"]] == ["TSA"]


async def test_protected_endpoint_requires_token(world, client):
    assert (await client.get("/api/v1/schools/")).status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert (await client.get("/api/v1/schools/", headers=bad)).status_code == 401


async def test_admin_cannot_use_mentor_endpoints(world, client):
    h = await auth_headers(client, "admin@test.marg")
    assert (await client.get("/api/v1/school-visits/", headers=h)).status_code == 403


async def test_refresh_rotates_and_reuse_revokes_family(world, client):
    first = await login(client, "mentor.a@test.marg")

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]

    # New access token works.
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"})
    assert me.status_code == 200

    # Re-using the rotated token is rejected and revokes the whole family...
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401
    # ...so the legitimately rotated token no longer works either.
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert after.status_code == 401


async def test_logout_revokes_refresh_token(world, client):
    tokens = await login(client, "mentor.a@test.marg")
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    r = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=h)
    assert r.status_code == 204
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


async def test_login_rate_limited(world, client):
    for _ in range(10):
        r = await client.post("/api/v1/auth/login", data={"username": "mentor.a@test.marg", "password": "nope"})
        assert r.status_code == 401
    r = await client.post("/api/v1/auth/login", data={"username": "mentor.a@test.marg", "password": PASSWORD})
    assert r.status_code == 429
    assert "Retry-After" in r.headers

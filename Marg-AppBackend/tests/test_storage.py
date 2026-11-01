"""Evidence storage: content validation, S3 backend path, production config guards."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.storage import service as storage
from tests.conftest import auth_headers

pytestmark = pytest.mark.anyio

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


async def _observation(client, h, world):
    v = await client.post(
        "/api/v1/school-visits/",
        json={"school_id": str(world["school_a"]), "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
        headers=h,
    )
    await client.patch(f"/api/v1/school-visits/{v.json()['id']}/status", json={"status": "in_progress"}, headers=h)
    o = await client.post(
        "/api/v1/observations/",
        json={"school_visit_id": v.json()["id"], "teacher_id": str(world["teacher_a"]),
              "classroom_id": str(world["class_a"]), "subject": "Science"},
        headers=h,
    )
    return o.json()["id"]


async def test_disguised_file_is_rejected(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    obs = await _observation(client, h, world)
    r = await client.post(
        "/api/v1/evidence/",
        data={"observation_id": obs},
        files={"file": ("photo.png", b"MZ\x90\x00 not really a png", "image/png")},
        headers=h,
    )
    assert r.status_code == 415
    r = await client.post(
        "/api/v1/evidence/",
        data={"observation_id": obs},
        files={"file": ("script.html", b"<script>alert(1)</script>", "text/html")},
        headers=h,
    )
    assert r.status_code == 415


async def test_other_mentor_cannot_download_evidence(world, client):
    h = await auth_headers(client, "mentor.a@test.marg")
    obs = await _observation(client, h, world)
    ev = await client.post(
        "/api/v1/evidence/", data={"observation_id": obs}, files={"file": ("a.png", PNG, "image/png")}, headers=h
    )
    assert ev.status_code == 201
    hb = await auth_headers(client, "mentor.b@test.marg")
    assert (await client.get(f"/api/v1/evidence/{ev.json()['id']}/download", headers=hb)).status_code == 404
    dl = await client.get(f"/api/v1/evidence/{ev.json()['id']}/download", headers=h)
    assert dl.status_code == 200 and dl.content == PNG
    assert dl.headers["x-content-type-options"] == "nosniff"


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def upload_fileobj(self, fileobj, bucket, key, extra):
        self.objects[key] = fileobj.read()

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        data = self.objects[Key]

        class Body:
            def iter_chunks(self, size):
                yield from (data[i:i + size] for i in range(0, len(data), size))

        return {"Body": Body()}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)


async def test_s3_backend_round_trip(world, client, monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(storage, "_s3", lambda: fake)
    h = await auth_headers(client, "mentor.a@test.marg")
    obs = await _observation(client, h, world)
    ev = await client.post(
        "/api/v1/evidence/", data={"observation_id": obs}, files={"file": ("a.png", PNG, "image/png")}, headers=h
    )
    assert ev.status_code == 201, ev.text
    assert len(fake.objects) == 1 and next(iter(fake.objects)).startswith("evidence/")
    dl = await client.get(f"/api/v1/evidence/{ev.json()['id']}/download", headers=h)
    assert dl.status_code == 200 and dl.content == PNG


def test_production_config_guards():
    base = dict(database_url="postgresql+asyncpg://u:p@h/db", jwt_secret_key="x" * 40, app_env="production",
                cors_origins="https://marg.example.org", _env_file=None)
    with pytest.raises(ValidationError, match="STORAGE_BACKEND"):
        Settings(**base, storage_backend="local")
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(**{**base, "jwt_secret_key": "short"}, storage_backend="s3")
    with pytest.raises(ValidationError, match="https"):
        Settings(**{**base, "cors_origins": "http://marg.example.org"}, storage_backend="s3")
    assert Settings(**base, storage_backend="s3").is_production


def test_storage_keys_cannot_traverse():
    for bad in ("../etc/passwd", "a/b", "", "abc.def"):
        with pytest.raises(ValueError):
            storage._valid_key(bad)

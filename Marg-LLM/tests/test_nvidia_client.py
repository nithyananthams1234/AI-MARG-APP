import json

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from app.config import settings
from app.llm import nvidia_client

pytestmark = pytest.mark.anyio


class Output(BaseModel):
    summary: str


@pytest.fixture
def mock_client(monkeypatch):
    requests = []
    client_type = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": settings.NVIDIA_MODEL}]})
        payload = json.loads(request.content)
        content = json.dumps({"summary": "validated"}) if "response_format" in payload else "validated"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
            },
        )

    monkeypatch.setattr(nvidia_client.httpx, "AsyncClient", lambda **kwargs: client_type(
        transport=httpx.MockTransport(handler), **kwargs
    ))
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", SecretStr("nvidia-test-key"))
    monkeypatch.setattr(settings, "NVIDIA_BASE_URL", "https://integrate.test/v1")
    monkeypatch.setattr(settings, "NVIDIA_MODEL", "nvidia/test-model")
    return requests


async def test_chat_uses_nvidia_api_and_secret_header(mock_client):
    assert await nvidia_client.generate_answer("Give one concise suggestion.") == "validated"
    request = mock_client[0]
    assert request.url == "https://integrate.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer nvidia-test-key"
    assert json.loads(request.content)["model"] == "nvidia/test-model"


async def test_chat_authorization_uses_current_configured_key(mock_client, monkeypatch):
    fake_key = "alternate-nvidia-test-key"
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", SecretStr(fake_key))

    await nvidia_client.generate_answer("Give one concise suggestion.")

    assert mock_client[-1].headers.get("Authorization") == f"Bearer {fake_key}"


async def test_structured_response_is_validated_and_model_readiness_works(mock_client):
    result = await nvidia_client.generate_structured("Return a summary.", Output)
    assert result == Output(summary="validated")
    assert json.loads(mock_client[0].content)["response_format"] == {"type": "json_object"}
    assert await nvidia_client.model_available()


async def test_missing_api_key_is_reported_without_request(monkeypatch):
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", None)
    with pytest.raises(nvidia_client.LLMUnavailable, match="not configured"):
        await nvidia_client.generate_answer("Test.")


async def test_truncated_chat_completion_is_rejected(monkeypatch):
    client_type = httpx.AsyncClient

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": "partial answer"},
                    }
                ],
            },
        )

    monkeypatch.setattr(
        nvidia_client.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", SecretStr("nvidia-test-key"))

    with pytest.raises(nvidia_client.LLMInvalidOutput, match="truncated"):
        await nvidia_client.generate_answer("Give one concise suggestion.")

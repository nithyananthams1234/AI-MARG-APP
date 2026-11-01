"""AI analysis provider dispatch.

Default provider is the MARG Classroom Coach (local educational LLM + RAG).
The original direct-OpenAI path is preserved and selectable with
AI_PROVIDER=openai. Both return a validated AIAnalysisResponse.
"""

import json

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.config import settings
from app.integrations import classroom_coach
from app.schemas.ai import AIAnalysisResponse


SYSTEM_PROMPT = """
You are the AI analysis assistant for MARG, an educational mentoring platform.

Analyze only the educational information supplied in the request.

Return a JSON object containing:
- summary
- findings
- learning_gaps
- recommendations

Rules:
1. Base every suggestion on the supplied information.
2. Do not invent classroom observations or evidence.
3. Keep suggestions practical and educationally relevant.
4. Clearly distinguish evidence from interpretation.
5. Do not make decisions on behalf of the mentor.
6. Never claim that a suggestion has been approved.
7. Return valid JSON matching the requested response structure.
"""


async def generate_ai_analysis(
    input_payload: dict,
) -> AIAnalysisResponse:
    provider = settings.ai_provider.lower()
    if provider == "classroom_coach":
        return await _classroom_coach_analysis(input_payload)
    if provider == "openai":
        return await _openai_analysis(input_payload)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Configured AI provider is not supported.",
    )


async def _classroom_coach_analysis(input_payload: dict) -> AIAnalysisResponse:
    request = {
        "subject": input_payload.get("subject") or "General",
        "grade": input_payload.get("grade"),
        "topic": input_payload.get("topic"),
        "observation_notes": input_payload.get("observation_notes") or "",
        "existing_findings": input_payload.get("existing_findings") or [],
    }
    try:
        data = await classroom_coach.analyze_observation(request)
    except classroom_coach.CoachError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc
    try:
        return AIAnalysisResponse.model_validate(
            {**data, "provider": "classroom_coach"}
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The Classroom Coach returned an invalid analysis.",
        ) from exc


async def _openai_analysis(input_payload: dict) -> AIAnalysisResponse:
    if not settings.ai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider API key is not configured.",
        )

    request_body = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(input_payload, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.ai_api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
            response.raise_for_status()
            provider_data = response.json()

        content = provider_data["choices"][0]["message"]["content"]
        if not content:
            raise ValueError("AI provider returned an empty response.")
        return AIAnalysisResponse.model_validate({**json.loads(content), "provider": "openai"})

    except httpx.TimeoutException:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="AI provider request timed out.")
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI provider request failed.")
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI provider returned an invalid response.")
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the AI provider.")

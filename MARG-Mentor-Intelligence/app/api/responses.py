from fastapi.responses import JSONResponse


class UTF8JSONResponse(JSONResponse):
    """Explicit charset so every client (including Windows PowerShell 5.1) decodes Tamil text correctly."""

    media_type = "application/json; charset=utf-8"

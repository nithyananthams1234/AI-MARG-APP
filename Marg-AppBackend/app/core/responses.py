from typing import Any
from uuid import UUID


def success_response(
    data: Any,
    message: str = "Operation successful",
    request_id: UUID | str | None = None,
) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "message": message,
        "request_id": str(request_id) if request_id else None,
    }


def error_response(
    code: str,
    message: str,
    details: Any = None,
    request_id: UUID | str | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
        },
        "request_id": str(request_id) if request_id else None,
    }

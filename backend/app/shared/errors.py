"""Consistent API error payload.

All error responses use the shape documented in architecture doc section 7::

    {
      "error": {
        "code": "TASK_NOT_FOUND",
        "message": "The requested task was not found.",
        "details": []
      }
    }
"""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """One field-level validation detail."""

    field: str | None = None
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ApiErrorPayload(BaseModel):
    error: ErrorBody


def error_payload(
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> dict[str, object]:
    """Build the JSON body for an API error response."""
    payload = ApiErrorPayload(error=ErrorBody(code=code, message=message, details=details or []))
    return payload.model_dump(mode="json")

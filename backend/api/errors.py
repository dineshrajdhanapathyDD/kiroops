"""Error envelope and exception handlers for the API layer (Task 7.3).

The API layer is the only place domain errors are mapped to HTTP status codes.
All error responses share the envelope from the coding-standards steering:

    {"error": {"code": str, "message": str, "field"?: str}}

Mapping (design.md error table):

    ValidationError (title/severity)      -> 422 (envelope includes ``field``)
    unknown status value / bad body shape -> 422 (Pydantic request validation)
    NotFoundError (unknown incident id)   -> 404
    InvalidTransitionError                -> 409 (status preserved; no write)
    DiagnosisUnavailableError             -> 503 (status preserved; no write)

Requirements: 1.6, 1.7, 2.3, 3.3, 3.4, 4.5, 7.4.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.service.errors import (
    DiagnosisUnavailableError,
    InvalidTransitionError,
    NotFoundError,
    ValidationError,
)


def _envelope(code: str, message: str, field: str | None = None) -> dict[str, Any]:
    """Build the shared error envelope, including ``field`` only when present."""
    error: dict[str, Any] = {"code": code, "message": message}
    if field is not None:
        error["field"] = field
    return {"error": error}


def _json(status_code: int, code: str, message: str, field: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_envelope(code, message, field),
    )


async def _handle_validation_error(
    _request: Request, exc: ValidationError
) -> JSONResponse:
    """Map a service ``ValidationError`` to 422 naming the field (Req 1.6, 1.7)."""
    return _json(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        exc.message,
        exc.field,
    )


async def _handle_not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
    """Map a ``NotFoundError`` to 404 (Req 2.3)."""
    return _json(status.HTTP_404_NOT_FOUND, "not_found", exc.message)


async def _handle_invalid_transition(
    _request: Request, exc: InvalidTransitionError
) -> JSONResponse:
    """Map an ``InvalidTransitionError`` to 409; status is preserved (Req 3.3, 7.4)."""
    return _json(status.HTTP_409_CONFLICT, "invalid_transition", exc.message)


async def _handle_diagnosis_unavailable(
    _request: Request, exc: DiagnosisUnavailableError
) -> JSONResponse:
    """Map a ``DiagnosisUnavailableError`` to 503; status is preserved (Req 4.5)."""
    return _json(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "diagnosis_unavailable",
        exc.message,
    )


async def _handle_request_validation(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map FastAPI/Pydantic body-shape errors to the shared 422 envelope.

    Covers an unknown ``severity`` on create and an unknown ``status`` value on a
    status update (Req 1.7, 3.4): the enum-typed request models reject these
    before any service call, so no state change occurs. The offending field name
    is surfaced in ``field`` when it can be derived from the error location.
    """
    field = _first_body_field(exc.errors())
    message = "Request validation failed."
    return _json(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        message,
        field,
    )


def _first_body_field(errors: list[Any]) -> str | None:
    """Return the first body field name from a Pydantic error list, if any."""
    for err in errors:
        loc = err.get("loc", ()) if isinstance(err, dict) else ()
        # loc is like ("body", "severity") for body field errors.
        if len(loc) >= 2 and loc[0] == "body":
            return str(loc[-1])
    return None


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain-error handlers on the app (Task 7.3)."""
    app.add_exception_handler(ValidationError, _handle_validation_error)
    app.add_exception_handler(NotFoundError, _handle_not_found)
    app.add_exception_handler(InvalidTransitionError, _handle_invalid_transition)
    app.add_exception_handler(
        DiagnosisUnavailableError, _handle_diagnosis_unavailable
    )
    app.add_exception_handler(RequestValidationError, _handle_request_validation)

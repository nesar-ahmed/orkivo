"""FastAPI application factory / ASGI entrypoint.

Run in development with::

    uv run uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.modules.tasks.exceptions import TaskNotFoundError
from app.shared.errors import ErrorDetail, error_payload

API_DOCS_VERSION = "0.1.0"

_STATUS_ERROR_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


def create_app() -> FastAPI:
    """Build the ASGI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=API_DOCS_VERSION,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    register_error_handlers(app)
    # Starlette/FastAPI answer unmatched paths with a built-in default that
    # bypasses exception handlers; override it to keep the error contract.
    app.router.default = _unmatched_route_response
    return app


async def _unmatched_route_response(_scope: Scope, _receive: Receive, send: Send) -> None:
    """404 for unmatched routes, in the consistent error shape."""
    response = JSONResponse(
        status_code=404,
        content=error_payload("NOT_FOUND", "The requested resource was not found."),
    )
    await response(_scope, _receive, send)


def register_error_handlers(app: FastAPI) -> None:
    """Map exceptions onto the documented consistent error shape."""

    @app.exception_handler(TaskNotFoundError)
    async def handle_task_not_found(_request: Request, exc: TaskNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=error_payload(exc.code, exc.message))

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        code = _STATUS_ERROR_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, str(exc.detail)),
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            ErrorDetail(
                field=".".join(str(part) for part in err["loc"][1:]) or None,
                message=str(err["msg"]),
            )
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_payload("VALIDATION_ERROR", "Request validation failed.", details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, _exc: Exception) -> JSONResponse:
        # Never leak internals to clients.
        return JSONResponse(
            status_code=500,
            content=error_payload("INTERNAL_ERROR", "An unexpected error occurred."),
        )


app = create_app()

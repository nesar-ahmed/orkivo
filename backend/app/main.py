"""FastAPI application factory / ASGI entrypoint.

Run in development with::

    uv run uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler, Receive, Scope, Send

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.modules.auth.csrf import CsrfMiddleware
from app.modules.auth.exceptions import (
    AccountDisabledError,
    AuthenticationError,
    AuthorizationError,
    SessionError,
)
from app.modules.tasks.exceptions import TaskConflictError, TaskNotFoundError
from app.modules.users.exceptions import (
    EmailAlreadyInUseError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.workspaces.exceptions import (
    AlreadyInvitedError,
    AlreadyMemberError,
    InviteNotPendingError,
    LastOwnerError,
    PersonalWorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceRoleNotAllowedError,
    WorkspaceSlugInUseError,
    WorkspaceSuspendedError,
)
from app.shared.errors import ErrorDetail, error_payload

API_DOCS_VERSION = "0.2.0"

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

# Domain exceptions and the status each one maps to. Handlers read ``code`` and
# ``message`` off the exception, so subclasses (``InvalidCredentialsError`` ->
# 401, ``CsrfCheckFailedError`` -> 403) inherit the right behaviour
# (architecture doc section 7).
_DOMAIN_ERROR_STATUS: dict[type[Exception], int] = {
    AuthenticationError: 401,
    SessionError: 401,
    AccountDisabledError: 401,
    AuthorizationError: 403,
    # Workspace tenancy. ``WorkspaceRoleNotAllowedError`` and
    # ``WorkspaceSuspendedError`` are 403 because the caller *is* in the tenant;
    # a caller who is not never reaches them, since membership failures answer
    # with the not-found shape (workspaces/service.py).
    WorkspaceRoleNotAllowedError: 403,
    WorkspaceSuspendedError: 403,
    WorkspaceNotFoundError: 404,
    TaskNotFoundError: 404,
    UserNotFoundError: 404,
    EmailAlreadyInUseError: 409,
    RoleChangeNotAllowedError: 409,
    TaskConflictError: 409,
    WorkspaceSlugInUseError: 409,
    AlreadyMemberError: 409,
    AlreadyInvitedError: 409,
    InviteNotPendingError: 409,
    LastOwnerError: 409,
    PersonalWorkspaceError: 409,
}


def create_app() -> FastAPI:
    """Build the ASGI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=API_DOCS_VERSION,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )
    # Added before CORS so that CORS stays the outermost layer: rejected
    # requests must still carry the headers a browser needs to read the error.
    app.add_middleware(CsrfMiddleware)
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

    def _domain_handler(status_code: int) -> ExceptionHandler:
        async def handler(_request: Request, exc: Exception) -> JSONResponse:
            code = getattr(exc, "code", "INTERNAL_ERROR")
            message = getattr(exc, "message", "An unexpected error occurred.")
            return JSONResponse(status_code=status_code, content=error_payload(code, message))

        return handler

    for exception_type, status_code in _DOMAIN_ERROR_STATUS.items():
        app.add_exception_handler(exception_type, _domain_handler(status_code))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Registered against Starlette's class, not ``fastapi.HTTPException``:
        # routing failures such as 405 are raised with the parent type, and a
        # handler on the subclass would leave them answering in the framework's
        # default ``{"detail": ...}`` shape. FastAPI's exception derives from
        # this one, so both come through here (architecture doc section 7).
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

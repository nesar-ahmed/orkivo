"""CSRF guard for cookie-authenticated state changes.

The session model is documented in ``app.modules.auth.cookies``: credentials
travel in ``SameSite=Lax`` httpOnly cookies. Lax already keeps them off
cross-site subrequests; this middleware is the deliberate second layer. Any
request that both presents a session cookie and mutates state must also carry
``X-Orkivo-Request: 1``. A cross-site attacker can trick a browser into sending
cookies (a form POST, say) but cannot set a custom header without passing a CORS
preflight it does not control, and cannot read the reply.

Requests authenticated with ``Authorization: Bearer`` are exempt: a browser
never attaches that header on its own, so there is no ambient authority to
abuse.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.modules.auth import cookies
from app.modules.auth.exceptions import CsrfCheckFailedError
from app.shared.errors import error_payload


class CsrfMiddleware:
    """Pure ASGI middleware so CORS stays the outermost layer."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if cookies.csrf_check_required(request) and not cookies.has_csrf_header(request):
            rejection = JSONResponse(
                status_code=403,
                content=error_payload("CSRF_CHECK_FAILED", CsrfCheckFailedError.message),
            )
            await rejection(scope, receive, send)
            return

        await self.app(scope, receive, send)

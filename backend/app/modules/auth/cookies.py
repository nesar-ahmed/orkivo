"""Session cookie transport (architecture doc section 9).

Chosen deployment model, as required by the doc ("document the chosen approach
and CSRF protections"):

* ``orkivo_access`` --- short-lived access JWT in an ``HttpOnly`` cookie scoped
  to the API prefix. JavaScript cannot read it, so an XSS bug in the dashboard
  does not hand over the credential.
* ``orkivo_refresh`` --- opaque refresh token in an ``HttpOnly`` cookie scoped
  to ``<api prefix>/auth`` only, so it travels to the smallest set of routes.
* Neither token is ever returned in a response body.

CSRF: ``SameSite=Lax`` stops cross-site requests from attaching these cookies,
and every cookie-authenticated state change must additionally carry the
``X-Orkivo-Request`` header, which a cross-site form or fetch cannot send
without a CORS preflight the attacker does not control. That guard is
``app.api.v1.deps.csrf_guard``.

Cookie names are host-only by default (``Settings.cookie_domain`` is ``None``),
so the API origin must match the origin the browser uses --- see the README
quickstart: the frontend must call the API at ``localhost`` (not ``127.0.0.1``)
while served from ``localhost:3000``, or the cookies will not be shared.
"""

from datetime import datetime

from fastapi import Request, Response

from app.core.config import get_settings
from app.shared.time import utc_now

ACCESS_COOKIE_NAME = "orkivo_access"
REFRESH_COOKIE_NAME = "orkivo_refresh"
CSRF_HEADER_NAME = "X-Orkivo-Request"
CSRF_HEADER_VALUE = "1"

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_SECONDS_PER_DAY = 86_400


def refresh_cookie_path() -> str:
    """The narrowest path the refresh cookie is sent to."""
    return f"{get_settings().api_v1_prefix}/auth"


def access_cookie_path() -> str:
    """Site-wide, not API-scoped --- and that is deliberate.

    Server components read through the Next.js origin and forward the incoming
    ``Cookie`` header, so the access credential must also be attached to
    requests for the app host. A ``Path=/api/v1`` cookie would only ever reach
    the API port directly, and the server-rendered dashboard would look signed
    out. The refresh token keeps the narrow path because only the browser's
    auth calls need it.
    """
    return "/"


def set_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    access_expires_at: datetime,
) -> None:
    """Attach both session cookies to ``response``."""
    settings = get_settings()
    access_max_age = max(int((access_expires_at - utc_now()).total_seconds()), 1)

    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        max_age=access_max_age,
        path=access_cookie_path(),
        domain=settings.cookie_domain,
        secure=settings.use_secure_cookies,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=settings.refresh_token_ttl_days * _SECONDS_PER_DAY,
        path=refresh_cookie_path(),
        domain=settings.cookie_domain,
        secure=settings.use_secure_cookies,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookies(response: Response) -> None:
    """Expire both cookies. Deletion must match the original name and path."""
    settings = get_settings()
    for name, path in (
        (ACCESS_COOKIE_NAME, access_cookie_path()),
        (REFRESH_COOKIE_NAME, refresh_cookie_path()),
    ):
        response.delete_cookie(
            name,
            path=path,
            domain=settings.cookie_domain,
            secure=settings.use_secure_cookies,
            httponly=True,
            samesite="lax",
        )


def read_access_token(request: Request) -> str | None:
    """Cookie first, then an ``Authorization: Bearer`` header (CLI and tests)."""
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if token:
        return token
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


def read_refresh_token(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE_NAME)


def uses_session_cookie(request: Request) -> bool:
    """Whether the request presents either session cookie."""
    return bool(request.cookies.get(ACCESS_COOKIE_NAME) or request.cookies.get(REFRESH_COOKIE_NAME))


def csrf_check_required(request: Request) -> bool:
    """Only unsafe, cookie-authenticated requests need the CSRF header."""
    if request.method in _SAFE_METHODS:
        return False
    return uses_session_cookie(request)


def has_csrf_header(request: Request) -> bool:
    return request.headers.get(CSRF_HEADER_NAME) == CSRF_HEADER_VALUE

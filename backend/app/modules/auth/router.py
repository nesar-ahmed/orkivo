"""HTTP routes for authentication: register, login, refresh, logout.

Routes parse/validate input, call the application service, and serialize
output. Token material is only ever written to httpOnly cookies, never to a
response body (architecture doc sections 4.1, 7.1 and 9).
"""

from fastapi import APIRouter, Request, Response, status

from app.modules.auth import cookies
from app.modules.auth.dependencies import AuthServiceDep
from app.modules.auth.exceptions import SessionError
from app.modules.auth.schemas import LoginRequest, RegisterRequest, SessionResponse
from app.modules.auth.service import IssuedSession
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _respond_with_session(response: Response, issued: IssuedSession) -> SessionResponse:
    """Set both cookies and return the public (token-free) body."""
    cookies.set_session_cookies(
        response,
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        access_expires_at=issued.access_expires_at,
    )
    return SessionResponse(
        user=UserRead.model_validate(issued.user),
        session_id=issued.session_id,
        access_token_expires_at=issued.access_expires_at,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, service: AuthServiceDep) -> UserRead:
    """Create an account. The client signs in afterwards to start a session."""
    return UserRead.model_validate(service.register(payload))


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, response: Response, service: AuthServiceDep) -> SessionResponse:
    """Start a new session family for the credentials presented."""
    return _respond_with_session(response, service.login(payload))


@router.post("/refresh", response_model=SessionResponse)
def refresh(request: Request, response: Response, service: AuthServiceDep) -> SessionResponse:
    """Rotate the refresh session carried by the cookie and reissue access."""
    presented = cookies.read_refresh_token(request)
    if presented is None:
        raise SessionError
    return _respond_with_session(response, service.refresh(presented))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def logout(request: Request, service: AuthServiceDep) -> Response:
    """Revoke the presented session and expire both cookies.

    Always succeeds from the client's point of view: an unknown or already
    revoked session still results in cleared cookies.
    """
    service.logout(
        refresh_token=cookies.read_refresh_token(request),
        access_token=cookies.read_access_token(request),
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    cookies.clear_session_cookies(response)
    return response

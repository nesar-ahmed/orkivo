"""Request-level authentication and authorization dependencies.

This is the public interface other modules use to ask "who is asking?" and "may
they do this?". Authorization is decided here and in application services, never
in repositories (architecture doc sections 4.1 and 9).
"""

from typing import Annotated

from fastapi import Depends, Request

from app.api.v1.deps import DbSession
from app.modules.auth import cookies
from app.modules.auth.exceptions import AuthenticationError, AuthorizationError
from app.modules.auth.service import AuthService
from app.modules.users.enums import PlatformRole
from app.modules.users.models import User


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_current_user(request: Request, service: AuthServiceDep) -> User:
    """Resolve the request's access token to a live user row.

    Raises ``AuthenticationError`` when no credential is presented and
    ``SessionError`` when the credential's session has been rotated or revoked.
    """
    token = cookies.read_access_token(request)
    if token is None:
        raise AuthenticationError
    return service.authenticate_access_token(token)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_operator(user: CurrentUser) -> User:
    """Platform-console access. The role comes from the database, not the token.

    This guards the operator surface only. It is *not* how a company is accessed:
    that is ``workspaces`` membership, checked per tenant, and an operator sees
    tenant metadata rather than tenant content (architecture doc section 9).
    """
    if user.platform_role is not PlatformRole.OPERATOR:
        raise AuthorizationError
    return user


OperatorUser = Annotated[User, Depends(require_operator)]

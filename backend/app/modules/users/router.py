"""HTTP routes for user profiles and platform account administration.

Every route here is protected: ``/users/me`` requires a live session, the
account directory and platform-role routes require the operator role. Backend
authorization is authoritative --- hiding these routes in the UI is a
convenience, not a control (architecture doc sections 8.2 and 9).

Note what this module does *not* do: it grants no company access. Authority
inside a tenant comes only from ``/workspaces`` membership, so an operator of the
platform is not an admin of anyone's company (architecture doc section 5).
"""

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.auth.dependencies import CurrentUser, OperatorUser
from app.modules.users.dependencies import UserServiceDep
from app.modules.users.schemas import (
    PlatformRoleUpdate,
    UserListResponse,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_own_profile(user: CurrentUser) -> UserRead:
    """The authenticated account, read from the database on every request."""
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
def update_own_profile(payload: UserUpdate, user: CurrentUser, service: UserServiceDep) -> UserRead:
    """Update the caller's own profile. Other accounts are not reachable here."""
    return UserRead.model_validate(service.update_profile(user.id, payload))


@router.get("", response_model=UserListResponse)
def list_accounts(
    actor: OperatorUser,
    service: UserServiceDep,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserListResponse:
    """Operator-only account directory with ``search`` over email/display name."""
    items, total = service.list_users(search=search, page=page, page_size=page_size)
    return UserListResponse(
        items=[UserRead.model_validate(user) for user in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page, page_size),
    )


@router.patch("/{user_id}/platform-role", response_model=UserRead)
def update_platform_role(
    user_id: uuid.UUID,
    payload: PlatformRoleUpdate,
    actor: OperatorUser,
    service: UserServiceDep,
) -> UserRead:
    """Promote or demote a *platform* role. Operators cannot change their own.

    The path is spelled out rather than left as ``/role`` because there are two
    role axes in this product, and an ambiguous name is how someone confuses a
    platform operator with a company admin.
    """
    return UserRead.model_validate(
        service.update_platform_role(user_id, platform_role=payload.platform_role, actor=actor)
    )


def _pages(total: int, page: int, page_size: int) -> int:
    """Page count for the collection envelope."""
    return math.ceil(total / page_size) if total else 0

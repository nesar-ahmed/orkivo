"""Application service implementing user profile and account use cases.

Business rules live here, not in route handlers. Transaction boundaries are
committed at this use-case layer and rolled back on failure
(architecture doc section 6.2).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.users import repository
from app.modules.users.enums import PlatformRole
from app.modules.users.exceptions import (
    AccountStatusChangeNotAllowedError,
    EmailAlreadyInUseError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.users.models import User
from app.modules.users.schemas import UserUpdate
from app.shared.time import utc_now


def normalize_email(email: str) -> str:
    """Emails are matched case-insensitively, so the normalized form is stored."""
    return email.strip().lower()


class UserService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        platform_role: PlatformRole = PlatformRole.USER,
    ) -> User:
        """Persist a new account and commit it. Email uniqueness is a DB invariant."""
        user = self.prepare_user(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            platform_role=platform_role,
        )
        self._commit()
        return user

    def prepare_user(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        platform_role: PlatformRole = PlatformRole.USER,
    ) -> User:
        """Add the account to the session **without** committing.

        Registration is one transaction: the account and the personal workspace
        that must never be missing from it commit together, with the use-case
        boundary held by ``AuthService.register`` (architecture doc section 6.2).
        """
        user = User(
            email=normalize_email(email),
            display_name=display_name,
            password_hash=password_hash,
            platform_role=platform_role,
        )
        # The flush makes a concurrent claim of the same address surface here,
        # before the caller's commit. A violation is rolled back by this service:
        # the only unique constraint on the table is the address
        # (architecture doc section 6.2).
        try:
            repository.add_user(self._session, user)
        except IntegrityError:
            self._session.rollback()
            raise EmailAlreadyInUseError from None
        return user

    def get_user(self, user_id: uuid.UUID) -> User:
        user = repository.get_user(self._session, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    def get_user_by_email(self, email: str) -> User | None:
        return repository.get_user_by_email(self._session, normalize_email(email))

    def list_users(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[User], int]:
        return repository.list_users(
            self._session,
            search=search,
            page=page,
            page_size=page_size,
        )

    def update_profile(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        user = self.get_user(user_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in changes.items():
            setattr(user, field, value)
        self._session.flush()
        self._commit()
        return user

    def update_platform_role(
        self, user_id: uuid.UUID, *, platform_role: PlatformRole, actor: User
    ) -> User:
        """Change an account's *platform* role. Operators may not change their own.

        This column decides nothing about companies: an operator who promotes
        someone is making them a platform operator, not a tenant admin
        (architecture doc section 9).
        """
        if actor.id == user_id:
            raise RoleChangeNotAllowedError
        user = self.get_user(user_id)
        user.platform_role = platform_role
        self._session.flush()
        self._commit()
        return user

    def set_disabled(
        self,
        user_id: uuid.UUID,
        *,
        disabled: bool,
        reason: str | None,
        actor: User,
        commit: bool = True,
    ) -> User:
        """Stop or restore an account. Operators may not change their own.

        ``commit=False`` lets ``AuthService`` end the account's sessions in the
        same transaction, so a disabled account never keeps a live session.
        Re-enabling clears the reason: the record describes the current state.
        """
        if actor.id == user_id:
            raise AccountStatusChangeNotAllowedError
        user = self.get_user(user_id)
        if disabled:
            if user.disabled_at is None:
                user.disabled_at = utc_now()
            user.disabled_reason = reason or None
        else:
            user.disabled_at = None
            user.disabled_reason = None
        self._session.flush()
        if commit:
            self._commit()
        return user

    def promote_bootstrap_operator(self, user: User, *, bootstrap_email: str | None) -> bool:
        """Give the configured bootstrap address the operator role, once.

        The one-shot guard is ``count_operators``: as soon as any operator exists
        the setting can no longer grant anything, so forgetting to clear it does
        not leave a standing privilege path. Returns whether this call promoted
        the account.

        Nothing here accepts a role from a request body, and nothing here touches
        tenancy: an operator is a platform role, while authority inside a company
        comes only from ``workspace_members`` (architecture doc section 9).
        """
        if bootstrap_email is None or user.platform_role is PlatformRole.OPERATOR:
            return False
        if user.email != normalize_email(bootstrap_email):
            return False
        if repository.count_operators(self._session) > 0:
            return False

        user.platform_role = PlatformRole.OPERATOR
        self._session.flush()
        self._commit()
        return True

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

"""Application service implementing the authentication use cases.

Registration, login, refresh rotation with reuse detection, logout, and
access-token resolution. Token material is produced here and handed to the
cookie transport in the router --- it is never part of a response body
(architecture doc sections 4.1 and 9).

Two deliberate choices:

* **Single transaction per rotation.** Revoking the presented session and
  issuing its replacement commit together, so a half-rotated session cannot be
  observed (architecture doc section 6.2).
* **Role is read from the database, never from the token.** A demoted or
  deleted account loses authority on the next request, not when its access
  token happens to expire.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.auth import repository, tokens
from app.modules.auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    SessionError,
)
from app.modules.auth.models import RefreshSession
from app.modules.auth.passwords import hash_password, needs_rehash, verify_password
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.users.exceptions import UserNotFoundError
from app.modules.users.models import User
from app.modules.users.service import UserService
from app.modules.workspaces.service import WorkspaceService
from app.shared.time import as_utc, utc_now

DEFAULT_DISPLAY_NAME = "New member"


@dataclass(frozen=True)
class IssuedSession:
    """A user plus the freshly minted token material for the transport layer."""

    user: User
    session_id: uuid.UUID
    access_token: str
    refresh_token: str
    access_expires_at: datetime


class AuthService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserService(session)
        self._workspaces = WorkspaceService(session)

    # --- use cases ---------------------------------------------------------
    def register(self, data: RegisterRequest) -> User:
        """Create an account with an Argon2id hash, plus its private tenant.

        One transaction: an account without a personal workspace would have
        nowhere for its work to live and no way to get one later, so the two rows
        are written together and committed here (architecture doc section 6.2).
        No session is started.
        """
        user = self._users.prepare_user(
            email=data.email,
            display_name=data.display_name or _display_name_from_email(data.email),
            password_hash=hash_password(data.password),
        )
        self._workspaces.create_personal_for(user, commit=False)
        self._commit()
        return user

    def login(self, data: LoginRequest) -> IssuedSession:
        user = self._users.get_user_by_email(data.email)
        if user is None or not verify_password(data.password, user.password_hash):
            # One generic failure whether the email or the password missed.
            raise InvalidCredentialsError
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(data.password)
        # The first operator is granted here and never from a request body:
        # only the operator-configured address, and only while none exists.
        self._users.promote_bootstrap_operator(
            user, bootstrap_email=get_settings().first_operator_email
        )
        return self._start_session(user)

    def refresh(self, presented_refresh_token: str) -> IssuedSession:
        """Rotate a refresh session: single-use, with reuse detection."""
        record = repository.get_by_token_hash(
            self._session, tokens.hash_refresh_token(presented_refresh_token)
        )
        if record is None:
            raise SessionError

        if record.revoked_at is not None:
            # A rotated token was replayed. Treat the whole family as
            # compromised and revoke every live member of it.
            repository.revoke_family(self._session, record.family_id, at=utc_now())
            self._commit()
            raise SessionError

        if as_utc(record.expires_at) <= utc_now():
            repository.revoke(self._session, record, at=utc_now())
            self._commit()
            raise SessionError

        user = self._user_by_id(record.user_id)
        repository.revoke(self._session, record, at=utc_now())
        return self._start_session(user, family_id=record.family_id)

    def logout(self, *, refresh_token: str | None, access_token: str | None) -> None:
        """Revoke the presented session, if one can be identified.

        Missing, expired or already-revoked material is not an error: the
        client's cookies are cleared either way.
        """
        record = self._find_live_session(refresh_token=refresh_token, access_token=access_token)
        if record is None:
            return
        repository.revoke(self._session, record, at=utc_now())
        self._commit()

    def authenticate_access_token(self, access_token: str) -> User:
        """Resolve an access token to a live user, or refuse."""
        claims = tokens.decode_access_token(access_token)
        record = repository.get_by_id(self._session, claims.session_id)
        if (
            record is None
            or record.revoked_at is not None
            or as_utc(record.expires_at) <= utc_now()
        ):
            raise SessionError
        if record.user_id != claims.user_id:
            # Token and session row disagree: never trust the claim.
            raise AuthenticationError
        return self._user_by_id(claims.user_id)

    # --- helpers -----------------------------------------------------------
    def _start_session(self, user: User, *, family_id: uuid.UUID | None = None) -> IssuedSession:
        now = utc_now()
        refresh_token = tokens.create_refresh_token()
        record = RefreshSession(
            user_id=user.id,
            token_hash=tokens.hash_refresh_token(refresh_token),
            family_id=family_id or uuid.uuid4(),
            expires_at=tokens.refresh_expires_at(from_time=now),
            last_used_at=now,
        )
        repository.add(self._session, record)
        access = tokens.create_access_token(user.id, record.id)
        self._commit()
        return IssuedSession(
            user=user,
            session_id=record.id,
            access_token=access.token,
            refresh_token=refresh_token,
            access_expires_at=access.expires_at,
        )

    def _find_live_session(
        self, *, refresh_token: str | None, access_token: str | None
    ) -> RefreshSession | None:
        if refresh_token:
            record = repository.get_by_token_hash(
                self._session, tokens.hash_refresh_token(refresh_token)
            )
            if record is not None and record.revoked_at is None:
                return record
        if access_token:
            try:
                claims = tokens.decode_access_token(access_token)
            except AuthenticationError:
                return None
            record = repository.get_by_id(self._session, claims.session_id)
            if (
                record is not None
                and record.revoked_at is None
                and record.user_id == claims.user_id
            ):
                return record
        return None

    def _user_by_id(self, user_id: uuid.UUID) -> User:
        try:
            return self._users.get_user(user_id)
        except UserNotFoundError:
            raise AuthenticationError from None

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise


def _display_name_from_email(email: str) -> str:
    """Derive a friendly default display name from the email local part."""
    local, _, _ = email.partition("@")
    for separator in ("_", ".", "-"):
        local = local.replace(separator, " ")
    cleaned = " ".join(local.split())
    return cleaned[:100].title() or DEFAULT_DISPLAY_NAME

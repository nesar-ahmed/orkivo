"""Access and refresh token primitives.

Access tokens are short-lived signed JWTs carrying only the subject user id and
the session id. Roles are deliberately **not** embedded in the token: the
authorization decision is always read from the database, so a demoted or
revoked account can never be honoured from a token that is still unexpired
(architecture doc section 9).

Refresh tokens are opaque random strings. Only their SHA-256 digest is
persisted, so a database leak does not hand out usable sessions.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.modules.auth.exceptions import AuthenticationError
from app.shared.time import utc_now

TOKEN_ISSUER = "orkivo"
ACCESS_TOKEN_ALGORITHM = "HS256"
REFRESH_TOKEN_BYTES = 48


@dataclass(frozen=True)
class IssuedAccessToken:
    """A freshly minted access token plus the metadata clients may see."""

    token: str
    user_id: uuid.UUID
    session_id: uuid.UUID
    expires_at: datetime


@dataclass(frozen=True)
class AccessClaims:
    """Validated claims from an access token."""

    user_id: uuid.UUID
    session_id: uuid.UUID
    expires_at: datetime


def signing_key() -> str:
    """HMAC signing secret from configuration, never from source control."""
    key = get_settings().secret_key
    if not key:  # Guarded by Settings validation; keeps the type narrow here.
        raise RuntimeError("SECRET_KEY is not configured.")
    return key


def create_access_token(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    *,
    ttl_seconds: int | None = None,
) -> IssuedAccessToken:
    """Issue an access token bound to one session.

    ``ttl_seconds`` overrides the configured lifetime; it exists so tests can
    mint expired tokens without waiting. Never pass it in production code.
    """
    lifetime = (
        ttl_seconds if ttl_seconds is not None else get_settings().access_token_ttl_minutes * 60
    )
    issued_at = utc_now()
    expires_at = issued_at + timedelta(seconds=lifetime)
    payload = {
        "iss": TOKEN_ISSUER,
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": str(uuid.uuid4()),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, signing_key(), algorithm=ACCESS_TOKEN_ALGORITHM)
    return IssuedAccessToken(
        token=token,
        user_id=user_id,
        session_id=session_id,
        expires_at=expires_at,
    )


def decode_access_token(token: str) -> AccessClaims:
    """Verify signature, algorithm, issuer, expiry and claim shape."""
    try:
        payload = jwt.decode(
            token,
            signing_key(),
            algorithms=[ACCESS_TOKEN_ALGORITHM],
            issuer=TOKEN_ISSUER,
            options={"require": ["exp", "iat", "sub", "sid"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError() from exc

    try:
        return AccessClaims(
            user_id=uuid.UUID(str(payload["sub"])),
            session_id=uuid.UUID(str(payload["sid"])),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), UTC),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError() from exc


def create_refresh_token() -> str:
    """Cryptographically random opaque refresh token."""
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """Digest stored in place of the refresh token itself."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expires_at(*, from_time: datetime | None = None) -> datetime:
    """Absolute expiry for a newly issued refresh session."""
    return (from_time or utc_now()) + timedelta(days=get_settings().refresh_token_ttl_days)

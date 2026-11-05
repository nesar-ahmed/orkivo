"""Unit tests for token primitives (architecture doc section 9).

Tokens are signed, short-lived, and carry the minimum claim set: nothing about
roles or permissions lives in them.
"""

import uuid

import jwt
import pytest

from app.modules.auth.exceptions import AuthenticationError
from app.modules.auth.tokens import (
    TOKEN_ISSUER,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_refresh_token,
    refresh_expires_at,
    signing_key,
)
from app.shared.time import utc_now

pytestmark = pytest.mark.unit

USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
OTHER_SESSION = uuid.UUID("44444444-4444-4444-4444-444444444444")


def test_access_token_roundtrip() -> None:
    session_id = uuid.uuid4()

    issued = create_access_token(USER_ID, session_id)
    claims = decode_access_token(issued.token)

    assert claims.user_id == USER_ID
    assert claims.session_id == session_id
    assert claims.expires_at > utc_now()
    # JWT timestamps have second resolution, so compare within a second.
    assert abs((claims.expires_at - issued.expires_at).total_seconds()) < 1


def test_access_token_claims_carry_no_role_or_privilege() -> None:
    """Authorization comes from the database, so the token must not claim roles."""
    issued = create_access_token(USER_ID, uuid.uuid4())
    payload = jwt.decode(issued.token, options={"verify_signature": False})

    assert set(payload) == {"iss", "sub", "sid", "jti", "iat", "exp"}
    assert "role" not in payload
    assert payload["iss"] == TOKEN_ISSUER


def test_expired_access_token_is_rejected() -> None:
    issued = create_access_token(USER_ID, uuid.uuid4(), ttl_seconds=-1)

    with pytest.raises(AuthenticationError):
        decode_access_token(issued.token)


def test_tampered_access_token_is_rejected() -> None:
    issued = create_access_token(USER_ID, uuid.uuid4())
    forged = f"{issued.token[:-2]}xx"

    with pytest.raises(AuthenticationError):
        decode_access_token(forged)


def test_token_signed_with_another_secret_is_rejected() -> None:
    session_id = uuid.uuid4()
    other = jwt.encode(
        {
            "iss": TOKEN_ISSUER,
            "sub": str(USER_ID),
            "sid": str(session_id),
            "iat": int(utc_now().timestamp()),
            "exp": int(utc_now().timestamp()) + 60,
        },
        "a-completely-different-secret-value",
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(other)


def test_algorithm_confusion_is_rejected() -> None:
    """``none``/other algorithms must not be honoured by the verifier."""
    unsecured = jwt.encode(
        {
            "iss": TOKEN_ISSUER,
            "sub": str(USER_ID),
            "sid": str(uuid.uuid4()),
            "iat": int(utc_now().timestamp()),
            "exp": int(utc_now().timestamp()) + 60,
        },
        key="",
        algorithm="none",
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(unsecured)


def test_foreign_issuer_is_rejected() -> None:
    forged = jwt.encode(
        {
            "iss": "some-other-service",
            "sub": str(USER_ID),
            "sid": str(uuid.uuid4()),
            "iat": int(utc_now().timestamp()),
            "exp": int(utc_now().timestamp()) + 60,
        },
        signing_key(),
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(forged)


def test_missing_required_claim_is_rejected() -> None:
    no_session = jwt.encode(
        {
            "iss": TOKEN_ISSUER,
            "sub": str(USER_ID),
            "iat": int(utc_now().timestamp()),
            "exp": int(utc_now().timestamp()) + 60,
        },
        signing_key(),
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(no_session)


def test_non_uuid_subject_is_rejected() -> None:
    """A well-signed token with an unusable subject still fails closed."""
    weird = jwt.encode(
        {
            "iss": TOKEN_ISSUER,
            "sub": "admin",  # not a UUID
            "sid": str(OTHER_SESSION),
            "iat": int(utc_now().timestamp()),
            "exp": int(utc_now().timestamp()) + 60,
        },
        signing_key(),
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(weird)


def test_not_a_token_at_all_is_rejected() -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token("definitely-not-a-jwt")


# --- refresh tokens --------------------------------------------------------
def test_refresh_tokens_are_unique_and_high_entropy() -> None:
    first = create_refresh_token()
    second = create_refresh_token()

    assert first != second
    assert len(first) >= 32
    assert first != hash_refresh_token(first)


def test_refresh_token_digest_is_stable_and_hex() -> None:
    token = create_refresh_token()
    digest = hash_refresh_token(token)

    assert digest == hash_refresh_token(token)
    assert len(digest) == 64
    assert all(character in "0123456789abcdef" for character in digest)


def test_refresh_expiry_follows_the_long_lived_policy() -> None:
    expires = refresh_expires_at()

    assert expires > utc_now()

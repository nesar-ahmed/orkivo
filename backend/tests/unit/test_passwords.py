"""Unit tests for password hashing (architecture doc section 9).

Only synthetic credentials are used.
"""

import pytest

from app.modules.auth.passwords import (
    PASSWORD_MIN_LENGTH,
    hash_password,
    needs_rehash,
    verify_password,
)
from tests.synth import PASSWORD, WRONG_PASSWORD

pytestmark = pytest.mark.unit


def test_hash_is_argon2id_and_not_the_password() -> None:
    hashed = hash_password(PASSWORD)

    assert hashed.startswith("$argon2id$")
    assert PASSWORD not in hashed


def test_two_hashes_of_the_same_password_differ() -> None:
    """A per-hash random salt must prevent identical stored values."""
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_verify_accepts_the_matching_password() -> None:
    hashed = hash_password(PASSWORD)

    assert verify_password(PASSWORD, hashed) is True


def test_verify_rejects_a_different_password() -> None:
    hashed = hash_password(PASSWORD)

    assert verify_password(WRONG_PASSWORD, hashed) is False


def test_verify_rejects_a_malformed_hash_instead_of_raising() -> None:
    """Stored garbage must read as "no match", never as a 500."""
    assert verify_password(PASSWORD, "clearly-not-an-argon2-hash") is False
    assert verify_password(PASSWORD, "") is False


def test_verify_argument_order_is_not_swappable() -> None:
    """Guards the ``verify(hash=..., password=...)`` call site specifically."""
    hashed = hash_password(PASSWORD)

    assert verify_password(hashed, PASSWORD) is False


def test_freshly_hashed_password_does_not_need_rehash() -> None:
    assert needs_rehash(hash_password(PASSWORD)) is False


def test_needs_rehash_flags_an_unusable_hash() -> None:
    assert needs_rehash("not-an-argon2-hash") is True


def test_minimum_length_policy_is_at_least_twelve() -> None:
    assert PASSWORD_MIN_LENGTH >= 12

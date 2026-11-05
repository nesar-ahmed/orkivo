"""Password hashing with Argon2id (architecture doc section 9).

Plaintext passwords are never stored or logged. Hashing parameters are the
maintained library's defaults, and ``needs_rehash`` lets a successful login
upgrade an older hash transparently.
"""

from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Password policy bounds. The lower bound follows current guidance against
# short passwords; the upper bound caps hashing work per request.
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


@lru_cache
def _hasher() -> PasswordHasher:
    return PasswordHasher()


def hash_password(plaintext: str) -> str:
    """Return an Argon2id encoded hash for ``plaintext``."""
    return _hasher().hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Constant-shape verification; any mismatch or bad hash returns False.

    Note the argument order: :meth:`PasswordHasher.verify` takes the stored
    hash *first*, so the keyword form is used deliberately to keep the two
    arguments from being transposed.
    """
    try:
        return _hasher().verify(hash=hashed, password=plaintext)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """Whether a stored hash should be re-computed with current parameters."""
    try:
        return _hasher().check_needs_rehash(hashed)
    except InvalidHashError:
        return True

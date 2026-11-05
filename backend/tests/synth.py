"""Synthetic test data only (architecture doc section 9.1).

Constants shared by the suite: the API prefix, a throwaway credential, and
helpers for reserved-for-documentation ``example.com`` addresses (RFC 2606),
which reach no real mailbox. ``example.com`` rather than ``example.test``
because the API validates addresses with ``EmailStr``, and email-validator
rejects ``.test`` as a special-use name that cannot receive mail --- so a
``.test`` fixture would fail registration rather than exercise it.
"""

BASE = "/api/v1"

# Longer than the production minimum, and used nowhere outside tests.
PASSWORD = "correct-horse-battery-staple"
WRONG_PASSWORD = "not-the-right-horse-battery"


def email_for(label: str) -> str:
    """Deterministic synthetic address for a scenario label."""
    return f"{label}@example.com"


def slug_for(label: str) -> str:
    """Deterministic synthetic tenant address, valid for the slug pattern."""
    cleaned = label.lower().replace("_", "-").replace(".", "-")
    return f"co-{cleaned}"

"""Database access for refresh sessions.

Queries only: rotation policy, reuse detection and every other decision live in
the service layer (architecture doc sections 4.1 and 6.2).
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import RefreshSession


def get_by_token_hash(session: Session, token_hash: str) -> RefreshSession | None:
    return session.scalars(
        select(RefreshSession).where(RefreshSession.token_hash == token_hash)
    ).first()


def get_by_id(session: Session, session_id: uuid.UUID) -> RefreshSession | None:
    return session.get(RefreshSession, session_id)


def add(session: Session, record: RefreshSession) -> None:
    session.add(record)
    session.flush()


def revoke(session: Session, record: RefreshSession, *, at: datetime) -> None:
    record.revoked_at = at


def revoke_family(
    session: Session,
    family_id: uuid.UUID,
    *,
    at: datetime,
    except_id: uuid.UUID | None = None,
) -> int:
    """Revoke every live session in a rotation family; returns rows touched.

    Used when a rotated token is replayed: the whole family is treated as
    compromised (architecture doc section 9).
    """
    stmt = select(RefreshSession).where(
        RefreshSession.family_id == family_id,
        RefreshSession.revoked_at.is_(None),
    )
    if except_id is not None:
        stmt = stmt.where(RefreshSession.id != except_id)

    records = session.scalars(stmt).all()
    for record in records:
        record.revoked_at = at
    session.flush()
    return len(records)

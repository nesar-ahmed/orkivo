"""Database access for the users module.

The repository encapsulates queries only. It does not decide authorization
policy and does not return HTTP responses; transaction commits happen at the
service layer (architecture doc sections 4.1 and 6.2).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.users.enums import PlatformRole
from app.modules.users.models import User


def get_user(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def get_user_by_email(session: Session, email: str) -> User | None:
    """Look up a user by email. Emails are stored normalized (lowercase)."""
    return session.scalars(select(User).where(User.email == email)).first()


def list_users(
    session: Session,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[User], int]:
    """Return one page of users plus the total matching count."""
    stmt: Select[User] = select(User).order_by(User.created_at.desc(), User.id.desc())
    if search:
        stmt = stmt.where(
            or_(
                # icontains escapes LIKE wildcards (% and _) in user input.
                User.email.icontains(search, autoescape=True),
                User.display_name.icontains(search, autoescape=True),
            )
        )

    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def count_operators(session: Session) -> int:
    """How many accounts hold the platform operator role.

    Only used to decide whether the first-operator bootstrap still applies.
    """
    return (
        session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.platform_role == PlatformRole.OPERATOR)
        )
        or 0
    )


def add_user(session: Session, user: User) -> None:
    session.add(user)
    session.flush()

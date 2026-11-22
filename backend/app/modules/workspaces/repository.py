"""Database access for workspaces, membership and invitations.

Queries only. Whether a role is enough, whether an owner may leave, and every
other decision belong to the service (architecture doc sections 4.1 and 6.2).

Two habits this module keeps for tenant safety:
* every workspace lookup that a member triggers is authorized by
  ``access.WorkspaceAccessPolicy``, so "exists" and "you are not in it" answer
  with the same shape;
* membership is joined explicitly rather than filtered in Python, so a page of
  members costs one query instead of N.
"""

import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.workspaces.enums import InviteStatus, WorkspaceKind, WorkspaceRole
from app.modules.workspaces.models import Workspace, WorkspaceInvite, WorkspaceMember


def add(session: Session, workspace: Workspace) -> None:
    session.add(workspace)
    session.flush()


def get_by_id(session: Session, workspace_id: uuid.UUID) -> Workspace | None:
    return session.get(Workspace, workspace_id)


def get_by_slug(session: Session, slug: str) -> Workspace | None:
    return session.scalars(select(Workspace).where(Workspace.slug == slug)).first()


def get_personal_for(session: Session, user_id: uuid.UUID) -> Workspace | None:
    """The account's private tenant: the personal workspace it is a member of."""
    return session.scalars(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id, Workspace.kind == WorkspaceKind.PERSONAL)
        .order_by(Workspace.created_at, Workspace.id)
    ).first()


def get_member(
    session: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMember | None:
    return session.scalars(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).first()


def list_memberships(
    session: Session, user_id: uuid.UUID
) -> Sequence[tuple[Workspace, WorkspaceMember]]:
    """Every tenant the account belongs to, with its membership row, unpaginated.

    For reads that span the caller's tenants at once (their tasks across every
    workspace); an account belongs to a handful, so one query returns them all.
    Ordered like ``list_for_user``: the personal space first, then newest.
    """
    rows = session.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(Workspace.kind.asc(), Workspace.created_at.desc(), Workspace.id.desc())
    ).all()
    return [(workspace, member) for workspace, member in rows]


def list_for_user(
    session: Session,
    user_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[tuple[Workspace, WorkspaceRole]], int]:
    """Tenants the account belongs to, with the role held in each."""
    stmt = (
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        # Personal space first, then the newest company: the switcher reads in
        # the order people actually use it.
        .order_by(Workspace.kind.asc(), Workspace.created_at.desc(), Workspace.id.desc())
    )
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    # Unpacked into plain tuples, so nothing upstream depends on a result row.
    return [(workspace, role) for workspace, role in rows], total


def add_member(session: Session, member: WorkspaceMember) -> None:
    session.add(member)
    session.flush()


def list_members(
    session: Session,
    workspace_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[tuple[WorkspaceMember, User]], int]:
    """One page of members with their accounts, oldest membership first."""
    stmt = (
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.joined_at, WorkspaceMember.id)
    )
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return [(member, account) for member, account in rows], total


def list_roster(
    session: Session, workspace_id: uuid.UUID
) -> Sequence[tuple[User, WorkspaceRole]]:
    """Everyone in the tenant with their role, alphabetically, unpaginated.

    For a report that covers every person at once --- a workload per member ---
    where a page would silently leave people out. One query.
    """
    rows = session.execute(
        select(User, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(func.lower(User.display_name), User.id)
    ).all()
    return [(account, role) for account, role in rows]


def get_member_by_email(
    session: Session, workspace_id: uuid.UUID, email: str
) -> WorkspaceMember | None:
    """Membership of the account holding this address, if the tenant has one.

    Joined here rather than looked up through the users module: the workspaces
    module needs "is this address already in my tenant", not the account itself,
    and reading another module's repository would cross the boundary that
    architecture doc section 5 draws.
    """
    return session.scalars(
        select(WorkspaceMember)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id, User.email == email)
    ).first()


def get_member_with_user(
    session: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[WorkspaceMember, User] | None:
    """One membership plus its account, for the response that follows a change."""
    row = session.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id)
    ).first()
    if row is None:
        return None
    member, account = row
    return member, account


def list_member_accounts(
    session: Session, workspace_id: uuid.UUID, user_ids: Collection[uuid.UUID]
) -> Sequence[User]:
    """The accounts among ``user_ids`` that hold a membership of this tenant.

    One query for any number of ids, so checking an assignee and, later, every
    person mentioned in a comment costs the same round trip.
    """
    if not user_ids:
        return []
    return session.scalars(
        select(User)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace_id, User.id.in_(list(user_ids)))
    ).all()


def get_invitable_account(
    session: Session, *, user_id: uuid.UUID | None = None, email: str | None = None
) -> User | None:
    """An enabled account, by id or by its (normalized) address.

    Read here rather than through the users module for the reason given on
    ``get_member_by_email``: the question is "who can this tenant invite", which
    is workspace policy about accounts, not the account itself.
    """
    stmt = select(User).where(User.disabled_at.is_(None))
    if user_id is not None:
        stmt = stmt.where(User.id == user_id)
    elif email is not None:
        stmt = stmt.where(User.email == email)
    else:
        return None
    return session.scalars(stmt).first()


def list_invite_candidates(
    session: Session,
    *,
    actor_id: uuid.UUID,
    search: str | None,
    exact_email: str | None,
    limit: int,
) -> Sequence[User]:
    """Accounts the actor may pick when inviting, alphabetically.

    Two sources, and nothing else, so the picker can never list the platform's
    user base:

    * people who already share a workspace with the actor --- matched by a part
      of their name or address, or all of them when there is no search;
    * anyone else only by their *exact* address, which the inviter already knows.

    The actor and disabled accounts are never candidates.
    """
    my_workspaces = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == actor_id)
    colleagues = select(WorkspaceMember.user_id).where(
        WorkspaceMember.workspace_id.in_(my_workspaces)
    )
    known: ColumnElement[bool] = User.id.in_(colleagues)
    if search:
        known = and_(
            known,
            or_(
                # icontains escapes LIKE wildcards (% and _) in user input.
                User.display_name.icontains(search, autoescape=True),
                User.email.icontains(search, autoescape=True),
            ),
        )
    reachable = or_(known, User.email == exact_email) if exact_email else known
    stmt = (
        select(User)
        .where(User.id != actor_id, User.disabled_at.is_(None), reachable)
        .order_by(func.lower(User.display_name), User.id)
        .limit(limit)
    )
    return session.scalars(stmt).all()


def member_ids_among(
    session: Session, workspace_id: uuid.UUID, user_ids: Collection[uuid.UUID]
) -> set[uuid.UUID]:
    if not user_ids:
        return set()
    return set(
        session.scalars(
            select(WorkspaceMember.user_id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id.in_(list(user_ids)),
            )
        ).all()
    )


def pending_invite_emails_among(
    session: Session, workspace_id: uuid.UUID, emails: Collection[str]
) -> set[str]:
    if not emails:
        return set()
    return set(
        session.scalars(
            select(WorkspaceInvite.email).where(
                WorkspaceInvite.workspace_id == workspace_id,
                WorkspaceInvite.status == InviteStatus.PENDING,
                WorkspaceInvite.email.in_(list(emails)),
            )
        ).all()
    )


def count_members(session: Session, workspace_id: uuid.UUID) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
        )
        or 0
    )


def count_owners(session: Session, workspace_id: uuid.UUID) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.OWNER,
            )
        )
        or 0
    )


def remove_member(session: Session, member: WorkspaceMember) -> None:
    session.delete(member)
    session.flush()


def list_tenants(
    session: Session,
    *,
    search: str | None = None,
    kind: WorkspaceKind | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[tuple[Workspace, int]], int]:
    """Platform console listing: tenants with their member counts.

    Content columns are never selected here --- the row shape itself is the
    privacy guarantee, not a filter applied afterwards.
    """
    count_sub = (
        select(func.count(WorkspaceMember.id))
        .where(WorkspaceMember.workspace_id == Workspace.id)
        .correlate(Workspace)
        .scalar_subquery()
    )
    stmt = select(Workspace, count_sub.label("member_count")).order_by(
        Workspace.created_at.desc(), Workspace.id.desc()
    )
    if kind is not None:
        stmt = stmt.where(Workspace.kind == kind)
    if search:
        stmt = stmt.where(
            or_(
                # icontains escapes LIKE wildcards (% and _) in user input.
                Workspace.name.icontains(search, autoescape=True),
                Workspace.slug.icontains(search, autoescape=True),
            )
        )

    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return [(workspace, member_count) for workspace, member_count in rows], total


def add_invite(session: Session, invite: WorkspaceInvite) -> None:
    session.add(invite)
    session.flush()


def get_invite(session: Session, invite_id: uuid.UUID) -> WorkspaceInvite | None:
    return session.get(WorkspaceInvite, invite_id)


def get_invite_by_workspace_and_email(
    session: Session, workspace_id: uuid.UUID, email: str
) -> WorkspaceInvite | None:
    return session.scalars(
        select(WorkspaceInvite).where(
            WorkspaceInvite.workspace_id == workspace_id,
            WorkspaceInvite.email == email,
        )
    ).first()


def list_invites(
    session: Session,
    workspace_id: uuid.UUID,
    *,
    statuses: Sequence[InviteStatus] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[WorkspaceInvite], int]:
    """Invitations for one tenant, newest first."""
    stmt = select(WorkspaceInvite).where(WorkspaceInvite.workspace_id == workspace_id)
    if statuses:
        stmt = stmt.where(WorkspaceInvite.status.in_(list(statuses)))
    stmt = stmt.order_by(WorkspaceInvite.created_at.desc(), WorkspaceInvite.id.desc())

    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def list_pending_for_email(
    session: Session, email: str
) -> Sequence[tuple[WorkspaceInvite, Workspace, User | None]]:
    """Open invitations addressed to an account, with the tenant and inviter.

    Joined in one query because the profile screen shows the tenant's name and
    who opened it --- neither of which should cost a round trip per row.
    """
    stmt = (
        select(WorkspaceInvite, Workspace, User)
        .join(Workspace, Workspace.id == WorkspaceInvite.workspace_id)
        .outerjoin(User, User.id == WorkspaceInvite.invited_by)
        .where(
            WorkspaceInvite.email == email,
            WorkspaceInvite.status == InviteStatus.PENDING,
        )
        .order_by(WorkspaceInvite.created_at.desc(), WorkspaceInvite.id.desc())
    )
    rows = session.execute(stmt).all()
    return [(invite, workspace, inviter) for invite, workspace, inviter in rows]

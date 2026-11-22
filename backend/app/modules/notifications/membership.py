"""What the notifications module does when someone's membership of a workspace ends.

The public answer to "this person is no longer here", called by the workspaces
service in the same transaction that removes the membership, next to
``tasks.membership.release_member``. The person stops watching the workspace's
tasks, and every notification they had from it is removed: a departed member
keeps no titles or comments from a company they have left --- not even if they
are invited back later (architecture doc sections 5 and 9).

It never commits.
"""

import uuid

from sqlalchemy.orm import Session

from app.modules.notifications import repository


def forget_member(session: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    repository.forget_member(session, workspace_id=workspace_id, user_id=user_id)

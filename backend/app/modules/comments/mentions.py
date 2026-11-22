"""The mention syntax inside a comment body: ``<@user-id>``.

A mention is written into the body as a token carrying the person's id, never
their name. Display names are not unique and change; an id is neither. The
comments module owns the syntax (it is part of what a comment *is*); whoever
renders or notifies resolves the ids to people --- and only to current members of
the comment's workspace, so a token can never reach someone outside it.

These are pure functions: no database, no policy.
"""

import re
import uuid
from collections.abc import Mapping

#: ``<@8c7f...-...>``: a UUID in its canonical, hyphenated form.
MENTION_PATTERN = re.compile(
    r"<@([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})>"
)

#: A comment that mentions more people than this is a broadcast, not a mention:
#: only the first ones notify.
MAX_MENTIONS = 20


def mentioned_ids(body: str) -> list[uuid.UUID]:
    """The people a body mentions, once each, in the order they first appear."""
    found: dict[uuid.UUID, None] = {}
    for match in MENTION_PATTERN.finditer(body):
        found.setdefault(uuid.UUID(match.group(1)), None)
        if len(found) == MAX_MENTIONS:
            break
    return list(found)


def plain_text(body: str, names: Mapping[uuid.UUID, str]) -> str:
    """The body with each token shown as ``@Name`` (``@someone`` if unknown)."""

    def replace(match: re.Match[str]) -> str:
        return f"@{names.get(uuid.UUID(match.group(1)), 'someone')}"

    return MENTION_PATTERN.sub(replace, body)

"""Domain/application exceptions for the comments module."""

import uuid


class CommentNotFoundError(Exception):
    """The comment does not exist, or lives on a task the caller cannot see."""

    code = "COMMENT_NOT_FOUND"
    message = "The requested comment was not found."

    def __init__(self, comment_id: uuid.UUID) -> None:
        super().__init__(f"Comment {comment_id} was not found.")
        self.comment_id = comment_id


class CommentForbiddenError(Exception):
    """A member tried to change a comment that is not theirs to change.

    Only its author edits a comment; its author or an owner or admin deletes it.
    The caller can see the comment, so this is a 403 with the reason, not a 404.
    """

    code = "COMMENT_FORBIDDEN"
    message = "Only the author can edit this comment, or an owner or admin delete it."

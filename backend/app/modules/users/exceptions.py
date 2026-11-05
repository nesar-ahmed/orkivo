"""Domain/application exceptions for the users module.

Each exception carries the stable ``code`` and client-safe ``message`` used by
the consistent error contract (architecture doc section 7).
"""

import uuid


class UserNotFoundError(Exception):
    """The requested user does not exist."""

    code = "USER_NOT_FOUND"
    message = "The requested user was not found."

    def __init__(self, user_id: uuid.UUID) -> None:
        super().__init__(f"User {user_id} was not found.")
        self.user_id = user_id


class EmailAlreadyInUseError(Exception):
    """The email address is registered (or was claimed concurrently)."""

    code = "EMAIL_ALREADY_IN_USE"
    message = "That email address is already registered."


class RoleChangeNotAllowedError(Exception):
    """An admin attempted to change their own role."""

    code = "ROLE_CHANGE_NOT_ALLOWED"
    message = "You cannot change your own role."


class AccountStatusChangeNotAllowedError(Exception):
    """An operator tried to disable or re-enable their own account.

    Refused for the same reason as changing one's own platform role: it is how a
    console can end up with nobody able to undo the mistake.
    """

    code = "ACCOUNT_STATUS_CHANGE_NOT_ALLOWED"
    message = "You cannot disable or enable your own account."

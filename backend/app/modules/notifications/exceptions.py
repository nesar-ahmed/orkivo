"""Domain/application exceptions for the notifications module."""

import uuid


class NotificationNotFoundError(Exception):
    """The notification does not exist, or is not the caller's.

    One answer for both: an inbox is private, and ids are never confirmed to
    anyone else.
    """

    code = "NOTIFICATION_NOT_FOUND"
    message = "The requested notification was not found."

    def __init__(self, notification_id: uuid.UUID) -> None:
        super().__init__(f"Notification {notification_id} was not found.")
        self.notification_id = notification_id

"""Domain/application exceptions for the labels module."""

import uuid


class LabelNotFoundError(Exception):
    """The requested label does not exist (or is not visible)."""

    code = "LABEL_NOT_FOUND"
    message = "The requested label was not found."

    def __init__(self, label_id: uuid.UUID) -> None:
        super().__init__(f"Label {label_id} was not found.")
        self.label_id = label_id


class LabelNameInUseError(Exception):
    """Another label in the same workspace already has this name.

    Compared without regard to case: "Bug" and "bug" would be the same tag to
    anyone choosing between them in a menu.
    """

    code = "LABEL_NAME_IN_USE"
    message = "A label with this name already exists in this workspace."


class LabelConflictError(Exception):
    """Someone changed the label after the caller read it."""

    code = "LABEL_CONFLICT"
    message = (
        "This label was changed by someone else after you opened it. "
        "Reload it to see the latest version."
    )

    def __init__(self, label_id: uuid.UUID) -> None:
        super().__init__(f"Label {label_id} changed concurrently.")
        self.label_id = label_id


class LabelLimitReachedError(Exception):
    """The workspace already holds as many labels as it may.

    Labels are a shared vocabulary picked from a menu; past a hundred, nobody can
    find the right one any more, and every picker would have to page.
    """

    code = "LABEL_LIMIT_REACHED"

    def __init__(self, limit: int) -> None:
        super().__init__(f"A workspace holds at most {limit} labels.")
        self.message = (
            f"This workspace already has {limit} labels, the most it can hold. "
            "Delete or reuse one instead."
        )

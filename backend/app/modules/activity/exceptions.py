"""Domain/application exceptions for the activity module."""


class ActivityLogIsAppendOnlyError(RuntimeError):
    """Something tried to change or remove a recorded event.

    A programming error, never a request error: no route offers it, so reaching
    this means a code path bypassed the repository. It answers 500 and the
    transaction is rolled back, which is the point.
    """

    def __init__(self, operation: str) -> None:
        super().__init__(f"Activity events are append-only; refused to {operation} one.")

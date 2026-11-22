"""Domain/application exceptions for the projects module."""

import uuid


class ProjectNotFoundError(Exception):
    """The requested project does not exist (or is not visible)."""

    code = "PROJECT_NOT_FOUND"
    message = "The requested project was not found."

    def __init__(self, project_id: uuid.UUID) -> None:
        super().__init__(f"Project {project_id} was not found.")
        self.project_id = project_id


class ProjectNameInUseError(Exception):
    """Another project in the same workspace already has this name.

    Compared without regard to case: "Website" and "website" would be the same
    group to anyone choosing between them in a menu.
    """

    code = "PROJECT_NAME_IN_USE"
    message = "A project with this name already exists in this workspace."


class ProjectConflictError(Exception):
    """Someone changed the project after the caller read it."""

    code = "PROJECT_CONFLICT"
    message = (
        "This project was changed by someone else after you opened it. "
        "Reload it to see the latest version."
    )

    def __init__(self, project_id: uuid.UUID) -> None:
        super().__init__(f"Project {project_id} changed concurrently.")
        self.project_id = project_id

"""Projects module: named groups of work inside one workspace.

Owns: project lifecycle (create, rename, describe, delete). Does not own: the
tasks filed under a project (``tasks``), or who may touch a tenant at all ---
that is ``workspaces.access``, asked on every use case (architecture doc
section 5).

Deleting a project never deletes work. The tasks module detaches them in the
same transaction through its public ``project_links``, so a deleted project
leaves its tasks in the workspace, under "no project".
"""

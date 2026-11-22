"""Tasks module: task lifecycle, status, and priority.

Owns: task CRUD, board status, who a task is assigned to, and which project it
is filed under. Does not own: user credentials (``auth``), workspace membership
and its roles (``workspaces``), project lifecycle (``projects``), or the decision
of *which* tenants a caller may read or write --- that is ``workspaces.access``,
which this module asks on every use case (architecture doc section 5).

Two public entry points exist for the modules that own those neighbours, so
neither ever touches the tasks table itself: ``membership`` (a member left) and
``project_links`` (project task counts; a project was deleted).
"""

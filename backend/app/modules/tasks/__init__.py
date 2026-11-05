"""Tasks module: task lifecycle, status, and priority.

Owns: task CRUD and board status. Does not own: user credentials (``auth``),
workspace membership and its roles (``workspaces``), or the decision of *which*
tenants a caller may read or write --- that is ``workspaces.access``, which this
module asks on every use case (architecture doc section 5).
"""

"""Tasks module: task lifecycle, status, and priority.

Owns: task CRUD and board status. Does not own: user credentials (``auth``) or
workspace membership and its roles (``workspaces``) --- and, once tasks are
scoped to a tenant, not the decision of *which* tenants a caller may read either
(architecture doc section 5).
"""

"""Labels module: named, colored tags for tasks, inside one workspace.

Owns: label lifecycle (create, rename, recolor, delete). Does not own: which
tasks carry a label (``tasks``), or who may touch a tenant at all --- that is
``workspaces.access``, asked on every use case (architecture doc section 5).

A label is vocabulary shared by a workspace, like a project, but a task may carry
several. Deleting a label never deletes work: the tasks module takes it off every
task in the same transaction through its public ``label_links``.
"""

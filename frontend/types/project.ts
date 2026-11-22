/**
 * Typed domain contracts for projects, mirroring
 * backend/app/modules/projects/schemas.py.
 *
 * A project is a named group of work inside exactly one workspace. Names are
 * unique per workspace regardless of case; deleting a project keeps its tasks,
 * which stay in the workspace without a project.
 */

/** Who created a project: a name to recognise, never an email. */
export interface ProjectPerson {
  id: string;
  display_name: string;
}

export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  /** Increments on every change. Send it back on update or delete. */
  version: number;
  /** `null` only if the account is gone. */
  created_by: ProjectPerson | null;
  created_at: string;
  updated_at: string;
}

/** A project in its workspace's list, with how much work it holds. */
export interface ProjectSummary extends Project {
  task_count: number;
  /** Everything not yet done. */
  open_task_count: number;
}

/** Paginated collection envelope returned by GET /workspaces/{id}/projects. */
export interface ProjectListResponse {
  items: ProjectSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ProjectCreateInput {
  name: string;
  description?: string | null;
}

/**
 * PATCH payload: only provided fields are changed. `version` is the version the
 * client read; if a colleague saved since, the API answers 409 `PROJECT_CONFLICT`.
 */
export type ProjectUpdateInput = Partial<ProjectCreateInput> & { version?: number };

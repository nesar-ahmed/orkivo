/**
 * Typed domain contracts mirroring the backend API
 * (backend/app/modules/tasks/schemas.py).
 *
 * A task lives in exactly one workspace. Who may read or change it follows from
 * membership of that workspace, decided by the backend on every request.
 */

export type TaskStatus = "todo" | "in_progress" | "done";
export type TaskPriority = "low" | "medium" | "high";

/** Who created or last changed a task: a name to recognise, never an email. */
export interface TaskPerson {
  id: string;
  display_name: string;
}

export interface Task {
  id: string;
  /** The workspace holding the task: private to one person, or a shared company. */
  workspace_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  /** Increments on every change. Send it back on update to detect conflicts. */
  version: number;
  created_by: TaskPerson | null;
  /** `null` until the task is first edited. */
  updated_by: TaskPerson | null;
  created_at: string;
  updated_at: string;
}

/** Paginated collection envelope returned by GET /workspaces/{id}/tasks. */
export interface TaskListResponse {
  items: Task[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TaskCreateInput {
  title: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  due_date?: string | null;
}

/**
 * PATCH payload: only provided fields are changed. `version` is the version the
 * client read; if a colleague saved since, the API answers 409 `TASK_CONFLICT`.
 */
export type TaskUpdateInput = Partial<TaskCreateInput> & { version?: number };

/** Field-level validation detail from the backend error contract. */
export interface ApiErrorDetail {
  field: string | null;
  message: string;
}

/**
 * Typed domain contracts mirroring the backend API
 * (backend/app/modules/tasks/schemas.py).
 */

export type TaskStatus = "todo" | "in_progress" | "done";
export type TaskPriority = "low" | "medium" | "high";

export interface Task {
  id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

/** Paginated collection envelope returned by GET /tasks. */
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

/** PATCH payload: only provided fields are changed. */
export type TaskUpdateInput = Partial<TaskCreateInput>;

/** Field-level validation detail from the backend error contract. */
export interface ApiErrorDetail {
  field: string | null;
  message: string;
}

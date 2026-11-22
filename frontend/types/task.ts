/**
 * Typed domain contracts mirroring the backend API
 * (backend/app/modules/tasks/schemas.py).
 *
 * A task lives in exactly one workspace. Who may read or change it follows from
 * membership of that workspace, decided by the backend on every request.
 */

import type { LabelColor } from "@/types/label";

export type TaskStatus = "todo" | "in_progress" | "done";
export type TaskPriority = "low" | "medium" | "high";

/**
 * What the caller may do to one task, beyond reading it, as decided by the
 * backend (`tasks/permissions.py`): anyone running the work may change or delete
 * any task; a member changes the tasks they created or hold and deletes the ones
 * they created.
 */
export type TaskCapability = "edit" | "delete";

/** Who created, changed or holds a task: a name to recognise, never an email. */
export interface TaskPerson {
  id: string;
  display_name: string;
}

/** The project a task is filed under: enough to label and group it. */
export interface TaskProject {
  id: string;
  name: string;
}

/** A label a task carries: enough to show it as a colored chip and filter by it. */
export interface TaskLabel {
  id: string;
  name: string;
  color: LabelColor;
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
  /** Who is expected to do it: always a member of the task's workspace, or `null`. */
  assignee: TaskPerson | null;
  /** One of the task's own workspace's projects, or `null`. */
  project: TaskProject | null;
  /** Labels of the task's own workspace, alphabetically; empty when it has none. */
  labels: TaskLabel[];
  /**
   * How many unfinished tasks this one still waits on. Informative only: a
   * blocked task can still be started or finished.
   */
  open_blocker_count: number;
  /**
   * What the caller may do to this task right now. Rendering hint only: every
   * save is re-checked, and an empty list means read only.
   */
  capabilities: TaskCapability[];
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
  /** A member of the workspace; the API answers 422 `ASSIGNEE_NOT_MEMBER` otherwise. */
  assignee_id?: string | null;
  /** A project of the same workspace; the API answers 422 `PROJECT_NOT_IN_WORKSPACE` otherwise. */
  project_id?: string | null;
  /**
   * Labels of the same workspace (422 `LABEL_NOT_IN_WORKSPACE` otherwise). On
   * update this *replaces* the set; send `[]` to remove every label, never `null`.
   */
  label_ids?: string[];
}

/**
 * The `?assignee=` filter: a member's id, `me` (resolved to the caller by the
 * backend, so a shared link shows each person their own work) or `none`. The
 * `& {}` keeps the two keywords visible to editors instead of widening to `string`.
 */
export type TaskAssigneeFilter = "me" | "none" | (string & {});

/** The `?project=` filter: a project's id, or `none` for tasks outside every project. */
export type TaskProjectFilter = "none" | (string & {});

/** The `?label=` filter: a label's id, or `none` for tasks carrying no label. */
export type TaskLabelFilter = "none" | (string & {});

/**
 * How the API sorts a list. `project` keeps each project's tasks together
 * (alphabetically, tasks without one last), so a page can be shown grouped;
 * `due` is soonest due first with undated tasks last; `priority` is high first.
 */
export type TaskOrder = "newest" | "project" | "due" | "priority";

/** The `?status=` filter: one status, or `open` for everything not done. */
export type TaskStatusFilter = TaskStatus | "open";

/**
 * PATCH payload: only provided fields are changed. `version` is the version the
 * client read; if a colleague saved since, the API answers 409 `TASK_CONFLICT`.
 */
export type TaskUpdateInput = Partial<TaskCreateInput> & { version?: number };

/** One task in a bulk request, with the version the client read (409 if stale). */
export interface BulkTaskRef {
  id: string;
  version?: number;
}

/**
 * What a bulk update changes on every selected task; only supplied fields change.
 * Labels are added and removed rather than replaced, so each task keeps the rest.
 */
export interface BulkTaskChanges {
  status?: TaskStatus;
  priority?: TaskPriority;
  due_date?: string | null;
  assignee_id?: string | null;
  project_id?: string | null;
  add_label_ids?: string[];
  remove_label_ids?: string[];
}

/** Field-level validation detail from the backend error contract. */
export interface ApiErrorDetail {
  field: string | null;
  message: string;
}

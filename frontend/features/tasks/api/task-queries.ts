/**
 * Typed read operations against the tasks API.
 *
 * Lists are read *from a workspace* --- the board shows one tenant at a time, and
 * the backend answers "not found" for a workspace the caller is not in --- or, for
 * a person's own list, from `/me/tasks`, which spans every workspace they are in.
 * Both take the same filters, written the same way.
 */

import { apiClient } from "@/lib/api/client";
import type {
  Task,
  TaskAssigneeFilter,
  TaskLabelFilter,
  TaskListResponse,
  TaskOrder,
  TaskPriority,
  TaskProjectFilter,
  TaskStatusFilter,
} from "@/types/task";

export interface TaskListParams {
  status?: TaskStatusFilter;
  priority?: TaskPriority;
  assignee?: TaskAssigneeFilter;
  project?: TaskProjectFilter;
  label?: TaskLabelFilter;
  /** Due on or after this day (`YYYY-MM-DD`). */
  due_from?: string;
  /** Due on or before this day (`YYYY-MM-DD`). */
  due_to?: string;
  /** `true` for scheduled tasks only, `false` for unscheduled ones only. */
  has_due_date?: boolean;
  order?: TaskOrder;
  page?: number;
  page_size?: number;
  search?: string;
}

/** A person's own list takes the same filters, except whose tasks, plus one workspace. */
export interface MyTaskListParams extends Omit<TaskListParams, "assignee"> {
  workspace?: string;
}

function listSuffix(params: MyTaskListParams & TaskListParams): string {
  const query = new URLSearchParams();
  if (params.workspace) query.set("workspace", params.workspace);
  if (params.status) query.set("status", params.status);
  if (params.priority) query.set("priority", params.priority);
  if (params.assignee) query.set("assignee", params.assignee);
  if (params.project) query.set("project", params.project);
  if (params.label) query.set("label", params.label);
  if (params.due_from) query.set("due_from", params.due_from);
  if (params.due_to) query.set("due_to", params.due_to);
  if (params.has_due_date !== undefined) query.set("has_due_date", String(params.has_due_date));
  if (params.order) query.set("order", params.order);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.search) query.set("search", params.search);
  return query.size > 0 ? `?${query.toString()}` : "";
}

export function fetchTasks(
  workspaceId: string,
  params: TaskListParams = {},
  cookie?: string,
): Promise<TaskListResponse> {
  return apiClient.get<TaskListResponse>(
    `/workspaces/${workspaceId}/tasks${listSuffix(params)}`,
    cookie ? { cookie } : {},
  );
}

/**
 * The caller's own work in every workspace: what is assigned to them, plus their
 * private to-dos. Soonest due first unless `order` says otherwise.
 */
export function fetchMyTasks(
  params: MyTaskListParams = {},
  cookie?: string,
): Promise<TaskListResponse> {
  return apiClient.get<TaskListResponse>(
    `/me/tasks${listSuffix(params)}`,
    cookie ? { cookie } : {},
  );
}

export function fetchTask(taskId: string, cookie?: string): Promise<Task> {
  return apiClient.get<Task>(`/tasks/${taskId}`, cookie ? { cookie } : {});
}
